"""Pure projected-energy calculations shared by subspace solvers."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import numpy as np

from worker.chemistry.eigensolver import solve_generalized_eigenproblem
from worker.chemistry.hamiltonian_action import HamiltonianAction
from worker.chemistry.overlap import build_overlap_matrix
from worker.chemistry.projected_subspace import orthonormalize_columns, solve_action_subspace

OverlapBuilder = Callable[[Sequence[np.ndarray]], np.ndarray]
GeneralizedEigensolver = Callable[[np.ndarray, np.ndarray], tuple[np.ndarray, Any]]


def generalized_projected_ground_energy(
    operator_matrix: np.ndarray,
    basis: Sequence[np.ndarray],
    *,
    direct_single_state: bool = False,
    overlap_builder: OverlapBuilder = build_overlap_matrix,
    eigensolver: GeneralizedEigensolver = solve_generalized_eigenproblem,
) -> float | None:
    """Return the lowest projected energy for the current basis."""
    if not basis:
        return None
    if direct_single_state and len(basis) == 1:
        state = np.asarray(basis[0], dtype=complex)
        return float(np.real(np.vdot(state, operator_matrix @ state)))

    basis_matrix = np.column_stack(basis)
    projected_hamiltonian = basis_matrix.conj().T @ operator_matrix @ basis_matrix
    overlap = overlap_builder(basis)
    projected_eigenvalues, _ = eigensolver(projected_hamiltonian, overlap)
    return float(projected_eigenvalues[0]) if projected_eigenvalues.size else None


def orthonormal_projected_ground_energy(
    operator_matrix: np.ndarray,
    basis: Sequence[np.ndarray],
) -> float | None:
    """Return the lowest energy after orthonormalizing a dense projected basis."""
    if not basis:
        return None
    try:
        orthonormal_basis, _ = orthonormalize_columns(np.column_stack(basis))
    except ValueError:
        return None
    projected = orthonormal_basis.conj().T @ operator_matrix @ orthonormal_basis
    projected = 0.5 * (projected + projected.conj().T)
    eigenvalues = np.linalg.eigvalsh(projected)
    return float(np.real_if_close(eigenvalues[0])) if eigenvalues.size else None


def matrix_free_projected_ground_energy(
    action: HamiltonianAction,
    basis: Sequence[np.ndarray],
    *,
    residual_tolerance: float,
) -> float | None:
    """Return the lowest energy for a matrix-free projected basis."""
    if not basis:
        return None
    try:
        eigenvalues, *_ = solve_action_subspace(
            action,
            np.column_stack(basis),
            residual_tolerance=residual_tolerance,
        )
    except ValueError:
        return None
    return float(eigenvalues[0]) if eigenvalues.size else None


__all__ = [
    "generalized_projected_ground_energy",
    "matrix_free_projected_ground_energy",
    "orthonormal_projected_ground_energy",
]
