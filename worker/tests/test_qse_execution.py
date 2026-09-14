"""Unit tests for the QSE execution-path boundary."""

import numpy as np

from worker.chemistry.algorithms.qse.execution import execute_dense_qse, execute_sector_qse


class _FakeAction:
    dimension = 3
    norb = 2

    def expectation(self, state: np.ndarray) -> float:
        return float(np.real(np.vdot(state, state)))


def test_execute_dense_qse_composes_injected_numerical_steps() -> None:
    operator = np.diag([1.0, -0.5]).astype(complex)
    reference_state = np.array([1.0, 0.0], dtype=complex)

    def resolve_reference(**kwargs):
        assert kwargs["operator_matrix"] is operator
        return "provided_state", reference_state, [{"role": "reference"}]

    def build_basis(state, matrix, **kwargs):
        assert state is reference_state
        assert matrix is operator
        assert kwargs["target_rank"] == 2
        return [reference_state, np.array([0.0, 1.0], dtype=complex)]

    def solve_generalized(projected, overlap, **kwargs):
        assert np.array_equal(projected, operator)
        assert np.array_equal(overlap, np.eye(2))
        return np.array([-0.5, 1.0]), {
            "overlap_condition": 1.0,
            "overlap_min_eigenvalue": 1.0,
            "stability_state": "stable",
        }

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
        resolve_reference_state_fn=resolve_reference,
        build_excitation_basis_fn=build_basis,
        build_overlap_matrix_fn=lambda basis: np.eye(len(basis)),
        solve_generalized_eigenproblem_fn=solve_generalized,
        projected_ritz_diagnostics_fn=lambda *args, **kwargs: {
            "ritz_residual_norm": 0.0,
            "relative_ritz_residual": 1e-8,
        },
        real_scalar_fn=lambda value, label: float(np.real(value)),
    )

    assert outcome.basis_rank == 2
    assert outcome.reference_method == "provided_state"
    assert outcome.reference_circuit_artifacts == [{"role": "reference"}]
    assert outcome.reference_state_energy == 1.0
    assert outcome.converged is True
    assert outcome.execution_mode == "dense_exact_emulation"


def test_execute_sector_qse_preserves_matrix_free_metadata() -> None:
    action = _FakeAction()
    reference_state = np.array([1.0, 0.0, 0.0], dtype=complex)

    def solve_action_subspace(received_action, basis_matrix, **kwargs):
        assert received_action is action
        assert basis_matrix.shape == (3, 2)
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
        build_excitation_basis_fn=lambda state, received_action, **kwargs: [
            state,
            np.array([0.0, 1.0, 0.0], dtype=complex),
        ],
        solve_action_subspace_fn=solve_action_subspace,
        real_scalar_fn=lambda value, label: float(np.real(value)),
    )

    assert outcome.basis_rank == 2
    assert outcome.converged is False
    assert outcome.execution_mode == "sector_matrix_free"
    assert outcome.sector_dimension == action.dimension
    assert outcome.num_spatial_orbitals == action.norb
    assert outcome.reference_state_energy == 1.0


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
        solve_generalized_eigenproblem_fn=lambda *_args, **_kwargs: (
            np.array([-1.0]),
            {
                "overlap_condition": 1.0,
                "overlap_min_eigenvalue": 0.0,
                "stability_state": "invalid",
            },
        ),
        projected_ritz_diagnostics_fn=lambda *_args, **_kwargs: {
            "ritz_residual_norm": 0.0,
            "relative_ritz_residual": 0.0,
        },
        real_scalar_fn=lambda value, label: float(np.real(value)),
    )

    assert outcome.converged is False
