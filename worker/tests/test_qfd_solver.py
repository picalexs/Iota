from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from qiskit.primitives import StatevectorEstimator
from qiskit.quantum_info import SparsePauliOp

from worker.adapters.base import BackendExecutionContext
from worker.chemistry.algorithms.qfd import workflow as qfd_solver
from worker.chemistry.algorithms.qfd.definition import ALGORITHM_DEFINITION
from worker.chemistry.eigensolver import StabilizedGeneralizedEigenproblemResult
from worker.chemistry.projected_subspace import projected_matrix_converged
from worker.jobs.dispatcher import dispatch_algorithm


def _single_qubit_x_hamiltonian() -> SimpleNamespace:
    return SimpleNamespace(
        pauli_hamiltonian=SparsePauliOp.from_list([("X", 1.0)]),
        num_qubits=1,
    )


def _large_pauli_z_hamiltonian(num_qubits: int = 13) -> SimpleNamespace:
    return SimpleNamespace(
        pauli_hamiltonian=SparsePauliOp.from_list([("Z" + "I" * (num_qubits - 1), 1.0)]),
        num_qubits=num_qubits,
    )


def _sector_hamiltonian(*, norb: int = 7, n_alpha: int = 1, n_beta: int = 1) -> SimpleNamespace:
    one_body = np.diag(np.linspace(-1.0, 0.5, norb))
    one_body[0, 1] = one_body[1, 0] = 0.07
    if norb > 2:
        one_body[1, 2] = one_body[2, 1] = -0.04
    return SimpleNamespace(
        num_spatial_orbitals=norb,
        num_qubits=2 * norb,
        num_electrons_alpha=n_alpha,
        num_electrons_beta=n_beta,
        one_body_tensor=one_body,
        two_body_tensor=np.zeros((norb, norb, norb, norb), dtype=float),
        constant=-0.25,
    )


def test_run_qfd_precomputes_exact_time_evolution_spectrum_once(monkeypatch) -> None:
    operator = np.array([[1.0, 0.2], [0.2, 0.8]], dtype=complex)
    reference_state = np.array([1.0, 0.0], dtype=complex)
    eigenvalues = np.array([0.7, 1.1], dtype=float)
    eigenvectors = np.eye(2, dtype=complex)

    prepare_calls: list[np.ndarray] = []
    evolution_calls: list[float] = []

    def prepare_exact_time_evolution(matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        prepare_calls.append(matrix)
        return eigenvalues, eigenvectors

    def exact_time_evolution_state_from_spectrum(
        _eigvals,
        _eigvecs,
        _state,
        *,
        time_step,
        state_projection=None,
    ) -> np.ndarray:
        del state_projection
        evolution_calls.append(time_step)
        return np.array([np.cos(time_step), np.sin(time_step)], dtype=complex)

    monkeypatch.setattr(qfd_solver, "resolve_operator_matrix", lambda _hamiltonian: operator)
    monkeypatch.setattr(
        qfd_solver, "build_hf_reference_state", lambda _hamiltonian, **_kw: reference_state
    )
    monkeypatch.setattr(
        qfd_solver,
        "prepare_exact_time_evolution",
        prepare_exact_time_evolution,
    )
    monkeypatch.setattr(
        qfd_solver,
        "exact_time_evolution_state_from_spectrum",
        exact_time_evolution_state_from_spectrum,
    )
    monkeypatch.setattr(
        qfd_solver,
        "build_time_grid",
        lambda *, num_time_points, max_time, grid_type: np.array([0.0, 0.25, 0.5]),
    )
    monkeypatch.setattr(
        qfd_solver,
        "build_overlap_matrix",
        lambda states: np.eye(len(states), dtype=complex),
    )
    monkeypatch.setattr(
        qfd_solver,
        "overlap_metrics",
        lambda overlap: {
            "overlap_condition": 1.0,
            "overlap_min_eigenvalue": 1.0,
            "overlap_max_eigenvalue": 1.0,
        },
    )
    monkeypatch.setattr(
        qfd_solver,
        "solve_exact_generalized_eigenproblem",
        lambda projected_hamiltonian, overlap: (
            np.array([0.1, 0.2, 0.3], dtype=float),
            {
                "overlap_condition": 1.0,
                "overlap_min_eigenvalue": 1.0,
                "stability_state": "stable",
                "regularization": 1e-8,
            },
        ),
    )

    result = qfd_solver.run_qfd(
        hamiltonian=object(),
        backend=object(),
        config={
            "algorithm": "qfd",
            "advanced_config": {
                "algorithm": "qfd",
                "num_time_points": 3,
                "max_time": 0.5,
                "time_grid_type": "linear",
            },
        },
    )

    assert result.algorithm == "qfd"
    assert result.primary_iterations == 3
    assert prepare_calls == [operator]
    assert evolution_calls == [0.25, 0.5]


def test_run_qfd_original_symmetric_persists_grid_provenance() -> None:
    result = qfd_solver.run_qfd(
        hamiltonian=_single_qubit_x_hamiltonian(),
        backend=None,
        config={
            "algorithm": "qfd",
            "advanced_config": {
                "algorithm": "qfd",
                "qfd_variant": "qfd_original_symmetric",
                "num_time_points": 3,
                "max_time": 1.0,
                "time_grid_type": "linear",
                "kappa": 2.1,
            },
        },
    )

    assert result.conditioning_summary["qfd_variant"] == "qfd_original_symmetric"
    assert result.conditioning_summary["kappa"] == pytest.approx(2.1)
    assert result.conditioning_summary["time_grid_values"] == pytest.approx(
        [-2.0 * np.pi / 2.1, 0.0, 2.0 * np.pi / 2.1]
    )
    assert result.conditioning_summary["spectral_width_bound"] == pytest.approx(2.0)
    assert result.conditioning_summary["kappa_safety_margin"] == pytest.approx(0.02)
    assert result.conditioning_summary["kappa_source"] == "user_supplied"
    assert len(result.conditioning_summary["time_grid_hash"]) == 64
    assert result.stability_summary["termination_reason"] in {
        "converged",
        "residual_tolerance_not_met",
        "projected_metric_rank_reduced",
        "projected_metric_not_positive_definite",
        "projected_metric_unstable",
    }


def test_run_qfd_original_symmetric_derives_kappa_from_exact_spectrum() -> None:
    result = qfd_solver.run_qfd(
        hamiltonian=_single_qubit_x_hamiltonian(),
        backend=None,
        config={
            "algorithm": "qfd",
            "advanced_config": {
                "algorithm": "qfd",
                "qfd_variant": "qfd_original_symmetric",
                "num_time_points": 3,
            },
        },
    )

    assert result.conditioning_summary["spectral_width_bound"] == pytest.approx(2.0)
    assert result.conditioning_summary["kappa"] == pytest.approx(2.02)
    assert result.conditioning_summary["kappa_source"] == "automatic_exact_dense_spectrum"
    assert result.conditioning_summary["time_grid_values"] != pytest.approx(
        [-2.0 * np.pi, 0.0, 2.0 * np.pi]
    )


def test_run_qfd_original_symmetric_uses_conservative_pauli_bound_on_branch_path() -> None:
    result = qfd_solver.run_qfd(
        hamiltonian=_single_qubit_x_hamiltonian(),
        backend=StatevectorEstimator(),
        config={
            "algorithm": "qfd",
            "advanced_config": {
                "algorithm": "qfd",
                "qfd_variant": "qfd_original_symmetric",
                "num_time_points": 3,
            },
        },
        backend_context=BackendExecutionContext(backend_target="ibm_runtime"),
    )

    assert result.matrix_element_summary["matrix_element_strategy"] == "branch_estimator"
    assert result.conditioning_summary["spectral_width_bound"] == pytest.approx(2.0)
    assert result.conditioning_summary["kappa"] == pytest.approx(2.02)
    assert result.conditioning_summary["kappa_source"] == (
        "automatic_pauli_l1_conservative_bound"
    )


def test_run_qfd_original_symmetric_rejects_undersized_kappa() -> None:
    with pytest.raises(ValueError, match="spectral-width bound plus overage"):
        qfd_solver.run_qfd(
            hamiltonian=_single_qubit_x_hamiltonian(),
            backend=None,
            config={
                "algorithm": "qfd",
                "advanced_config": {
                    "algorithm": "qfd",
                    "qfd_variant": "qfd_original_symmetric",
                    "num_time_points": 3,
                    "kappa": 2.0,
                },
            },
        )


def test_qfd_sector_states_match_dense_sector_matrix() -> None:
    hamiltonian = _sector_hamiltonian(norb=4, n_alpha=1, n_beta=1)
    action = qfd_solver.build_hamiltonian_action(hamiltonian)
    reference = qfd_solver.hartree_fock_sector_state(action.norb, action.nelec)
    dense_operator = np.column_stack(
        [
            action.matvec(np.eye(action.dimension, dtype=complex)[:, index])
            for index in range(action.dimension)
        ]
    )
    time_grid = qfd_solver.build_time_grid(
        num_time_points=3,
        max_time=0.4,
        grid_type="linear",
    )
    eigenvalues, eigenvectors = qfd_solver.prepare_exact_time_evolution(dense_operator)
    reference_projection = eigenvectors.conj().T @ reference
    dense_states = [
        reference
        if np.isclose(time_point, 0.0)
        else qfd_solver.exact_time_evolution_state_from_spectrum(
            eigenvalues,
            eigenvectors,
            reference,
            time_step=float(time_point),
            state_projection=reference_projection,
        )
        for time_point in time_grid
    ]
    sector_states = qfd_solver._build_sector_qfd_states(
        action,
        reference,
        time_grid,
        max_time=0.4,
        time_grid_type="linear",
        progress_callback=None,
    )
    dense_matrix = np.column_stack(dense_states)
    sector_matrix = np.column_stack(sector_states)
    dense_values, _ = qfd_solver.solve_generalized_eigenproblem(
        dense_matrix.conj().T @ dense_operator @ dense_matrix,
        qfd_solver.build_overlap_matrix(dense_states),
    )
    sector_values, _ = qfd_solver.solve_generalized_eigenproblem(
        action.project(sector_matrix),
        qfd_solver.build_overlap_matrix(sector_states),
    )

    assert sector_values[:3] == pytest.approx(dense_values[:3], abs=1e-8)


def test_run_qfd_sector_path_does_not_materialize_dense_matrix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail_dense_resolution(*args, **kwargs):
        del args, kwargs
        raise AssertionError("QFD sector path should not resolve a dense matrix")

    monkeypatch.setattr(qfd_solver, "resolve_operator_matrix", _fail_dense_resolution)

    result = qfd_solver.run_qfd(
        hamiltonian=_sector_hamiltonian(),
        backend=None,
        config={
            "algorithm": "qfd",
            "advanced_config": {
                "algorithm": "qfd",
                "num_time_points": 3,
                "max_time": 0.4,
                "time_grid_type": "linear",
                "residual_tolerance": 1e-8,
            },
        },
    )

    assert result.algorithm == "qfd"
    assert result.primary_energy is not None
    assert result.matrix_element_summary["matrix_element_strategy"] == "sector_matrix_free"
    assert (
        result.matrix_element_summary["execution_selection_reason"]
        == "large_noiseless_problem_uses_sector_matrix_free_action"
    )
    assert result.matrix_element_summary["projected_dimension"] == 3
    assert result.matrix_element_summary["projected_matrix_element_count"] == 18
    assert result.matrix_element_summary["timing_breakdown"]["total_seconds"] >= 0.0
    assert result.conditioning_summary["sector_dimension"] == pytest.approx(49.0)


def test_dispatch_qfd_does_not_create_unused_estimator(
    mock_backend_adapter,
    mock_hamiltonian_bundle,
) -> None:
    result = dispatch_algorithm(
        algorithm="qfd",
        backend=mock_backend_adapter,
        config_snapshot={"algorithm": "qfd", "num_time_points": 2},
        hamiltonian_bundle=mock_hamiltonian_bundle,
    )

    assert result.algorithm == "qfd"
    assert mock_backend_adapter.calls == []


def test_run_qfd_passes_residual_tolerance_into_projected_ritz_diagnostics(
    monkeypatch,
) -> None:
    operator = np.array([[1.0, 0.0], [0.0, -1.0]], dtype=complex)
    reference_state = np.array([1.0, 0.0], dtype=complex)
    captured: dict[str, float] = {}

    monkeypatch.setattr(qfd_solver, "resolve_operator_matrix", lambda _hamiltonian: operator)
    monkeypatch.setattr(
        qfd_solver,
        "build_hf_reference_state",
        lambda _hamiltonian, **_kw: reference_state,
    )
    monkeypatch.setattr(
        qfd_solver,
        "prepare_exact_time_evolution",
        lambda matrix: (np.array([-1.0, 1.0], dtype=float), np.eye(matrix.shape[0], dtype=complex)),
    )
    monkeypatch.setattr(
        qfd_solver,
        "exact_time_evolution_state_from_spectrum",
        lambda *_args, **_kwargs: reference_state,
    )
    monkeypatch.setattr(
        qfd_solver,
        "build_time_grid",
        lambda *, num_time_points, max_time, grid_type: np.array([0.0, max_time]),
    )
    monkeypatch.setattr(
        qfd_solver,
        "build_overlap_matrix",
        lambda states: np.eye(len(states), dtype=complex),
    )
    monkeypatch.setattr(
        qfd_solver,
        "overlap_metrics",
        lambda overlap: {
            "overlap_condition": 1.0,
            "overlap_min_eigenvalue": 1.0,
            "overlap_max_eigenvalue": 1.0,
        },
    )
    monkeypatch.setattr(
        qfd_solver,
        "solve_exact_generalized_eigenproblem",
        lambda projected_hamiltonian, overlap: (
            np.array([-1.0, 0.5], dtype=float),
            {
                "overlap_condition": 1.0,
                "overlap_min_eigenvalue": 1.0,
                "stability_state": "stable",
                "regularization": 1e-8,
            },
        ),
    )

    def _capture(operator, basis_matrix, *, residual_tolerance):
        del operator, basis_matrix
        captured["residual_tolerance"] = residual_tolerance
        return {
            "relative_ritz_residual": residual_tolerance / 2.0,
            "ritz_residual_norm": residual_tolerance / 2.0,
            "residual_convergence_threshold": residual_tolerance,
            "basis_numerical_rank": 2.0,
        }

    monkeypatch.setattr(qfd_solver, "projected_ritz_diagnostics", _capture)

    result = qfd_solver.run_qfd(
        hamiltonian=object(),
        backend=object(),
        config={
            "algorithm": "qfd",
            "advanced_config": {
                "algorithm": "qfd",
                "num_time_points": 2,
                "max_time": 0.5,
                "residual_tolerance": 1e-5,
            },
        },
    )

    assert captured["residual_tolerance"] == pytest.approx(1e-5)
    assert result.converged is True


def test_run_qfd_does_not_mark_singular_dense_projection_converged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        qfd_solver,
        "_build_dense_qfd_states",
        lambda **_kwargs: [
            np.array([1.0, 0.0], dtype=complex),
            np.array([1.0, 0.0], dtype=complex),
            np.array([1.0, 0.0], dtype=complex),
        ],
    )

    result = qfd_solver.run_qfd(
        hamiltonian=_single_qubit_x_hamiltonian(),
        backend=None,
        config={
            "algorithm": "qfd",
            "advanced_config": {
                "algorithm": "qfd",
                "num_time_points": 3,
                "max_time": 0.4,
                "time_grid_type": "linear",
                "residual_tolerance": 1e-5,
            },
        },
    )

    assert result.converged is False
    assert result.stability_summary["stability_state"] == "invalid"


def test_run_qfd_ibm_context_uses_estimator_matrix_elements() -> None:
    events: list[dict[str, object]] = []
    hamiltonian = _single_qubit_x_hamiltonian()

    result = qfd_solver.run_qfd(
        hamiltonian=hamiltonian,
        backend=StatevectorEstimator(),
        config={
            "algorithm": "qfd",
            "advanced_config": {
                "algorithm": "qfd",
                "num_time_points": 2,
                "max_time": 0.1,
                "time_grid_type": "linear",
            },
        },
        progress_callback=events.append,
        backend_context=BackendExecutionContext(backend_target="ibm_runtime"),
    )

    assert result.algorithm == "qfd"
    assert result.primary_iterations == 2
    assert result.matrix_element_summary["matrix_element_strategy"] == "branch_estimator"
    assert result.matrix_element_summary["reference_descriptor"]["reference_source"] == (
        "computational_basis_fallback"
    )
    assert result.matrix_element_summary["reference_descriptor"]["state_fingerprint"]
    assert result.matrix_element_summary["residual_kind"] == "projected_gevp_equation"
    assert result.converged is False
    assert result.matrix_element_summary["projected_solver_converged"] is True
    assert result.conditioning_summary["relative_ritz_residual"] >= 0.0
    assert result.stability_summary["stability_state"] in {"stable", "stabilized"}
    assert result.raw_filter_eigenvalues
    assert events[-1]["time_evolution_backend"] == "hardware_branch_estimator"
    assert events[-1]["scientific_converged"] is None
    assert events[-1]["termination_reason"] == "full_space_residual_unavailable"


def test_run_qfd_branch_path_uses_supported_default_time_points() -> None:
    result = qfd_solver.run_qfd(
        hamiltonian=_single_qubit_x_hamiltonian(),
        backend=StatevectorEstimator(),
        config={"algorithm": "qfd", "advanced_config": {"algorithm": "qfd"}},
        backend_context=BackendExecutionContext(backend_target="ibm_runtime"),
    )

    assert result.primary_iterations == 7
    assert result.matrix_element_summary["projected_dimension"] == 7


def test_qfd_rejects_unsupported_branch_dimension_before_primitive_creation() -> None:
    class _Backend:
        create_calls = 0

        def create_estimator(self, _context):
            self.create_calls += 1
            raise AssertionError("invalid configuration must fail before primitive creation")

    backend = _Backend()
    with pytest.raises(ValueError, match="supports at most 8 time points"):
        ALGORITHM_DEFINITION.runner(
            backend,
            {
                "algorithm": "qfd",
                "advanced_config": {
                    "algorithm": "qfd",
                    "num_time_points": 9,
                },
            },
            _single_qubit_x_hamiltonian(),
            None,
            BackendExecutionContext(backend_target="ibm_runtime"),
        )

    assert backend.create_calls == 0


def test_run_qfd_returns_stabilized_noisy_projected_solve_as_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        qfd_solver,
        "solve_stabilized_generalized_eigenproblem",
        lambda *_args, **_kwargs: StabilizedGeneralizedEigenproblemResult(
            eigenvalues=np.array([-93.0]),
            raw_eigenvalues=np.array([-1.0]),
            diagnostics={
                "stability_state": "stable",
                "overlap_condition": 128.0,
                "overlap_min_eigenvalue": 1e-3,
                "raw_projected_rank": 2,
                "stabilized_projected_rank": 1,
                "dropped_rank": 1,
                "raw_overlap_condition": 1e6,
                "stabilized_overlap_condition": 128.0,
                "psd_projected": True,
                "projected_ritz_residual_norm": 0.1,
                "relative_projected_ritz_residual": 0.01,
                "stabilized_ritz_residual_norm": 0.1,
                "stabilized_relative_ritz_residual": 0.01,
            },
        ),
    )

    events: list[dict[str, Any]] = []
    result = qfd_solver.run_qfd(
        hamiltonian=_single_qubit_x_hamiltonian(),
        backend=StatevectorEstimator(),
        config={
            "algorithm": "qfd",
            "advanced_config": {
                "algorithm": "qfd",
                "num_time_points": 2,
                "max_time": 0.1,
                "time_grid_type": "linear",
            },
        },
        progress_callback=events.append,
        backend_context=BackendExecutionContext(backend_target="ibm_runtime"),
    )

    assert result.converged is False
    assert result.primary_energy == pytest.approx(-93.0)
    assert result.stability_summary["diagnostic_only"] is True
    assert result.stability_summary["energy_state"] == "diagnostic"
    assert result.stability_summary["termination_reason"] == "projected_metric_rank_reduced"
    assert result.stability_summary["raw_projected_rank"] == 2
    assert result.stability_summary["stabilized_projected_rank"] == 1
    assert result.stability_summary["raw_overlap_condition"] == pytest.approx(1e6)
    assert result.stability_summary["stabilized_overlap_condition"] == pytest.approx(128.0)
    assert result.conditioning_summary["stabilized_relative_ritz_residual"] == pytest.approx(
        0.01
    )
    assert events[-1]["energy"] is None
    assert events[-1]["diagnostic_energy"] == pytest.approx(-93.0)
    assert events[-1]["energy_state"] == "diagnostic"


def test_projected_matrix_converged_requires_stable_overlap_gate() -> None:
    assert projected_matrix_converged(
        {
            "stability_state": "stable",
            "overlap_condition": 128.0,
            "overlap_min_eigenvalue": 1e-3,
        }
    )
    assert not projected_matrix_converged(
        {
            "stability_state": "stabilized",
            "overlap_condition": 128.0,
            "overlap_min_eigenvalue": 1e-3,
        }
    )
    assert not projected_matrix_converged(
        {
            "stability_state": "stable",
            "overlap_condition": 128.0,
            "overlap_min_eigenvalue": 1e-3,
            "dropped_rank": 1,
        }
    )


def test_run_qfd_large_ideal_aer_uses_sector_projection_without_dense_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail_dense_resolution(*args, **kwargs):
        del args, kwargs
        raise AssertionError("large ideal Aer QFD should not resolve a dense operator")

    monkeypatch.setattr(qfd_solver, "resolve_operator_matrix", _fail_dense_resolution)

    result = qfd_solver.run_qfd(
        hamiltonian=_sector_hamiltonian(norb=7, n_alpha=2, n_beta=2),
        backend=StatevectorEstimator(),
        config={
            "algorithm": "qfd",
            "advanced_config": {
                "algorithm": "qfd",
                "num_time_points": 2,
                "max_time": 0.1,
                "time_grid_type": "linear",
                "trotter_steps": 3,
            },
        },
        backend_context=BackendExecutionContext(backend_target="aer_simulator"),
    )

    assert result.matrix_element_summary["matrix_element_strategy"] == "sector_matrix_free"
    assert result.matrix_element_summary["implemented_evolution_method"] == "sector_expm_multiply"
    assert result.matrix_element_summary["sector_dimension"] > 0


def test_run_qfd_aer_state_propagation_matches_statevector() -> None:
    hamiltonian = _single_qubit_x_hamiltonian()
    config = {
        "algorithm": "qfd",
        "advanced_config": {
            "algorithm": "qfd",
            "num_time_points": 2,
            "max_time": 0.4,
            "time_grid_type": "linear",
        },
    }

    statevector_result = qfd_solver.run_qfd(
        hamiltonian=hamiltonian,
        backend=None,
        config=config,
    )
    aer_result = qfd_solver.run_qfd(
        hamiltonian=hamiltonian,
        backend=None,
        config=config,
        backend_context=BackendExecutionContext(
            backend_target="aer_simulator",
            simulator_method="statevector",
        ),
    )

    assert aer_result.primary_energy == pytest.approx(statevector_result.primary_energy, abs=1e-6)
    assert aer_result.conditioning_summary["time_points"] == pytest.approx(2.0)
    assert aer_result.matrix_element_summary["matrix_element_strategy"] == "dense_classical"
    assert aer_result.matrix_element_summary["projected_dimension"] == 2
    assert aer_result.matrix_element_summary["timing_breakdown"]["total_seconds"] >= 0.0


def test_run_qfd_rejects_empty_dense_spectrum(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        qfd_solver,
        "solve_exact_generalized_eigenproblem",
        lambda *_args, **_kwargs: (np.array([]), {}),
    )

    with pytest.raises(ValueError, match="no filter eigenvalues"):
        qfd_solver.run_qfd(
            hamiltonian=_single_qubit_x_hamiltonian(),
            backend=None,
            config={
                "algorithm": "qfd",
                "advanced_config": {
                    "algorithm": "qfd",
                    "num_time_points": 3,
                    "max_time": 0.2,
                },
            },
        )


def test_run_qfd_small_noisy_aer_uses_estimator_matrix_elements(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail_dense_resolution(*args, **kwargs):
        del args, kwargs
        raise AssertionError("noisy Aer QFD should use branch matrix elements")

    monkeypatch.setattr(qfd_solver, "resolve_operator_matrix", _fail_dense_resolution)

    result = qfd_solver.run_qfd(
        hamiltonian=_single_qubit_x_hamiltonian(),
        backend=StatevectorEstimator(),
        config={
            "algorithm": "qfd",
            "advanced_config": {
                "algorithm": "qfd",
                "num_time_points": 2,
                "max_time": 0.1,
                "time_grid_type": "linear",
                "trotter_steps": 1,
            },
        },
        backend_context=BackendExecutionContext(
            backend_target="aer_simulator",
            noise_profile={"source": "backend_derived", "reference_backend": "ibm_kyiv"},
        ),
    )

    assert result.matrix_element_summary["matrix_element_strategy"] == "branch_estimator"
    assert result.matrix_element_summary["projected_dimension"] == 2
    assert result.matrix_element_summary["projected_matrix_element_count"] == 8
    assert result.matrix_element_summary["timing_breakdown"]["total_seconds"] >= 0.0
    assert result.matrix_element_summary["backend_target"] == "aer_simulator"
    assert "max_standard_error" in result.conditioning_summary


def test_run_qfd_large_noisy_aer_rejects_projected_matrix_execution() -> None:
    with pytest.raises(ValueError, match="limited to active spaces up to 6 orbitals"):
        qfd_solver.run_qfd(
            hamiltonian=_sector_hamiltonian(norb=7, n_alpha=2, n_beta=2),
            backend=StatevectorEstimator(),
            config={
                "algorithm": "qfd",
                "advanced_config": {
                    "algorithm": "qfd",
                    "num_time_points": 4,
                    "max_time": 0.2,
                    "time_grid_type": "linear",
                    "trotter_steps": 1,
                },
            },
            backend_context=BackendExecutionContext(
                backend_target="aer_simulator",
                noise_profile={"source": "backend_derived", "reference_backend": "ibm_kyiv"},
            ),
        )


def test_run_qfd_large_ibm_rejects_projected_matrix_execution() -> None:
    with pytest.raises(ValueError, match="IBM Runtime QFD projected-matrix runs are limited"):
        qfd_solver.run_qfd(
            hamiltonian=_sector_hamiltonian(norb=7, n_alpha=2, n_beta=2),
            backend=StatevectorEstimator(),
            config={
                "algorithm": "qfd",
                "advanced_config": {
                    "algorithm": "qfd",
                    "num_time_points": 4,
                    "max_time": 0.2,
                    "time_grid_type": "linear",
                    "trotter_steps": 1,
                },
            },
            backend_context=BackendExecutionContext(backend_target="ibm_runtime"),
        )
