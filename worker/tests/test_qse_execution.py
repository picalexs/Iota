"""Unit tests for the QSE execution-path boundary."""

from types import SimpleNamespace

import numpy as np
import pytest

from worker.chemistry.algorithms.qse.execution import (
    execute_dense_qse,
    execute_measured_qse,
    execute_sector_qse,
)
from worker.chemistry.eigensolver import solve_exact_generalized_eigensystem


class _FakeAction:
    dimension = 3
    norb = 2

    def expectation(self, state: np.ndarray) -> float:
        return float(np.real(np.vdot(state, state)))


def test_execute_dense_qse_uses_exact_final_solver_and_tracks_progress_regularization() -> None:
    operator = np.diag([1.0, -0.5]).astype(complex)
    reference_state = np.array([1.0, 0.0], dtype=complex)
    basis_regularization = []

    def resolve_reference(**kwargs):
        assert kwargs["operator_matrix"] is operator
        return "provided_state", reference_state, [{"role": "reference"}]

    def build_basis(state, matrix, **kwargs):
        assert state is reference_state
        assert matrix is operator
        assert kwargs["target_rank"] == 2
        basis_regularization.append(kwargs["regularization"])
        return [reference_state, np.array([0.0, 1.0], dtype=complex)]

    outcome = execute_dense_qse(
        hamiltonian=object(),
        backend=object(),
        operator=operator,
        resolved_config={"reference_method": "provided_state"},
        excitation_level="singles",
        target_rank=2,
        overlap_threshold=1e-8,
        regularization=1e-3,
        residual_tolerance=1e-6,
        progress_callback=None,
        resolve_reference_state_fn=resolve_reference,
        build_excitation_basis_fn=build_basis,
        build_overlap_matrix_fn=lambda basis: np.eye(len(basis)),
        solve_generalized_eigensystem_fn=solve_exact_generalized_eigensystem,
        real_scalar_fn=lambda value, label: float(np.real(value)),
    )

    assert outcome.basis_rank == 2
    assert outcome.reference_method == "provided_state"
    assert outcome.reference_circuit_artifacts == [{"role": "reference"}]
    assert outcome.reference_state_energy == 1.0
    assert outcome.converged is True
    assert outcome.execution_mode == "dense_exact_emulation"
    assert outcome.eigenvalues == pytest.approx([-0.5, 1.0])
    assert outcome.residual_diagnostics["ritz_energy"] == pytest.approx(-0.5)
    assert basis_regularization == [pytest.approx(1e-3)]
    assert outcome.diagnostics["regularization"] == pytest.approx(0.0)
    assert outcome.diagnostics["requested_regularization"] == pytest.approx(1e-3)
    assert outcome.diagnostics["regularization_scope"] == "basis_progress_estimates_only"
    assert outcome.diagnostics["final_metric_diagonal_shift"] == pytest.approx(0.0)
    assert outcome.diagnostics["regularization_may_change_reported_energy"] is False


def test_execute_dense_qse_collects_basis_without_enabling_progress_work() -> None:
    operator = np.diag([1.0, -0.5]).astype(complex)
    reference_state = np.array([1.0, 0.0], dtype=complex)
    excitation = ("single", (1,), (0,))

    def build_basis(state, _matrix, **kwargs):
        assert kwargs["progress_callback"] is None
        kwargs["selection_callback"](("reference", (), ()))
        kwargs["selection_callback"](excitation)
        return [state, np.array([0.0, 1.0], dtype=complex)]

    outcome = execute_dense_qse(
        hamiltonian=object(),
        backend=object(),
        operator=operator,
        resolved_config={"reference_method": "provided_state"},
        excitation_level="singles",
        target_rank=2,
        overlap_threshold=1e-8,
        regularization=0.0,
        residual_tolerance=1e-6,
        progress_callback=None,
        resolve_reference_state_fn=lambda **_kwargs: (
            "provided_state",
            reference_state,
            [],
        ),
        build_excitation_basis_fn=build_basis,
        build_overlap_matrix_fn=lambda basis: np.eye(len(basis)),
        solve_generalized_eigensystem_fn=solve_exact_generalized_eigensystem,
        real_scalar_fn=lambda value, label: float(np.real(value)),
    )

    selection = outcome.diagnostics["basis_selection"]
    assert selection["selected_specs_complete"] is True
    assert selection["selected_excitation_specs"][1]["kind"] == "single"


def test_execute_sector_qse_preserves_matrix_free_metadata() -> None:
    action = _FakeAction()
    reference_state = np.array([1.0, 0.0, 0.0], dtype=complex)
    basis_regularization = []

    def build_basis(state, received_action, **kwargs):
        assert received_action is action
        assert "regularization" not in kwargs
        basis_regularization.append("not passed")
        return [state, np.array([0.0, 1.0, 0.0], dtype=complex)]

    def solve_action_subspace(received_action, basis_matrix, **kwargs):
        assert received_action is action
        assert basis_matrix.shape == (3, 2)
        assert kwargs["regularization"] == pytest.approx(0.0)
        return (
            np.array([-2.0]),
            None,
            {
                "overlap_condition": 2.0,
                "overlap_min_eigenvalue": 1.0,
                "stability_state": "stable",
            },
            {"ritz_residual_norm": 0.1, "relative_ritz_residual": 1e-3},
            None,
        )

    outcome = execute_sector_qse(
        hamiltonian=object(),
        action=action,
        resolved_config={"reference_method": "hf"},
        excitation_level="singles",
        target_rank=2,
        overlap_threshold=1e-8,
        regularization=1e-8,
        residual_tolerance=1e-4,
        progress_callback=None,
        resolve_reference_state_fn=lambda **kwargs: (
            "hf",
            reference_state,
            [{"role": "reference"}],
        ),
        build_excitation_basis_fn=build_basis,
        solve_action_subspace_fn=solve_action_subspace,
        real_scalar_fn=lambda value, label: float(np.real(value)),
    )

    assert outcome.basis_rank == 2
    assert outcome.converged is False
    assert outcome.execution_mode == "sector_matrix_free"
    assert outcome.sector_dimension == action.dimension
    assert outcome.num_spatial_orbitals == action.norb
    assert outcome.reference_state_energy == 1.0
    assert basis_regularization == ["not passed"]
    assert outcome.diagnostics["regularization"] == pytest.approx(0.0)
    assert outcome.diagnostics["requested_regularization"] == pytest.approx(1e-8)
    assert outcome.diagnostics["regularization_scope"] == (
        "not_applied_in_fixed_sector_path"
    )
    assert outcome.diagnostics["regularization_may_change_reported_energy"] is False


def test_execute_dense_qse_rejects_unstable_projection_even_with_small_residual() -> None:
    operator = np.eye(2, dtype=complex)
    reference_state = np.array([1.0, 0.0], dtype=complex)

    outcome = execute_dense_qse(
        hamiltonian=object(),
        backend=object(),
        operator=operator,
        resolved_config={"reference_method": "provided_state"},
        excitation_level="singles",
        target_rank=2,
        overlap_threshold=1e-8,
        regularization=1e-8,
        residual_tolerance=1e-6,
        progress_callback=None,
        resolve_reference_state_fn=lambda **_kwargs: (
            "provided_state",
            reference_state,
            [],
        ),
        build_excitation_basis_fn=lambda *_args, **_kwargs: [
            reference_state,
            np.array([0.0, 1.0], dtype=complex),
        ],
        build_overlap_matrix_fn=lambda _basis: np.eye(2, dtype=complex),
        solve_generalized_eigensystem_fn=lambda *_args, **_kwargs: (
            np.array([1.0, 1.0]),
            np.eye(2, dtype=complex),
            {
                "overlap_condition": 1.0,
                "overlap_min_eigenvalue": 0.0,
                "stability_state": "invalid",
            },
        ),
        real_scalar_fn=lambda value, label: float(np.real(value)),
    )

    assert outcome.converged is False


def test_execute_measured_qse_uses_overlap_uncertainty_for_rank_cutoff() -> None:
    observed_errors: list[float | None] = []
    observed_regularization: list[float] = []
    hamiltonian = SimpleNamespace(num_electrons_alpha=1, num_electrons_beta=1)

    def solve_stabilized(_projected, _overlap, **kwargs):
        observed_errors.append(kwargs.get("max_standard_error"))
        observed_regularization.append(kwargs["regularization"])
        return SimpleNamespace(
            eigenvalues=np.array([-1.0]),
            diagnostics={
                "stability_state": "stable",
                "dropped_rank": 0,
                "overlap_condition": 1.0,
                "overlap_min_eigenvalue": 1.0,
                "retained_rank": 1,
                "projected_ritz_residual_norm": 0.0,
                "relative_projected_ritz_residual": 0.0,
            },
        )

    outcome = execute_measured_qse(
        hamiltonian=hamiltonian,
        estimator=object(),
        resolved_config={"reference_method": "hf"},
        excitation_level="singles",
        target_rank=1,
        regularization=1e-8,
        residual_tolerance=1e-6,
        progress_callback=None,
        backend_context=SimpleNamespace(backend_target="ibm_runtime"),
        estimate_matrices_fn=lambda **_kwargs: SimpleNamespace(
            projected_hamiltonian=np.array([[-1.0]], dtype=complex),
            overlap=np.array([[1.0]], dtype=complex),
            summary={
                "max_hamiltonian_standard_error": 5.0,
                "max_overlap_standard_error": 0.02,
                "max_standard_error": 5.0,
            },
        ),
        solve_stabilized_fn=solve_stabilized,
        diagnostic_reportable_fn=lambda _diagnostics: True,
        build_reference_descriptor_fn=lambda **_kwargs: {"reference_source": "hf"},
        build_hf_reference_state_fn=lambda *_args, **_kwargs: (
            np.array([1.0, 0.0], dtype=complex),
            "hartree_fock",
        ),
    )

    assert observed_errors == pytest.approx([0.02])
    assert observed_regularization == pytest.approx([1e-8])
    assert outcome.diagnostics["requested_regularization"] == pytest.approx(1e-8)
    assert outcome.diagnostics["regularization_scope"] == (
        "raw_metric_spectrum_and_overlap_mode_cutoff_floor"
    )
    assert outcome.diagnostics["final_metric_diagonal_shift"] == pytest.approx(0.0)
    assert outcome.diagnostics["regularization_may_change_reported_energy"] is True
