"""Unit tests for shared projected-energy calculations."""

from __future__ import annotations

import numpy as np
import pytest

from worker.chemistry.projected_energy import (
    generalized_projected_ground_energy,
    matrix_free_projected_ground_energy,
    orthonormal_projected_ground_energy,
)


def test_generalized_projected_ground_energy_solves_the_current_subspace() -> None:
    operator = np.diag([1.0, 3.0]).astype(complex)
    basis = [np.array([1.0, 0.0], dtype=complex), np.array([0.0, 1.0], dtype=complex)]

    assert generalized_projected_ground_energy(operator, basis) == pytest.approx(1.0)


def test_generalized_projected_ground_energy_can_use_direct_single_state_expectation() -> None:
    operator = np.diag([1.0, 3.0]).astype(complex)
    state = np.array([1.0, 1.0], dtype=complex) / np.sqrt(2.0)

    assert generalized_projected_ground_energy(
        operator,
        [state],
        direct_single_state=True,
    ) == pytest.approx(2.0)


def test_generalized_projected_ground_energy_accepts_boundary_callbacks() -> None:
    operator = np.eye(2, dtype=complex)
    basis = [np.array([1.0, 0.0], dtype=complex)]
    overlap_calls: list[int] = []
    eigensolver_calls: list[tuple[np.ndarray, np.ndarray]] = []

    def build_overlap(states):
        overlap_calls.append(len(states))
        return np.eye(len(states), dtype=complex)

    def solve_eigenproblem(projected_hamiltonian, overlap):
        eigensolver_calls.append((projected_hamiltonian, overlap))
        return np.array([0.75]), {}

    result = generalized_projected_ground_energy(
        operator,
        basis,
        overlap_builder=build_overlap,
        eigensolver=solve_eigenproblem,
    )

    assert result == 0.75
    assert overlap_calls == [1]
    assert len(eigensolver_calls) == 1


def test_orthonormal_projected_ground_energy_ignores_dependent_columns() -> None:
    operator = np.diag([1.0, 3.0]).astype(complex)
    basis = [
        np.array([1.0, 0.0], dtype=complex),
        np.array([2.0, 0.0], dtype=complex),
        np.array([0.0, 1.0], dtype=complex),
    ]

    assert orthonormal_projected_ground_energy(operator, basis) == pytest.approx(1.0)


def test_orthonormal_projected_ground_energy_returns_none_for_empty_or_zero_basis() -> None:
    operator = np.eye(2, dtype=complex)

    assert orthonormal_projected_ground_energy(operator, []) is None
    assert (
        orthonormal_projected_ground_energy(
            operator,
            [np.zeros(2, dtype=complex)],
        )
        is None
    )


def test_matrix_free_projected_ground_energy_uses_action_boundary() -> None:
    class Action:
        dimension = 2

        def project(self, basis_matrix: np.ndarray) -> np.ndarray:
            return basis_matrix.conj().T @ np.diag([1.0, 3.0]) @ basis_matrix

        def residual_diagnostics(
            self,
            basis_matrix: np.ndarray,
            *,
            residual_tolerance: float,
        ) -> tuple[dict[str, float], np.ndarray | None]:
            del basis_matrix, residual_tolerance
            return {}, None

    basis = [
        np.array([1.0, 0.0], dtype=complex),
        np.array([0.0, 1.0], dtype=complex),
    ]

    assert matrix_free_projected_ground_energy(
        Action(),
        basis,
        residual_tolerance=1e-8,
    ) == pytest.approx(1.0)
