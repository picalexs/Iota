from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from qiskit.primitives import StatevectorEstimator
from qiskit.quantum_info import SparsePauliOp

from worker.adapters.aer_adapter import AerAdapter
from worker.adapters.base import BackendExecutionContext
from worker.adapters.result_adapter import normalize_result
from worker.chemistry.eigensolver import (
    StabilizedGeneralizedEigenproblemResult,
    solve_generalized_eigenproblem,
)
from worker.chemistry.hamiltonian_action import build_hamiltonian_action
from worker.chemistry.kqd_solver import (
    _build_krylov_basis,
    _build_sector_krylov_basis,
    _projected_matrix_converged,
    run_kqd,
)
from worker.chemistry.overlap import build_overlap_matrix
from worker.chemistry.sector_basis import hartree_fock_sector_state
from worker.jobs.dispatcher import dispatch_algorithm

RESOLVE_OPERATOR_MATRIX_PATH = "worker.chemistry.kqd_solver.resolve_operator_matrix"


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


def _sector_hamiltonian(*, norb: int = 7, n_alpha: int = 1, n_beta: int = 1) -> Any:
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


def test_run_kqd_uses_shared_config_and_emits_canonical_progress(
    mock_hamiltonian_bundle: object,
    capture_progress: tuple[list[dict[str, Any]], Any],
) -> None:
    events, progress_callback = capture_progress

    result = run_kqd(
        hamiltonian=mock_hamiltonian_bundle,
        backend=None,
        config={
            "algorithm": "kqd",
            "krylov_dim": 64,
            "advanced_config": {
                "algorithm": "kqd",
                "krylov_dim": 3,
                "time_step": 0.2,
                "evolution_method": "exact",
            },
        },
        progress_callback=progress_callback,
    )

    assert result.algorithm == "kqd"
    assert result.primary_iterations == 3
    assert events
    assert all(event["algorithm"] == "kqd" for event in events)
    assert all("iteration" in event for event in events)
    assert all("completed_iterations" in event for event in events)
    assert all("energy" in event for event in events)
    assert events[-1]["stage"] == "completed"
    assert events[-1]["iteration"] == result.primary_iterations


def test_dispatch_kqd_does_not_create_unused_estimator(
    mock_backend_adapter: Any,
    mock_hamiltonian_bundle: object,
) -> None:
    result = dispatch_algorithm(
        algorithm="kqd",
        backend=mock_backend_adapter,
        config_snapshot={"algorithm": "kqd", "krylov_dim": 2},
        hamiltonian_bundle=mock_hamiltonian_bundle,
    )

    assert result.algorithm == "kqd"
    assert mock_backend_adapter.calls == []


def test_kqd_basis_uses_real_time_evolved_states_not_hamiltonian_powers() -> None:
    operator = np.diag([0.0, 1.0]).astype(complex)
    reference = np.array([1.0, 1.0], dtype=complex) / np.sqrt(2.0)

    basis = _build_krylov_basis(
        object(),
        operator,
        reference,
        target_rank=3,
        evolution_method="exact",
        time_step=np.pi / 2.0,
        trotter_steps=1,
        progress_callback=None,
    )

    assert len(basis) == 3
    assert basis[0] == pytest.approx(reference)
    assert basis[1] == pytest.approx(np.array([1.0, -1.0j], dtype=complex) / np.sqrt(2.0))
    assert basis[2] == pytest.approx(np.array([1.0, -1.0], dtype=complex) / np.sqrt(2.0))
    assert not np.allclose(basis[1], operator @ reference)


def test_kqd_sector_krylov_matches_dense_sector_matrix() -> None:
    hamiltonian = _sector_hamiltonian(norb=4, n_alpha=1, n_beta=1)
    action = build_hamiltonian_action(hamiltonian)
    reference = hartree_fock_sector_state(action.norb, action.nelec)
    dense_operator = np.column_stack(
        [
            action.matvec(np.eye(action.dimension, dtype=complex)[:, index])
            for index in range(action.dimension)
        ]
    )

    dense_basis = _build_krylov_basis(
        object(),
        dense_operator,
        reference,
        target_rank=3,
        evolution_method="exact",
        time_step=0.2,
        trotter_steps=1,
        progress_callback=None,
    )
    sector_basis = _build_sector_krylov_basis(
        action,
        reference,
        target_rank=3,
        evolution_method="exact",
        time_step=0.2,
        trotter_steps=1,
        progress_callback=None,
    )

    dense_matrix = np.column_stack(dense_basis)
    sector_matrix = np.column_stack(sector_basis)
    dense_values, _ = solve_generalized_eigenproblem(
        dense_matrix.conj().T @ dense_operator @ dense_matrix,
        build_overlap_matrix(dense_basis),
    )
    sector_values, _ = solve_generalized_eigenproblem(
        action.project(sector_matrix),
        build_overlap_matrix(sector_basis),
    )

    assert sector_values[:3] == pytest.approx(dense_values[:3], abs=1e-8)


def test_run_kqd_sector_path_does_not_materialize_dense_matrix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail_dense_resolution(*args: Any, **kwargs: Any) -> np.ndarray:
        del args, kwargs
        raise AssertionError("KQD sector path should not resolve a dense matrix")

    monkeypatch.setattr(RESOLVE_OPERATOR_MATRIX_PATH, _fail_dense_resolution)

    result = run_kqd(
        hamiltonian=_sector_hamiltonian(),
        backend=None,
        config={
            "algorithm": "kqd",
            "advanced_config": {
                "algorithm": "kqd",
                "krylov_dim": 3,
                "time_step": 0.2,
                "evolution_method": "exact",
                "residual_tolerance": 1e-8,
            },
        },
    )

    assert result.algorithm == "kqd"
    assert result.primary_energy is not None
    assert result.matrix_element_summary["matrix_element_strategy"] == "sector_matrix_free"
    assert result.matrix_element_summary["projected_dimension"] == result.krylov_rank
    assert result.matrix_element_summary["projected_matrix_element_count"] > 0
    assert result.matrix_element_summary["timing_breakdown"]["total_seconds"] >= 0.0
    assert result.matrix_element_summary["basis_index_convention"] == "k=0..krylov_dim-1"
    assert result.matrix_element_summary["time_points"] == pytest.approx([0.0, 0.2, 0.4])
    assert result.orthogonality_metrics["sector_dimension"] == pytest.approx(49.0)


def test_run_kqd_sector_path_reports_orthonormal_projected_energy() -> None:
    result = run_kqd(
        hamiltonian=_sector_hamiltonian(),
        backend=None,
        config={
            "algorithm": "kqd",
            "advanced_config": {
                "algorithm": "kqd",
                "krylov_dim": 5,
                "time_step": 0.2,
                "evolution_method": "exact",
                "residual_tolerance": 1e-8,
            },
        },
    )

    assert result.primary_energy == pytest.approx(
        result.orthogonality_metrics["ritz_energy"],
        abs=1e-10,
    )


def test_run_kqd_passes_residual_tolerance_into_projected_ritz_diagnostics(
    monkeypatch, mock_hamiltonian_bundle: object
) -> None:
    captured: dict[str, float] = {}

    from worker.chemistry import kqd_solver

    original = kqd_solver.projected_ritz_diagnostics

    def _capture(operator, basis_matrix, *, residual_tolerance):
        del operator, basis_matrix
        captured["residual_tolerance"] = residual_tolerance
        return {
            "relative_ritz_residual": residual_tolerance / 2.0,
            "ritz_residual_norm": residual_tolerance / 2.0,
            "residual_convergence_threshold": residual_tolerance,
            "basis_numerical_rank": 2.0,
        }

    monkeypatch.setattr(kqd_solver, "projected_ritz_diagnostics", _capture)
    try:
        result = run_kqd(
            hamiltonian=mock_hamiltonian_bundle,
            backend=None,
            config={
                "algorithm": "kqd",
                "advanced_config": {
                    "algorithm": "kqd",
                    "krylov_dim": 3,
                    "time_step": 0.2,
                    "evolution_method": "exact",
                    "residual_tolerance": 1e-5,
                },
            },
        )
    finally:
        monkeypatch.setattr(kqd_solver, "projected_ritz_diagnostics", original)

    assert captured["residual_tolerance"] == pytest.approx(1e-5)
    assert result.converged is True


def test_run_kqd_does_not_mark_singular_dense_projection_converged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "worker.chemistry.kqd_solver._build_krylov_basis",
        lambda *args, **kwargs: [
            np.array([1.0, 0.0], dtype=complex),
            np.array([1.0, 0.0], dtype=complex),
            np.array([1.0, 0.0], dtype=complex),
        ],
    )

    result = run_kqd(
        hamiltonian=_single_qubit_x_hamiltonian(),
        backend=None,
        config={
            "algorithm": "kqd",
            "advanced_config": {
                "algorithm": "kqd",
                "krylov_dim": 3,
                "time_step": 0.2,
                "evolution_method": "exact",
                "residual_tolerance": 1e-5,
            },
        },
    )

    assert result.converged is False
    assert result.stability_summary["stability_state"] == "invalid"
    assert result.stability_summary["termination_reason"] == "projected_metric_rank_reduced"


def test_run_kqd_emits_reference_and_evolution_circuit_artifacts() -> None:
    hamiltonian = _single_qubit_x_hamiltonian()

    result = run_kqd(
        hamiltonian=hamiltonian,
        backend=None,
        config={
            "algorithm": "kqd",
            "advanced_config": {
                "algorithm": "kqd",
                "krylov_dim": 3,
                "time_step": 0.2,
                "evolution_method": "exact",
                "trotter_steps": 2,
            },
        },
    )

    metrics = normalize_result(result)["algorithm_metrics"]
    assert [artifact["role"] for artifact in metrics["circuit_artifacts"]] == [
        "reference",
        "evolution",
    ]
    assert metrics["circuit_artifacts"][1]["representative"] is True
    assert metrics["circuit_artifacts"][1]["source"] == "logical_time_evolution_template"


def test_run_kqd_ibm_context_uses_estimator_matrix_elements(
) -> None:
    events: list[dict[str, Any]] = []
    hamiltonian = _single_qubit_x_hamiltonian()

    result = run_kqd(
        hamiltonian=hamiltonian,
        backend=StatevectorEstimator(),
        config={
            "algorithm": "kqd",
            "advanced_config": {
                "algorithm": "kqd",
                "krylov_dim": 2,
                "time_step": 0.1,
                "evolution_method": "trotter",
                "trotter_steps": 1,
            },
        },
        progress_callback=events.append,
        backend_context=BackendExecutionContext(backend_target="ibm_runtime"),
    )

    assert result.algorithm == "kqd"
    assert result.krylov_rank == 2
    assert result.matrix_element_summary["matrix_element_strategy"] == "branch_estimator"
    assert result.matrix_element_summary["reference_descriptor"]["reference_source"] == (
        "computational_basis_fallback"
    )
    assert result.matrix_element_summary["reference_descriptor"]["state_fingerprint"]
    assert (
        result.matrix_element_summary["execution_selection_reason"]
        == "requested_ibm_runtime_requires_branch_estimator"
    )
    assert result.matrix_element_summary["residual_kind"] == "projected_generalized_eigenpair"
    assert "max_standard_error" in result.matrix_element_summary
    assert result.orthogonality_metrics["relative_ritz_residual"] >= 0.0
    assert result.stability_summary["stability_state"] in {"stable", "stabilized"}
    assert result.raw_ritz_values
    assert events[-1]["time_evolution_backend"] == "hardware_branch_estimator"


def test_run_kqd_returns_stabilized_noisy_projected_solve_as_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "worker.chemistry.kqd_solver.solve_stabilized_generalized_eigenproblem",
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
    result = run_kqd(
        hamiltonian=_single_qubit_x_hamiltonian(),
        backend=StatevectorEstimator(),
        config={
            "algorithm": "kqd",
            "advanced_config": {
                "algorithm": "kqd",
                "krylov_dim": 2,
                "time_step": 0.1,
                "evolution_method": "trotter",
                "trotter_steps": 1,
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
    assert result.orthogonality_metrics["stabilized_relative_ritz_residual"] == pytest.approx(
        0.01
    )
    assert events[-1]["energy"] is None
    assert events[-1]["diagnostic_energy"] == pytest.approx(-93.0)
    assert events[-1]["energy_state"] == "diagnostic"


def test_projected_matrix_converged_requires_stable_overlap_gate() -> None:
    assert _projected_matrix_converged(
        {
            "stability_state": "stable",
            "overlap_condition": 128.0,
            "overlap_min_eigenvalue": 1e-3,
        }
    )
    assert not _projected_matrix_converged(
        {
            "stability_state": "stabilized",
            "overlap_condition": 128.0,
            "overlap_min_eigenvalue": 1e-3,
        }
    )
    assert not _projected_matrix_converged(
        {
            "stability_state": "stable",
            "overlap_condition": 128.0,
            "overlap_min_eigenvalue": 1e-3,
            "dropped_rank": 1,
        }
    )


def test_run_kqd_large_ideal_aer_uses_sector_projection_without_dense_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail_dense_resolution(*args: Any, **kwargs: Any) -> np.ndarray:
        del args, kwargs
        raise AssertionError("large ideal Aer KQD should not resolve a dense operator")

    monkeypatch.setattr(RESOLVE_OPERATOR_MATRIX_PATH, _fail_dense_resolution)

    result = run_kqd(
        hamiltonian=_sector_hamiltonian(norb=7, n_alpha=2, n_beta=2),
        backend=StatevectorEstimator(),
        config={
            "algorithm": "kqd",
            "advanced_config": {
                "algorithm": "kqd",
                "krylov_dim": 2,
                "time_step": 0.1,
                "evolution_method": "trotter",
                "trotter_steps": 1,
            },
        },
        backend_context=BackendExecutionContext(backend_target="aer_simulator"),
    )

    assert result.matrix_element_summary["matrix_element_strategy"] == "sector_matrix_free"
    assert (
        result.matrix_element_summary["implemented_evolution_method"]
        == "sector_diagonal_residual_trotter"
    )
    assert result.matrix_element_summary["sector_dimension"] > 0


def test_run_kqd_aer_state_propagation_matches_statevector() -> None:
    hamiltonian = _single_qubit_x_hamiltonian()
    config = {
        "algorithm": "kqd",
        "advanced_config": {
            "algorithm": "kqd",
            "krylov_dim": 2,
            "time_step": 0.4,
            "evolution_method": "trotter",
            "trotter_steps": 1,
        },
    }

    statevector_result = run_kqd(hamiltonian=hamiltonian, backend=None, config=config)
    aer_result = run_kqd(
        hamiltonian=hamiltonian,
        backend=None,
        config=config,
        backend_context=BackendExecutionContext(
            backend_target="aer_simulator",
            simulator_method="statevector",
        ),
    )

    assert aer_result.primary_energy == pytest.approx(statevector_result.primary_energy, abs=1e-6)
    assert aer_result.orthogonality_metrics["basis_rank"] == pytest.approx(2.0)


def test_run_kqd_small_noisy_aer_uses_estimator_matrix_elements(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail_dense_resolution(*args: Any, **kwargs: Any) -> np.ndarray:
        del args, kwargs
        raise AssertionError("noisy Aer KQD should use branch matrix elements")

    monkeypatch.setattr(RESOLVE_OPERATOR_MATRIX_PATH, _fail_dense_resolution)

    result = run_kqd(
        hamiltonian=_single_qubit_x_hamiltonian(),
        backend=StatevectorEstimator(),
        config={
            "algorithm": "kqd",
            "advanced_config": {
                "algorithm": "kqd",
                "krylov_dim": 2,
                "time_step": 0.1,
                "evolution_method": "trotter",
                "trotter_steps": 1,
            },
        },
        backend_context=BackendExecutionContext(
            backend_target="aer_simulator",
            noise_profile={"source": "backend_derived", "reference_backend": "ibm_kyiv"},
        ),
    )

    assert result.matrix_element_summary["matrix_element_strategy"] == "branch_estimator"
    assert result.matrix_element_summary["backend_target"] == "aer_simulator"


def test_run_kqd_custom_aer_noise_returns_finite_reported_or_diagnostic_result() -> None:
    hamiltonian = SimpleNamespace(
        pauli_hamiltonian=SparsePauliOp.from_list([("XX", 0.5), ("ZI", 1.0)]),
        num_qubits=2,
    )
    context = BackendExecutionContext(
        backend_target="aer_simulator",
        backend_options={"seed_simulator": 7},
        noise_profile={
            "source": "custom_preset",
            "preset": "depolarizing_cx",
            "strength": 0.01,
        },
        shots=256,
    )

    result = run_kqd(
        hamiltonian=hamiltonian,
        backend=AerAdapter().create_estimator(context),
        config={
            "algorithm": "kqd",
            "advanced_config": {
                "algorithm": "kqd",
                "krylov_dim": 2,
                "time_step": 0.1,
                "evolution_method": "trotter",
                "trotter_steps": 1,
            },
        },
        backend_context=context,
    )

    assert np.isfinite(result.primary_energy)
    assert result.matrix_element_summary["matrix_element_strategy"] == "branch_estimator"
    assert result.matrix_element_summary["overlap_diagonal_normalized"] is True
    if result.stability_summary["stability_state"] == "stabilized":
        assert result.converged is False
        assert result.stability_summary["diagnostic_only"] is True


def test_run_kqd_branch_rejects_exact_evolution_claim() -> None:
    with pytest.raises(ValueError, match="supports evolution_method='trotter' only"):
        run_kqd(
            hamiltonian=_single_qubit_x_hamiltonian(),
            backend=StatevectorEstimator(),
            config={
                "algorithm": "kqd",
                "advanced_config": {
                    "algorithm": "kqd",
                    "krylov_dim": 2,
                    "time_step": 0.1,
                    "evolution_method": "exact",
                    "trotter_steps": 1,
                },
            },
            backend_context=BackendExecutionContext(
                backend_target="aer_simulator",
                noise_profile={"source": "backend_derived", "reference_backend": "ibm_kyiv"},
            ),
        )


def test_run_kqd_large_noisy_aer_rejects_projected_matrix_execution() -> None:
    with pytest.raises(ValueError, match="limited to active spaces up to 6 orbitals"):
        run_kqd(
            hamiltonian=_sector_hamiltonian(norb=7, n_alpha=2, n_beta=2),
            backend=StatevectorEstimator(),
            config={
                "algorithm": "kqd",
                "advanced_config": {
                    "algorithm": "kqd",
                    "krylov_dim": 4,
                    "time_step": 0.1,
                    "evolution_method": "trotter",
                    "trotter_steps": 1,
                },
            },
            backend_context=BackendExecutionContext(
                backend_target="aer_simulator",
                noise_profile={"source": "backend_derived", "reference_backend": "ibm_kyiv"},
            ),
        )


def test_run_kqd_large_ibm_rejects_projected_matrix_execution() -> None:
    with pytest.raises(ValueError, match="IBM Runtime KQD projected-matrix runs are limited"):
        run_kqd(
            hamiltonian=_sector_hamiltonian(norb=7, n_alpha=2, n_beta=2),
            backend=StatevectorEstimator(),
            config={
                "algorithm": "kqd",
                "advanced_config": {
                    "algorithm": "kqd",
                    "krylov_dim": 4,
                    "time_step": 0.1,
                    "evolution_method": "trotter",
                    "trotter_steps": 1,
                },
            },
            backend_context=BackendExecutionContext(backend_target="ibm_runtime"),
        )
