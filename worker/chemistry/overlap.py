"""Overlap utilities shared by worker chemistry solvers."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np


def state_overlap(left: np.ndarray, right: np.ndarray) -> complex:
    """Return the Hermitian inner product between two states."""
    return complex(np.vdot(np.asarray(left, dtype=complex), np.asarray(right, dtype=complex)))


def build_overlap_matrix(states: Iterable[np.ndarray]) -> np.ndarray:
    """Build a pairwise overlap matrix for a collection of states."""
    states_list = [np.asarray(state, dtype=complex) for state in states]
    if not states_list:
        return np.zeros((0, 0), dtype=complex)

    matrix = np.empty((len(states_list), len(states_list)), dtype=complex)
    for row, left in enumerate(states_list):
        for col, right in enumerate(states_list):
            matrix[row, col] = state_overlap(left, right)
    return matrix


def overlap_metrics(overlap_matrix: np.ndarray) -> dict[str, float]:
    """Compute basic conditioning metrics for an overlap matrix."""
    overlap = np.asarray(overlap_matrix, dtype=complex)
    if overlap.size == 0:
        return {
            "condition_number": 0.0,
            "max_offdiag": 0.0,
            "min_eigenvalue": 0.0,
            "trace_deviation": 0.0,
        }

    eigenvalues = np.linalg.eigvalsh(0.5 * (overlap + overlap.conj().T))
    singular_values = np.linalg.svd(overlap, compute_uv=False)
    if singular_values.size == 0 or singular_values[-1] <= 0.0:
        condition_number = float("inf")
    else:
        condition_number = float(singular_values[0] / singular_values[-1])

    diagonal = np.diag(overlap)
    offdiag = overlap - np.diag(diagonal)
    max_offdiag = float(np.max(np.abs(offdiag))) if offdiag.size else 0.0
    trace_deviation = float(abs(np.trace(overlap) - overlap.shape[0]))

    return {
        "condition_number": condition_number,
        "max_offdiag": max_offdiag,
        "min_eigenvalue": float(np.min(eigenvalues).real),
        "trace_deviation": trace_deviation,
    }
