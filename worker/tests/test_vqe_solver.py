"""Unit tests for VQE solver runtime behavior."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
from qiskit.quantum_info import SparsePauliOp

from worker.adapters.base import BackendExecutionContext
from worker.adapters.result_adapter import normalize_result
from worker.chemistry import vqe_solver
from worker.chemistry.vqe_solver import run_vqe


class _FakeEstimatorJob:
    def __init__(self, energy: float, standard_error: float = 0.025) -> None:
        self._energy = energy
        self._standard_error = standard_error

    def result(self):
        pub_result = SimpleNamespace(
            data=SimpleNamespace(
                evs=np.asarray([self._energy]),
                stds=np.asarray([self._standard_error]),
            )
        )
        return [pub_result]


class _FakeEstimator:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def run(self, pubs):
        pub = pubs[0]
        self.calls.append(pub)
        _, observables, parameter_grid = pub
        _ = observables
        parameters = np.asarray(parameter_grid[0], dtype=float)
        energy = float(np.sum(parameters**2))
        return _FakeEstimatorJob(energy)


def test_run_vqe_uses_v2_pub_shape_for_estimator_calls() -> None:
    backend = _FakeEstimator()
    hamiltonian = SparsePauliOp.from_list([("Z", 1.0)])

    result = run_vqe(
        hamiltonian=hamiltonian,
        backend=backend,
        config={
            "algorithm": "vqe",
            "max_iterations": 4,
            "optimizer_name": "COBYLA",
            "ansatz_name": "EfficientSU2",
            "initial_point": [0.2, -0.3, 0.1, -0.1, 0.05, -0.05],
        },
    )

    assert result.algorithm == "vqe"
    assert result.primary_iterations is not None
    assert result.primary_iterations >= 1
    assert len(result.convergence_trace) >= 1
    assert result.optimizer_diagnostics["independent_reevaluation_status"] == "completed"
    assert result.optimizer_diagnostics["independent_final_energy"] == pytest.approx(
        result.optimizer_diagnostics["final_energy"]
    )
    assert result.optimizer_diagnostics["independent_final_standard_error"] == pytest.approx(
        0.025
    )
    assert result.optimizer_diagnostics["independent_uncertainty_status"] == "available"
    assert backend.calls
    assert result.optimizer_diagnostics["convergence_threshold"] == pytest.approx(1e-8)
    assert result.optimizer_diagnostics["convergence_threshold_policy"] == "absolute_energy_delta"
    assert (
        result.optimizer_diagnostics["reference_descriptor"]["reference_source"]
        == "vqe_optimizer"
    )
    assert result.optimizer_diagnostics["reference_descriptor"]["circuit_fingerprint"]

    circuit, observables, parameter_grid = backend.calls[0]
    assert hasattr(circuit, "num_parameters")
    assert isinstance(observables, list)
    assert len(observables) == 1
    assert isinstance(observables[0], SparsePauliOp)
    assert isinstance(parameter_grid, list)
    assert len(parameter_grid) == 1
    assert isinstance(parameter_grid[0], list)


def test_number_preserving_vqe_records_zero_ideal_sector_leakage() -> None:
    backend = _FakeEstimator()
    hamiltonian = SimpleNamespace(
        pauli_hamiltonian=SparsePauliOp.from_list([("IIII", 1.0)]),
        num_qubits=4,
        num_spatial_orbitals=2,
        num_electrons_alpha=1,
        num_electrons_beta=1,
    )

    result = run_vqe(
        hamiltonian=hamiltonian,
        backend=backend,
        config={
            "algorithm": "vqe",
            "max_iterations": 2,
            "optimizer_name": "COBYLA",
            "ansatz_name": "NumberPreserving",
            "initial_point_strategy": "zero",
        },
    )

    assert result.optimizer_diagnostics["ideal_sector_leakage"] == pytest.approx(0.0)
    assert result.optimizer_diagnostics["sector_diagnostic_source"] == (
        "ideal_statevector_from_ansatz"
    )


def test_run_vqe_supports_spsa_runtime_path() -> None:
    backend = _FakeEstimator()
    hamiltonian = SparsePauliOp.from_list([("Z", 1.0)])

    result = run_vqe(
        hamiltonian=hamiltonian,
        backend=backend,
        config={
            "algorithm": "vqe",
            "max_iterations": 3,
            "optimizer_name": "SPSA",
            "ansatz_name": "EfficientSU2",
            "seed": 7,
            "optimizer_options": {
                "learning_rate": 0.2,
                "perturbation": 0.05,
            },
        },
    )

    assert result.algorithm == "vqe"
    assert result.primary_iterations is not None
    assert result.primary_iterations >= 1
    assert len(result.convergence_trace) >= 1
    assert backend.calls
    assert result.optimizer_diagnostics["optimizer_iterations"] >= 1
    assert result.optimizer_diagnostics["convergence_threshold"] == pytest.approx(1e-8)


def test_run_vqe_noise_aware_policy_selects_spsa_without_explicit_optimizer() -> None:
    result = run_vqe(
        hamiltonian=SparsePauliOp.from_list([("Z", 1.0)]),
        backend=_FakeEstimator(),
        config={
            "algorithm": "vqe",
            "max_iterations": 2,
            "optimizer_policy": "noise_aware_auto",
            "ansatz_name": "EfficientSU2",
            "initial_point_strategy": "zero",
        },
        backend_context=BackendExecutionContext(
            backend_target="aer_simulator",
            noise_profile={"source": "custom_preset"},
        ),
    )

    assert result.optimizer_diagnostics["optimizer_name"] == "SPSA"
    assert result.optimizer_diagnostics["optimizer_policy"] == "noise_aware_auto"
    assert result.optimizer_diagnostics["optimizer_selection_reason"] == "noise_aware_auto"


def test_run_vqe_emits_live_progress_callbacks() -> None:
    backend = _FakeEstimator()
    hamiltonian = SparsePauliOp.from_list([("Z", 1.0)])
    progress_events: list[dict[str, object]] = []

    result = run_vqe(
        hamiltonian=hamiltonian,
        backend=backend,
        config={
            "algorithm": "vqe",
            "max_iterations": 4,
            "optimizer_name": "COBYLA",
            "ansatz_name": "EfficientSU2",
            "initial_point": [0.2, -0.3, 0.1, -0.1, 0.05, -0.05],
        },
        progress_callback=progress_events.append,
    )

    assert result.algorithm == "vqe"
    assert progress_events
    assert all(event["algorithm"] == "vqe" for event in progress_events)
    assert all(event["stage"] == "progress" for event in progress_events)
    assert len(progress_events) == len(result.convergence_trace)
    assert all(event["objective_evaluations"] == event["iteration"] for event in progress_events)
    assert all(event["max_function_evaluations"] is None for event in progress_events)


def test_run_vqe_does_not_treat_flat_final_delta_as_convergence(monkeypatch) -> None:
    """A repeated final energy is not enough when the optimizer reports failure."""
    backend = _FakeEstimator()
    hamiltonian = SparsePauliOp.from_list([("Z", 1.0)])

    def fake_minimize(objective, x0, method, options, bounds):
        del method, options, bounds
        first_energy = objective(np.asarray(x0, dtype=float))
        second_energy = objective(np.asarray(x0, dtype=float))
        assert first_energy == second_energy
        return SimpleNamespace(
            x=np.asarray(x0, dtype=float),
            fun=second_energy,
            success=False,
            status=3,
            message="max function evaluations",
            nfev=2,
            nit=1,
        )

    monkeypatch.setattr(vqe_solver, "minimize", fake_minimize)

    result = run_vqe(
        hamiltonian=hamiltonian,
        backend=backend,
        config={
            "algorithm": "vqe",
            "max_iterations": 4,
            "optimizer_name": "COBYLA",
            "ansatz_name": "EfficientSU2",
            "initial_point": [0.2, -0.3, 0.1, -0.1, 0.05, -0.05],
        },
    )

    assert result.converged is False
    assert result.optimizer_diagnostics["success"] is False
    assert result.optimizer_diagnostics["final_delta_energy"] == pytest.approx(0.0)
    assert result.optimizer_diagnostics["convergence_threshold"] == pytest.approx(1e-8)


def test_run_vqe_rejects_non_finite_objective_values() -> None:
    class NonFiniteEstimator(_FakeEstimator):
        def run(self, pubs):
            del pubs
            return _FakeEstimatorJob(float("nan"))

    with pytest.raises(ValueError, match="non-finite energy"):
        run_vqe(
            hamiltonian=SparsePauliOp.from_list([("Z", 1.0)]),
            backend=NonFiniteEstimator(),
            config={
                "algorithm": "vqe",
                "max_iterations": 2,
                "optimizer_name": "COBYLA",
                "ansatz_name": "EfficientSU2",
                "initial_point_strategy": "zero",
            },
        )


def test_run_vqe_hard_stops_scipy_by_function_evaluations(monkeypatch) -> None:
    backend = _FakeEstimator()
    hamiltonian = SparsePauliOp.from_list([("Z", 1.0)])

    def fake_minimize(objective, x0, method, options, bounds):
        del method, options, bounds
        for _ in range(10):
            objective(np.asarray(x0, dtype=float))
        raise AssertionError("objective cap did not stop scipy minimization")

    monkeypatch.setattr(vqe_solver, "minimize", fake_minimize)

    result = run_vqe(
        hamiltonian=hamiltonian,
        backend=backend,
        config={
            "algorithm": "vqe",
            "max_iterations": 20,
            "max_function_evaluations": 3,
            "optimizer_name": "COBYLA",
            "ansatz_name": "EfficientSU2",
            "initial_point_strategy": "zero",
        },
    )

    assert result.converged is False
    assert result.primary_iterations == 3
    assert len(result.convergence_trace) == 3
    assert len(backend.calls) == 3
    assert (
        result.optimizer_diagnostics["independent_reevaluation_status"]
        == "skipped_max_function_evaluations"
    )
    assert result.optimizer_diagnostics["termination_reason"] == "max_function_evaluations"
    assert result.optimizer_diagnostics["objective_evaluations"] == 3
    assert result.optimizer_diagnostics["function_evaluations"] == 3
    assert result.optimizer_diagnostics["optimizer_iterations"] is None

    metrics = normalize_result(result)["algorithm_metrics"]
    assert metrics["objective_evaluations"] == 3
    assert metrics["optimizer_iterations"] is None
    assert metrics["max_function_evaluations"] == 3


def test_run_vqe_reports_best_observed_energy_and_keeps_final_optimizer_state(
    monkeypatch,
) -> None:
    backend = _FakeEstimator()
    hamiltonian = SparsePauliOp.from_list([("Z", 1.0)])

    def fake_minimize(objective, x0, method, options, bounds):
        del method, options, bounds
        best_point = np.zeros_like(x0)
        final_point = np.full_like(x0, 0.5)
        best_energy = objective(best_point)
        final_energy = objective(final_point)
        assert best_energy < final_energy
        return SimpleNamespace(
            x=final_point,
            fun=final_energy,
            success=True,
            status=0,
            message="ok",
            nfev=2,
            nit=2,
        )

    monkeypatch.setattr(vqe_solver, "minimize", fake_minimize)

    result = run_vqe(
        hamiltonian=hamiltonian,
        backend=backend,
        config={
            "algorithm": "vqe",
            "max_iterations": 4,
            "optimizer_name": "COBYLA",
            "ansatz_name": "EfficientSU2",
            "initial_point": [0.2, -0.3, 0.1, -0.1, 0.05, -0.05],
        },
    )

    expected_zero_parameters = [0.0] * len(result.optimal_parameters)
    expected_final_parameters = [0.5] * len(result.optimal_parameters)

    assert result.primary_energy == pytest.approx(0.0)
    assert result.optimal_parameters == pytest.approx(expected_zero_parameters)
    assert result.optimizer_diagnostics["final_energy"] > result.primary_energy
    assert (
        result.optimizer_diagnostics["reported_energy_source"]
        == "best_observed_optimizer_evaluation"
    )
    assert result.optimizer_diagnostics["best_observed_parameters"] == pytest.approx(
        expected_zero_parameters
    )
    assert result.optimizer_diagnostics["final_parameters"] == pytest.approx(
        expected_final_parameters
    )

    metrics = normalize_result(result)["algorithm_metrics"]
    artifacts = metrics["circuit_artifacts"]
    assert [artifact["role"] for artifact in artifacts] == ["ansatz", "final", "optimizer_final"]
    assert artifacts[1]["label"] == "Best observed VQE circuit"
    assert artifacts[2]["label"] == "Last optimizer circuit"


def test_run_vqe_emits_ansatz_and_final_circuit_artifacts() -> None:
    backend = _FakeEstimator()
    hamiltonian = SparsePauliOp.from_list([("Z", 1.0)])

    result = run_vqe(
        hamiltonian=hamiltonian,
        backend=backend,
        config={
            "algorithm": "vqe",
            "max_iterations": 2,
            "optimizer_name": "COBYLA",
            "ansatz_name": "EfficientSU2",
            "initial_point_strategy": "zero",
        },
    )

    metrics = normalize_result(result)["algorithm_metrics"]
    artifacts = metrics["circuit_artifacts"]
    assert [artifact["role"] for artifact in artifacts] == ["ansatz", "final"]
    assert all(artifact["artifact_type"] == "quantum_circuit" for artifact in artifacts)
    assert artifacts[0]["artifact_id"] == "vqe.ansatz"
    assert artifacts[1]["artifact_id"] == "vqe.final"
    assert artifacts[1]["parameters"]["bound"] is True
    assert "OPENQASM 3.0" in artifacts[1]["preview"]["qasm"]


def test_run_vqe_respects_reps_config() -> None:
    """VQE with reps=2 must produce more parameters than reps=1."""
    backend_r1 = _FakeEstimator()
    backend_r2 = _FakeEstimator()
    hamiltonian = SparsePauliOp.from_list([("ZZ", 1.0), ("XI", -0.5)])

    run_vqe(
        hamiltonian=hamiltonian,
        backend=backend_r1,
        config={
            "algorithm": "vqe",
            "max_iterations": 2,
            "optimizer_name": "COBYLA",
            "ansatz_name": "EfficientSU2",
            "reps": 1,
        },
    )
    run_vqe(
        hamiltonian=hamiltonian,
        backend=backend_r2,
        config={
            "algorithm": "vqe",
            "max_iterations": 2,
            "optimizer_name": "COBYLA",
            "ansatz_name": "EfficientSU2",
            "reps": 2,
        },
    )

    _, _, params_r1 = backend_r1.calls[0]
    _, _, params_r2 = backend_r2.calls[0]
    assert len(params_r2[0]) > len(params_r1[0]), (
        "reps=2 ansatz must have more parameters than reps=1"
    )


def test_run_vqe_default_reps_is_2() -> None:
    """When reps is not specified, the ansatz must use reps=2 (not reps=1)."""
    backend_default = _FakeEstimator()
    backend_explicit = _FakeEstimator()
    hamiltonian = SparsePauliOp.from_list([("ZZ", 1.0)])

    run_vqe(
        hamiltonian=hamiltonian,
        backend=backend_default,
        config={
            "algorithm": "vqe",
            "max_iterations": 2,
            "optimizer_name": "COBYLA",
            "ansatz_name": "EfficientSU2",
        },
    )
    run_vqe(
        hamiltonian=hamiltonian,
        backend=backend_explicit,
        config={
            "algorithm": "vqe",
            "max_iterations": 2,
            "optimizer_name": "COBYLA",
            "ansatz_name": "EfficientSU2",
            "reps": 2,
        },
    )

    _, _, params_default = backend_default.calls[0]
    _, _, params_explicit = backend_explicit.calls[0]
    assert len(params_default[0]) == len(params_explicit[0]), (
        "default reps must produce the same parameter count as explicit reps=2"
    )


def test_run_vqe_selects_best_warm_start_candidate(monkeypatch) -> None:
    """Zero-plus-random warm start should begin scipy optimization from the best candidate."""
    backend = _FakeEstimator()
    hamiltonian = SparsePauliOp.from_list([("Z", 1.0)])
    selected_x0: list[np.ndarray] = []

    def fake_minimize(objective, x0, method, options, bounds):
        del method, options, bounds
        selected_x0.append(np.asarray(x0, dtype=float))
        energy = objective(np.asarray(x0, dtype=float))
        return SimpleNamespace(
            x=np.asarray(x0, dtype=float),
            fun=energy,
            success=True,
            status=0,
            message="ok",
            nfev=1,
            nit=1,
        )

    monkeypatch.setattr(vqe_solver, "minimize", fake_minimize)

    result = run_vqe(
        hamiltonian=hamiltonian,
        backend=backend,
        config={
            "algorithm": "vqe",
            "max_iterations": 2,
            "optimizer_name": "COBYLA",
            "ansatz_name": "EfficientSU2",
            "initial_point_strategy": "zero_plus_seeded_random",
            "initial_point_candidates": 3,
            "seed": 7,
        },
    )

    assert selected_x0
    assert np.allclose(selected_x0[0], np.zeros_like(selected_x0[0]))
    assert result.optimizer_diagnostics["initial_point_candidates"] == 3
    assert result.optimizer_diagnostics["initial_point_best_index"] == 0
    assert result.optimizer_diagnostics["initial_point_selection_evaluations"] == 3
    assert result.optimizer_diagnostics["seed"] == 7


def test_run_vqe_retries_stationary_zero_warm_start_for_gradient_optimizers(monkeypatch) -> None:
    """L-BFGS-B should not stop forever on a zero warm start when alternates improve later."""
    backend = _FakeEstimator()
    hamiltonian = SparsePauliOp.from_list([("Z", 1.0)])
    calls: list[np.ndarray] = []

    def fake_build_initial_point_candidates(*args, **kwargs):
        del args, kwargs
        zero = np.zeros(6, dtype=float)
        return [zero, np.full(6, 2.0, dtype=float)], {
            "initial_point_strategy": "zero_plus_seeded_random",
            "initial_point_candidates": 2,
            "initial_point_selection_evaluations": 2,
        }

    def fake_select_initial_point(*, objective, candidates):
        energies = [float(objective(candidate)) for candidate in candidates]
        return candidates[0], {
            "initial_point_best_index": 0,
            "initial_point_best_energy": energies[0],
            "initial_point_candidate_energies": energies,
        }

    def fake_evaluate_energy(*, backend, ansatz, operator, parameter_values):
        del backend, ansatz, operator
        first_param = float(np.asarray(parameter_values, dtype=float)[0])
        return float(first_param**4 - first_param**2)

    def fake_minimize(objective, x0, method, options, bounds):
        del method, options, bounds
        candidate = np.asarray(x0, dtype=float)
        calls.append(candidate.copy())
        if np.allclose(candidate, 0.0):
            energy = objective(candidate)
            return SimpleNamespace(
                x=candidate,
                fun=energy,
                success=True,
                status=0,
                message="stationary",
                nfev=1,
                nit=0,
            )

        improved = candidate.copy()
        improved[0] = 1 / np.sqrt(2)
        energy = objective(improved)
        return SimpleNamespace(
            x=improved,
            fun=energy,
            success=True,
            status=0,
            message="ok",
            nfev=1,
            nit=2,
        )

    monkeypatch.setattr(
        vqe_solver, "_build_initial_point_candidates", fake_build_initial_point_candidates
    )
    monkeypatch.setattr(vqe_solver, "_select_initial_point", fake_select_initial_point)
    monkeypatch.setattr(vqe_solver, "_evaluate_energy", fake_evaluate_energy)
    monkeypatch.setattr(vqe_solver, "minimize", fake_minimize)

    result = run_vqe(
        hamiltonian=hamiltonian,
        backend=backend,
        config={
            "algorithm": "vqe",
            "max_iterations": 4,
            "optimizer_name": "L_BFGS_B",
            "ansatz_name": "EfficientSU2",
            "initial_point_strategy": "zero_plus_seeded_random",
            "initial_point_candidates": 2,
        },
    )

    assert len(calls) == 2
    assert np.allclose(calls[0], 0.0)
    assert np.allclose(calls[1], 2.0)
    assert result.primary_energy == pytest.approx(-0.25)
    assert result.converged is True
    assert result.optimizer_diagnostics["warm_start_retry_reason"] == "stationary_zero_candidate"
    assert result.optimizer_diagnostics["warm_start_retry_attempted_indices"] == [1]
    assert result.optimizer_diagnostics["warm_start_retry_selected_index"] == 1
    assert result.optimizer_diagnostics["optimizer_iterations"] == 2


def test_run_vqe_clips_explicit_initial_point_to_parameter_bounds(monkeypatch) -> None:
    backend = _FakeEstimator()
    hamiltonian = SparsePauliOp.from_list([("Z", 1.0)])
    selected_x0: list[np.ndarray] = []

    def fake_minimize(objective, x0, method, options, bounds):
        del method, options, bounds
        selected_x0.append(np.asarray(x0, dtype=float))
        energy = objective(np.asarray(x0, dtype=float))
        return SimpleNamespace(
            x=np.asarray(x0, dtype=float),
            fun=energy,
            success=True,
            status=0,
            message="ok",
            nfev=1,
            nit=1,
        )

    monkeypatch.setattr(vqe_solver, "minimize", fake_minimize)

    result = run_vqe(
        hamiltonian=hamiltonian,
        backend=backend,
        config={
            "algorithm": "vqe",
            "max_iterations": 2,
            "optimizer_name": "COBYLA",
            "ansatz_name": "EfficientSU2",
            "initial_parameters": [1.2, -1.5, 0.4, -0.6, 0.8, -0.9],
            "parameter_bounds": [
                [-0.1, 0.1],
                [-0.2, 0.2],
                [-0.3, 0.3],
                [-0.4, 0.4],
                [-0.5, 0.5],
                [-0.6, 0.6],
            ],
        },
    )

    assert selected_x0
    assert selected_x0[0] == pytest.approx([0.1, -0.2, 0.3, -0.4, 0.5, -0.6])
    assert result.optimal_parameters == pytest.approx([0.1, -0.2, 0.3, -0.4, 0.5, -0.6])
    assert result.primary_energy == pytest.approx(0.91)


def test_run_vqe_rejects_malformed_initial_parameters() -> None:
    backend = _FakeEstimator()
    hamiltonian = SparsePauliOp.from_list([("Z", 1.0)])

    with pytest.raises(ValueError, match="initial_parameters must contain exactly"):
        run_vqe(
            hamiltonian=hamiltonian,
            backend=backend,
            config={
                "algorithm": "vqe",
                "max_iterations": 2,
                "optimizer_name": "COBYLA",
                "ansatz_name": "EfficientSU2",
                "initial_parameters": [0.1],
            },
        )


def test_run_vqe_rejects_malformed_parameter_bounds() -> None:
    backend = _FakeEstimator()
    hamiltonian = SparsePauliOp.from_list([("Z", 1.0)])

    with pytest.raises(ValueError, match="parameter_bounds lower values cannot exceed upper"):
        run_vqe(
            hamiltonian=hamiltonian,
            backend=backend,
            config={
                "algorithm": "vqe",
                "max_iterations": 2,
                "optimizer_name": "COBYLA",
                "ansatz_name": "EfficientSU2",
                "initial_point_strategy": "zero",
                "parameter_bounds": [
                    [0.2, -0.2],
                    [-0.2, 0.2],
                    [-0.2, 0.2],
                    [-0.2, 0.2],
                    [-0.2, 0.2],
                    [-0.2, 0.2],
                ],
            },
        )


def test_run_vqe_skips_statevector_payload_for_non_statevector_backend_target() -> None:
    backend = _FakeEstimator()
    hamiltonian = SparsePauliOp.from_list([("Z", 1.0)])

    result = run_vqe(
        hamiltonian=hamiltonian,
        backend=backend,
        config={
            "algorithm": "vqe",
            "backend_target": "aer_simulator",
            "advanced_config": {
                "algorithm": "vqe",
                "max_iterations": 2,
                "optimizer_name": "COBYLA",
                "ansatz_name": "EfficientSU2",
                "initial_point": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            },
        },
    )

    assert result.bloch_vectors is None
    assert result.density_matrix_real is None
    assert result.density_matrix_imag is None


def test_run_vqe_reports_objective_evaluation_iteration_units() -> None:
    backend = _FakeEstimator()
    hamiltonian = SparsePauliOp.from_list([("Z", 1.0)])
    progress_events: list[dict[str, object]] = []

    result = run_vqe(
        hamiltonian=hamiltonian,
        backend=backend,
        config={
            "algorithm": "vqe",
            "max_iterations": 2,
            "optimizer_name": "COBYLA",
            "ansatz_name": "EfficientSU2",
            "initial_point_strategy": "zero",
        },
        progress_callback=progress_events.append,
    )

    assert result.optimizer_diagnostics["reported_iterations_unit"] == "objective_evaluations"
    assert progress_events
    assert all(event["iteration_unit"] == "objective_evaluations" for event in progress_events)
    metrics = normalize_result(result)["algorithm_metrics"]
    assert metrics["reported_iterations_unit"] == "objective_evaluations"
