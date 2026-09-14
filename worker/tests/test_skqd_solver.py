from __future__ import annotations

from typing import Any

import numpy as np
import pytest
from qiskit.quantum_info import SparsePauliOp

from worker.adapters.aer_adapter import AerAdapter
from worker.adapters.base import BackendExecutionContext
from worker.adapters.result_adapter import normalize_result
from worker.chemistry.hamiltonian_action import build_hamiltonian_action
from worker.chemistry.skqd_solver import (
    _build_krylov_extension,
    _build_sector_krylov_extension,
    _seed_state_from_sqd_result,
    run_skqd,
)
from worker.chemistry.types import SQDResult

SQD_SEED_ARTIFACT_ID = "sqd.iteration.1.sampler"
RUN_SQD_PATCH_TARGET = "worker.chemistry.skqd_solver.run_sqd"
BUILD_KRYLOV_EXTENSION_PATCH_TARGET = "worker.chemistry.skqd_solver._build_krylov_extension"


def _sector_hamiltonian(*, norb: int = 7, n_alpha: int = 1, n_beta: int = 1) -> Any:
    return type(
        "SectorHamiltonian",
        (),
        {
            "num_spatial_orbitals": norb,
            "num_qubits": 2 * norb,
            "num_electrons_alpha": n_alpha,
            "num_electrons_beta": n_beta,
            "one_body_tensor": np.diag(np.linspace(-1.0, 0.5, norb)),
            "two_body_tensor": np.zeros((norb, norb, norb, norb), dtype=float),
            "constant": -0.25,
        },
    )()


def test_run_skqd_uses_shared_config_and_emits_canonical_progress(
    monkeypatch: Any,
    mock_hamiltonian_bundle: object,
    capture_progress: tuple[list[dict[str, Any]], Any],
) -> None:
    events, progress_callback = capture_progress

    def _fake_run_sqd(**kwargs: Any) -> SQDResult:
        callback = kwargs.get("progress_callback")
        if callback is not None:
            callback(
                {
                    "algorithm": "sqd",
                    "iteration": 1,
                    "completed_iterations": 1,
                    "energy": -0.9,
                    "stage": "completed",
                }
            )
        return SQDResult(
            algorithm="sqd",
            primary_energy=-0.9,
            primary_iterations=1,
            converged=True,
            sci_energies=[-0.9],
            configuration_recovery_trace=[],
            spin_diagnostics={},
            sci_result_package={"final_occupancies": [1.0, 0.0]},
            circuit_artifacts=[
                {
                    "schema_version": "2.0",
                    "artifact_type": "quantum_circuit",
                    "id": SQD_SEED_ARTIFACT_ID,
                    "artifact_id": SQD_SEED_ARTIFACT_ID,
                    "algorithm": "sqd",
                    "role": "sqd_sampling",
                    "label": "SQD seed",
                    "representative": True,
                }
            ],
            circuit_artifact_policy={"name": "all_or_windowed_sqd_iterations"},
        )

    monkeypatch.setattr(RUN_SQD_PATCH_TARGET, _fake_run_sqd)

    result = run_skqd(
        hamiltonian=mock_hamiltonian_bundle,
        backend=object(),
        config={
            "algorithm": "skqd",
            "krylov_extension_dim": 32,
            "advanced_config": {
                "algorithm": "skqd",
                "krylov_extension_dim": 2,
                "sampling_mode": "legacy_statevector_extension",
                "base_sampling_options": {"max_iterations": 1},
            },
        },
        progress_callback=progress_callback,
    )

    skqd_events = [event for event in events if event["algorithm"] == "skqd"]
    assert result.algorithm == "skqd"
    assert result.primary_iterations == 3
    assert skqd_events
    assert all("iteration" in event for event in skqd_events)
    assert all("completed_iterations" in event for event in skqd_events)
    assert all("energy" in event for event in skqd_events)
    assert all(event["energy"] is not None for event in skqd_events)
    assert skqd_events[-1]["stage"] == "completed"
    assert skqd_events[-1]["iteration"] == result.krylov_extension_diagnostics["basis_rank"]
    assert skqd_events[-1]["overall_iterations"] == result.primary_iterations
    metrics = normalize_result(result)["algorithm_metrics"]
    assert metrics["circuit_artifact_policy"]["name"] == "all_or_windowed_sqd_iterations"
    assert len(metrics["circuit_artifacts"]) == 1
    assert metrics["circuit_artifacts"][0]["algorithm"] == "skqd"
    assert metrics["circuit_artifacts"][0]["role"] == "sqd_seed"
    assert metrics["circuit_artifacts"][0]["source"] == "sqd_seed"
    assert metrics["circuit_artifacts"][0]["parent_artifact_id"] == SQD_SEED_ARTIFACT_ID
    assert metrics["circuit_artifacts"][0]["representative"] is True


def test_run_skqd_defaults_to_sample_union_selected_ci(
    monkeypatch: Any,
    mock_hamiltonian_bundle: object,
) -> None:
    monkeypatch.setattr(
        RUN_SQD_PATCH_TARGET,
        lambda **_kwargs: pytest.fail("direct sample-union SKQD must not run SQD first"),
    )

    result = run_skqd(
        hamiltonian=mock_hamiltonian_bundle,
        backend=object(),
        config={
            "algorithm": "skqd",
            "krylov_extension_dim": 2,
            "samples_per_state": 4,
            "base_sampling_options": {"max_iterations": 1, "max_dim": "full"},
        },
    )

    diagnostics = result.krylov_extension_diagnostics
    assert diagnostics["algorithm_variant"] == "skqd_sample_union"
    assert diagnostics["sampling_mode"] == "sample_union_exact"
    assert diagnostics["sampling_source"] == "exact_statevector_oracle"
    assert diagnostics["requested_sampling_mode"] == "sample_union_exact"
    assert diagnostics["execution_path"] == "analysis_only_exact_statevector_oracle"
    assert diagnostics["execution_provenance"] == {
        "requested_sampling_mode": "sample_union_exact",
        "actual_sampling_mode": "sample_union_exact",
        "execution_path": "analysis_only_exact_statevector_oracle",
        "comparison_scope": "analysis_only",
        "hardware_sampling_capable": False,
        "backend_target": None,
    }
    assert diagnostics["selected_solution"] == "skqd_sample_union"
    assert diagnostics["sample_union"]["sampled_krylov_states"] == 2
    assert diagnostics["sample_union"]["solve_type"] == "ordinary_selected_ci"
    assert diagnostics["sample_union"]["configuration_recovery_policy"] == "postselect_only"
    assert diagnostics["sample_provenance"]
    assert diagnostics["reference_descriptor"]["reference_source"] == "hartree_fock"
    assert diagnostics["reference_descriptor"]["state_fingerprint"]
    assert diagnostics["sqd_core_status"] == "not_run"
    assert diagnostics["sqd_iterations"] == 0
    # The compact mock spans its full CI sector, so the sample-union path now
    # reports a genuine convergence verdict instead of a hardcoded False.
    assert diagnostics["selected_solution_converged"] is True
    assert diagnostics["convergence_status"] in {
        "full_sector_recovered",
        "subspace_saturated",
    }
    assert diagnostics["convergence_verdict"]["converged"] is True
    assert diagnostics["sample_union"]["sampled_union_determinants"] > 0
    assert len(diagnostics["krylov_prefix_summaries"]) == 2
    assert diagnostics["krylov_prefix_summaries"][-1]["sample_count"] == 8
    assert result.primary_iterations == 2
    assert result.converged is True


def test_run_skqd_aer_samples_each_krylov_circuit() -> None:
    hamiltonian = type(
        "SamplerHamiltonian",
        (),
        {
            "num_spatial_orbitals": 1,
            "num_qubits": 2,
            "num_electrons_alpha": 1,
            "num_electrons_beta": 0,
            "one_body_tensor": np.asarray([[0.3]]),
            "two_body_tensor": np.zeros((1, 1, 1, 1)),
            "constant": 0.0,
            "pauli_hamiltonian": SparsePauliOp.from_list([("ZI", 0.3), ("IZ", 0.2)]),
        },
    )()
    context = BackendExecutionContext(
        backend_target="aer_simulator",
        simulator_method="statevector",
        shots=32,
    )
    sampler = AerAdapter().create_sampler(context)

    result = run_skqd(
        hamiltonian=hamiltonian,
        backend=sampler,
        config={
            "algorithm": "skqd",
            "samples_per_state": 8,
            "base_sampling_options": {
                "max_dim": "full",
            },
            "krylov_extension_dim": 2,
        },
        backend_context=context,
    )

    diagnostics = result.krylov_extension_diagnostics
    assert diagnostics["sampling_mode"] == "sample_union_sampler"
    assert diagnostics["sampling_source"] == "sampler_krylov_circuits"
    assert diagnostics["requested_sampling_mode"] == "sample_union_exact"
    assert diagnostics["execution_path"] == "sampler_krylov_union"
    assert diagnostics["execution_provenance"] == {
        "requested_sampling_mode": "sample_union_exact",
        "actual_sampling_mode": "sample_union_sampler",
        "execution_path": "sampler_krylov_union",
        "comparison_scope": "sampler_krylov_union",
        "hardware_sampling_capable": True,
        "backend_target": "aer_simulator",
    }
    assert diagnostics["sample_count"] == 16
    assert len(diagnostics["krylov_prefix_summaries"]) == 2
    assert diagnostics["krylov_prefix_summaries"][-1]["sample_count"] == 16
    assert diagnostics["sample_union"]["sampled_krylov_states"] == 2
    assert len(diagnostics["krylov_circuit_metadata"]) == 2


def test_run_skqd_does_not_degrade_below_sqd_core_energy(
    monkeypatch: Any,
    mock_hamiltonian_bundle: object,
    capture_progress: tuple[list[dict[str, Any]], Any],
) -> None:
    events, progress_callback = capture_progress

    def _fake_run_sqd(**kwargs: Any) -> SQDResult:
        callback = kwargs.get("progress_callback")
        if callback is not None:
            callback({"algorithm": "sqd", "iteration": 1, "energy": -1.0})
        return SQDResult(
            algorithm="sqd",
            primary_energy=-1.0,
            primary_iterations=1,
            converged=True,
            sci_energies=[-1.0],
            configuration_recovery_trace=[],
            spin_diagnostics={},
            sci_result_package={"final_occupancies": [1.0, 0.0], "nelec": [1, 0]},
        )

    def _fake_krylov_extension(
        *args: Any, **kwargs: Any
    ) -> tuple[list[float], int, dict[str, Any], Any]:
        del args, kwargs
        return (
            [-0.8],
            1,
            {"relative_ritz_residual": 1.0, "ritz_residual_norm": 1.0},
            np.array([1.0, 0.0, 0.0, 0.0], dtype=complex),
        )

    monkeypatch.setattr(RUN_SQD_PATCH_TARGET, _fake_run_sqd)
    monkeypatch.setattr(
        BUILD_KRYLOV_EXTENSION_PATCH_TARGET,
        _fake_krylov_extension,
    )

    result = run_skqd(
        hamiltonian=mock_hamiltonian_bundle,
        backend=object(),
        config={
            "algorithm": "skqd",
            "advanced_config": {
                "algorithm": "skqd",
                "krylov_extension_dim": 2,
                "sampling_mode": "legacy_statevector_extension",
                "base_sampling_options": {"max_iterations": 1},
            },
        },
        progress_callback=progress_callback,
    )

    assert result.primary_energy == pytest.approx(-1.0)
    assert result.converged is True
    assert result.krylov_extension_diagnostics["selected_solution"] == "sqd_core"
    assert result.krylov_extension_diagnostics["extension_energy"] == pytest.approx(-0.8)
    assert result.krylov_extension_diagnostics["extension_attempted"] is True
    assert result.krylov_extension_diagnostics["extension_status"] == "completed"
    assert result.krylov_extension_diagnostics["extension_cost"]["basis_rank"] == 1
    assert events[-1]["energy"] == pytest.approx(-1.0)


def test_run_skqd_preserves_core_when_extension_fails(
    monkeypatch: Any,
    mock_hamiltonian_bundle: object,
) -> None:
    def _fake_run_sqd(**kwargs: Any) -> SQDResult:
        del kwargs
        return SQDResult(
            algorithm="sqd",
            primary_energy=-1.0,
            primary_iterations=1,
            converged=True,
            sci_energies=[-1.0],
            configuration_recovery_trace=[],
            spin_diagnostics={},
            sci_result_package={"final_occupancies": [1.0, 0.0], "nelec": [1, 0]},
        )

    def _fail_krylov_extension(*args: Any, **kwargs: Any) -> None:
        del args, kwargs
        raise RuntimeError("synthetic extension failure")

    monkeypatch.setattr(RUN_SQD_PATCH_TARGET, _fake_run_sqd)
    monkeypatch.setattr(BUILD_KRYLOV_EXTENSION_PATCH_TARGET, _fail_krylov_extension)

    result = run_skqd(
        hamiltonian=mock_hamiltonian_bundle,
        backend=object(),
        config={
            "algorithm": "skqd",
            "advanced_config": {
                "algorithm": "skqd",
                "krylov_extension_dim": 2,
                "sampling_mode": "legacy_statevector_extension",
                "base_sampling_options": {"max_iterations": 1},
            },
        },
    )

    assert result.primary_energy == pytest.approx(-1.0)
    assert result.converged is True
    diagnostics = result.krylov_extension_diagnostics
    assert diagnostics["selected_solution"] == "sqd_core"
    assert diagnostics["extension_attempted"] is True
    assert diagnostics["extension_status"] == "failed"
    assert diagnostics["extension_failure_reason"] == "RuntimeError: synthetic extension failure"
    assert diagnostics["extension_energy"] is None
    assert diagnostics["extension_improved_sqd"] is None
    assert diagnostics["extension_cost"]["wall_time_seconds"] >= 0.0


def test_seed_state_from_sqd_result_preserves_electron_count() -> None:
    sqd_result = SQDResult(
        algorithm="sqd",
        primary_energy=-1.0,
        primary_iterations=1,
        converged=True,
        sci_energies=[-1.0],
        configuration_recovery_trace=[],
        spin_diagnostics={},
        sci_result_package={
            "final_occupancies": [0.9, 0.8, 0.7, 0.6, 0.95, 0.85, 0.75, 0.65],
            "nelec": [2, 2],
        },
    )

    state = _seed_state_from_sqd_result(sqd_result, target_size=2**8)

    assert state is not None
    basis_index = int(np.argmax(np.abs(state)))
    occupied_qubits = [qubit for qubit in range(8) if basis_index & (1 << qubit)]
    assert occupied_qubits == [0, 1, 4, 5]


def test_seed_state_from_sqd_result_uses_sector_correct_bitstring_probabilities() -> None:
    sqd_result = SQDResult(
        algorithm="sqd",
        primary_energy=-1.0,
        primary_iterations=1,
        converged=True,
        sci_energies=[-1.0],
        configuration_recovery_trace=[],
        spin_diagnostics={},
        sci_result_package={
            "final_occupancies": [0.6, 0.4, 0.7, 0.3],
            "nelec": [1, 1],
            "final_bitstring_probabilities": [
                {"bitstring": "1111", "probability": 0.9},
                {"bitstring": "0101", "probability": 0.25},
                {"bitstring": "1010", "probability": 0.75},
            ],
        },
    )

    state = _seed_state_from_sqd_result(sqd_result, target_size=2**4)

    assert state is not None
    assert state[15] == pytest.approx(0.0)
    assert abs(state[5]) ** 2 == pytest.approx(0.25)
    assert abs(state[10]) ** 2 == pytest.approx(0.75)


def test_krylov_extension_reports_energy_from_orthonormal_basis() -> None:
    operator = np.diag(
        [-1.0 + index * 1e-12 if index < 8 else -1.0 + 0.25 * (index - 7) for index in range(16)]
    ).astype(complex)
    seed_state = np.ones(16, dtype=complex) / 4.0

    ritz_values, basis_rank, diagnostics, ground_state = _build_krylov_extension(
        operator,
        seed_state=seed_state,
        seeded_from_sqd=True,
        target_rank=12,
        time_step=0.2,
        residual_tolerance=1e-6,
        progress_callback=None,
    )

    assert basis_rank == diagnostics["basis_numerical_rank"]
    assert ritz_values[0] == pytest.approx(diagnostics["ritz_energy"])
    assert ritz_values[0] >= float(np.min(np.diag(operator).real)) - 1e-9
    assert ground_state is not None


def test_sector_krylov_matches_dense_sector_matrix() -> None:
    hamiltonian = _sector_hamiltonian(norb=4, n_alpha=2, n_beta=2)
    action = build_hamiltonian_action(hamiltonian)
    seed_state = np.ones(action.dimension, dtype=complex) / np.sqrt(action.dimension)
    dense_operator = np.column_stack(
        [
            action.matvec(np.eye(action.dimension, dtype=complex)[:, index])
            for index in range(action.dimension)
        ]
    )

    dense_values, dense_rank, _, _ = _build_krylov_extension(
        dense_operator,
        seed_state=seed_state,
        seeded_from_sqd=True,
        target_rank=4,
        time_step=0.2,
        residual_tolerance=1e-8,
        progress_callback=None,
    )
    sector_values, sector_rank, _, _ = _build_sector_krylov_extension(
        action,
        seed_state=seed_state,
        seeded_from_sqd=True,
        target_rank=4,
        time_step=0.2,
        residual_tolerance=1e-8,
        progress_callback=None,
    )

    assert sector_rank == dense_rank
    assert sector_values[:sector_rank] == pytest.approx(dense_values[:dense_rank])


def test_run_skqd_sector_path_does_not_materialize_dense_matrix(monkeypatch: Any) -> None:
    def _fake_run_sqd(**kwargs: Any) -> SQDResult:
        del kwargs
        return SQDResult(
            algorithm="sqd",
            primary_energy=-1.0,
            primary_iterations=1,
            converged=True,
            sci_energies=[-1.0],
            configuration_recovery_trace=[],
            spin_diagnostics={},
            sci_result_package={"final_occupancies": [], "nelec": [1, 1]},
        )

    def _fail_dense_resolution(*args: Any, **kwargs: Any) -> np.ndarray:
        del args, kwargs
        raise AssertionError("SKQD sector path should not resolve a dense matrix")

    monkeypatch.setattr(RUN_SQD_PATCH_TARGET, _fake_run_sqd)
    monkeypatch.setattr(
        "worker.chemistry.skqd_solver.resolve_operator_matrix",
        _fail_dense_resolution,
    )

    result = run_skqd(
        hamiltonian=_sector_hamiltonian(),
        backend=object(),
        config={
            "algorithm": "skqd",
            "krylov_extension_dim": 3,
            "residual_tolerance": 1e-8,
            "sampling_mode": "legacy_statevector_extension",
        },
    )

    diagnostics = result.krylov_extension_diagnostics
    assert result.algorithm == "skqd"
    assert diagnostics["execution_mode"] == "sector_matrix_free"
    assert diagnostics["operator_dimension"] == pytest.approx(49.0)
    assert "krylov_state_bitstring_distribution" in diagnostics


def test_run_skqd_convergence_reflects_krylov_extension(monkeypatch: Any) -> None:
    def _fake_run_sqd(**kwargs: Any) -> SQDResult:
        del kwargs
        return SQDResult(
            algorithm="sqd",
            primary_energy=-0.9,
            primary_iterations=1,
            converged=True,
            sci_energies=[-0.9],
            configuration_recovery_trace=[],
            spin_diagnostics={},
            sci_result_package={
                "final_occupancies": [1.0, 0.0],
                "nelec": [1, 0],
                "final_bitstring_probabilities": [{"bitstring": "01", "probability": 1.0}],
            },
        )

    def _fake_krylov_extension(*args: Any, **kwargs: Any):
        del args
        del kwargs
        return (
            np.array([-1.2]),
            2,
            {
                "relative_ritz_residual": 1e-2,
                "ritz_residual_norm": 1e-2,
                "residual_convergence_threshold": 1e-6,
                "basis_numerical_rank": 2.0,
            },
            None,
        )

    monkeypatch.setattr(RUN_SQD_PATCH_TARGET, _fake_run_sqd)
    monkeypatch.setattr(
        BUILD_KRYLOV_EXTENSION_PATCH_TARGET,
        _fake_krylov_extension,
    )
    hamiltonian = type(
        "Hamiltonian",
        (),
        {"dense_operator_matrix": np.diag([-1.0, -0.5, 0.0, 0.5]).astype(complex)},
    )()

    result = run_skqd(
        hamiltonian=hamiltonian,
        backend=object(),
        config={
            "algorithm": "skqd",
            "krylov_extension_dim": 2,
            "time_step": 0.4,
            "residual_tolerance": 1e-6,
            "sampling_mode": "legacy_statevector_extension",
        },
    )

    assert result.primary_energy == pytest.approx(-0.9)
    assert result.converged is True
    assert result.krylov_extension_diagnostics["krylov_converged"] is False
    assert result.krylov_extension_diagnostics["sqd_converged"] is True
    assert result.krylov_extension_diagnostics["overall_converged"] is False
    assert result.krylov_extension_diagnostics["selected_solution"] == "sqd_core"
    assert result.krylov_extension_diagnostics["time_step"] == pytest.approx(0.4)
    assert result.krylov_extension_diagnostics["time_evolved_sampling_time_step"] == pytest.approx(
        0.4
    )
    assert result.krylov_extension_diagnostics["time_evolved_bitstring_distribution"]


def test_run_skqd_convergence_requires_sqd_core_even_when_krylov_converges(
    monkeypatch: Any,
) -> None:
    def _fake_run_sqd(**kwargs: Any) -> SQDResult:
        del kwargs
        return SQDResult(
            algorithm="sqd",
            primary_energy=-0.9,
            primary_iterations=1,
            converged=False,
            sci_energies=[-0.9],
            configuration_recovery_trace=[],
            spin_diagnostics={},
            sci_result_package={
                "final_occupancies": [1.0, 0.0],
                "nelec": [1, 0],
                "final_bitstring_probabilities": [{"bitstring": "01", "probability": 1.0}],
            },
        )

    def _fake_krylov_extension(*args: Any, **kwargs: Any):
        del args
        del kwargs
        return (
            np.array([-1.2]),
            2,
            {
                "relative_ritz_residual": 1e-8,
                "ritz_residual_norm": 1e-8,
                "residual_convergence_threshold": 1e-6,
                "basis_numerical_rank": 2.0,
            },
            None,
        )

    monkeypatch.setattr(RUN_SQD_PATCH_TARGET, _fake_run_sqd)
    monkeypatch.setattr(
        BUILD_KRYLOV_EXTENSION_PATCH_TARGET,
        _fake_krylov_extension,
    )
    hamiltonian = type(
        "Hamiltonian",
        (),
        {"dense_operator_matrix": np.diag([-1.0, -0.5, 0.0, 0.5]).astype(complex)},
    )()

    result = run_skqd(
        hamiltonian=hamiltonian,
        backend=object(),
        config={
            "algorithm": "skqd",
            "krylov_extension_dim": 2,
            "residual_tolerance": 1e-6,
            "sampling_mode": "legacy_statevector_extension",
        },
    )

    assert result.converged is False
    assert result.krylov_extension_diagnostics["krylov_converged"] is True
    assert result.krylov_extension_diagnostics["sqd_converged"] is False
    assert result.krylov_extension_diagnostics["overall_converged"] is False


def test_krylov_extension_time_step_changes_dense_projected_spectrum() -> None:
    operator = np.array(
        [
            [0.0, 1.0, 0.0],
            [1.0, 0.0, 1.0],
            [0.0, 1.0, 2.0],
        ],
        dtype=complex,
    )
    seed_state = np.array([1.0, 0.0, 0.0], dtype=complex)

    fast_values, _, _, _ = _build_krylov_extension(
        operator,
        seed_state=seed_state,
        seeded_from_sqd=True,
        target_rank=2,
        time_step=0.1,
        residual_tolerance=1e-8,
        progress_callback=None,
    )
    slow_values, _, _, _ = _build_krylov_extension(
        operator,
        seed_state=seed_state,
        seeded_from_sqd=True,
        target_rank=2,
        time_step=1.0,
        residual_tolerance=1e-8,
        progress_callback=None,
    )

    assert fast_values[0] != pytest.approx(slow_values[0])
