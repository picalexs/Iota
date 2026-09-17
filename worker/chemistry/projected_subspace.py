"""Small projected-subspace linear algebra helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from worker.chemistry.hamiltonian_action import HamiltonianAction

_HARDWARE_OVERLAP_CONDITION_LIMIT = 1e10

_STABILIZED_DIAGNOSTIC_RELATIVE_RESIDUAL_LIMIT = 1.0


def _real_diagnostic(value: Any, *, default: float) -> float:
    """Return a finite real scalar from a projected-solve diagnostic."""
    if value is None:
        return default
    scalar = complex(np.asarray(value).reshape(()).item())
    if not np.isfinite(scalar.real) or not np.isfinite(scalar.imag):
        return default
    if abs(scalar.imag) > 1e-8:
        return default
    return float(scalar.real)


def projected_matrix_converged(diagnostics: Mapping[str, Any]) -> bool:
    """Return whether projected-matrix conditioning passes the stability gate."""
    if int(diagnostics.get("dropped_rank", 0) or 0) > 0:
        return False
    condition = _real_diagnostic(
        diagnostics.get("overlap_condition"),
        default=float("inf"),
    )
    min_eigenvalue = _real_diagnostic(
        diagnostics.get("overlap_min_eigenvalue"),
        default=0.0,
    )
    stability_state = diagnostics.get("stability_state")
    return bool(
        stability_state == "stable"
        and np.isfinite(condition)
        and condition <= _HARDWARE_OVERLAP_CONDITION_LIMIT
        and min_eigenvalue > 0.0
    )


def projected_convergence_reason(
    diagnostics: Mapping[str, Any],
    *,
    relative_residual: float,
    residual_tolerance: float,
) -> str:
    """Explain why a projected solve did or did not pass its convergence gate."""
    if not projected_matrix_converged(diagnostics):
        if int(diagnostics.get("dropped_rank", 0) or 0) > 0:
            return "projected_metric_rank_reduced"
        if bool(diagnostics.get("psd_projected", False)):
            return "projected_metric_not_positive_definite"
        return "projected_metric_unstable"
    if not np.isfinite(relative_residual) or relative_residual > residual_tolerance:
        return "residual_tolerance_not_met"
    return "converged"


def _stabilized_relative_residual(diagnostics: Mapping[str, Any]) -> float | None:
    """Return the finite relative Ritz residual of a stabilized projected solve."""
    for key in (
        "relative_projected_ritz_residual",
        "stabilized_relative_ritz_residual",
    ):
        residual = _real_diagnostic(diagnostics.get(key), default=float("nan"))
        if np.isfinite(residual):
            return residual
    return None


def projected_diagnostic_energy_is_reportable(diagnostics: Mapping[str, Any]) -> bool:
    """Return whether a stabilized projected solve yields a reportable diagnostic.

    A ``stable`` solve is always reportable. A ``stabilized`` solve (overlap
    thresholding or PSD projection dropped rank) is reportable as a
    non-converged diagnostic only when a finite subspace remains and its
    relative Ritz residual is finite and within the diagnostic bound. Truncation
    is the accepted noise treatment for quantum-Krylov generalized eigenproblems
    (arXiv:2110.07492, arXiv:2604.11532); the retained energy is a diagnostic,
    never a converged or chemically accurate result. ``invalid`` states, zero
    retained rank, and non-finite residuals remain hard failures.
    """
    stability_state = diagnostics.get("stability_state")
    if stability_state == "stable":
        return True
    if stability_state != "stabilized":
        return False
    retained_rank = int(diagnostics.get("retained_rank", 0) or 0)
    if retained_rank < 1:
        return False
    relative_residual = _stabilized_relative_residual(diagnostics)
    if relative_residual is None:
        return False
    return relative_residual <= _STABILIZED_DIAGNOSTIC_RELATIVE_RESIDUAL_LIMIT


def accept_basis_candidate(
    candidate: np.ndarray,
    *,
    basis: list[np.ndarray],
    orthonormal_basis: list[np.ndarray],
    overlap_threshold: float,
) -> float | None:
    """Append a normalized candidate when it adds a new independent direction."""
    vector = np.asarray(candidate, dtype=complex).reshape(-1)
    norm = float(np.linalg.norm(vector))
    if not np.isfinite(norm) or norm == 0.0:
        return None

    normalized = vector / norm
    residual = normalized.copy()
    for basis_vector in orthonormal_basis:
        residual -= np.vdot(basis_vector, residual) * basis_vector

    residual_norm = float(np.linalg.norm(residual))
    if orthonormal_basis and residual_norm <= overlap_threshold:
        return None

    if not np.isfinite(residual_norm):
        return None
    basis.append(normalized)
    if residual_norm == 0.0:
        orthonormal_basis.append(normalized)
        return 0.0

    orthonormal_basis.append(residual / residual_norm)
    return residual_norm


def orthonormalize_candidate(
    candidate: np.ndarray,
    basis: list[np.ndarray],
) -> tuple[np.ndarray | None, float]:
    """Return a normalized candidate after projection against an orthonormal basis."""
    vector = np.asarray(candidate, dtype=complex).copy()
    for basis_vector in basis:
        vector -= np.vdot(basis_vector, vector) * basis_vector
    norm = float(np.linalg.norm(vector))
    if not np.isfinite(norm) or norm == 0.0:
        return None, norm
    return vector / norm, norm


def orthonormalize_columns(
    basis_matrix: np.ndarray,
    *,
    rank_tolerance: float = 1e-10,
) -> tuple[np.ndarray, int]:
    """Return the numerical-rank QR basis for a column-basis matrix."""
    basis = np.asarray(basis_matrix, dtype=complex)
    if basis.ndim != 2 or basis.shape[1] < 1:
        raise ValueError("basis_matrix must have at least one column")
    q_matrix, r_matrix = np.linalg.qr(basis)
    diag = np.abs(np.diag(r_matrix)) if r_matrix.size else np.array([], dtype=float)
    rank = int(np.sum(diag > rank_tolerance))
    if rank < 1:
        raise ValueError("projected basis has zero numerical rank")
    return q_matrix[:, :rank], rank


def overlap_diagnostics(
    basis_matrix: np.ndarray,
    *,
    regularization: float = 1e-8,
) -> dict[str, Any]:
    """Return condition diagnostics for an unorthogonalized projected basis."""
    basis = np.asarray(basis_matrix, dtype=complex)
    overlap = basis.conj().T @ basis
    return overlap_matrix_diagnostics(overlap, regularization=regularization)


def overlap_matrix_diagnostics(
    overlap_matrix: np.ndarray,
    *,
    regularization: float = 1e-8,
) -> dict[str, Any]:
    """Return condition diagnostics for an already-built overlap matrix."""
    overlap = np.asarray(overlap_matrix, dtype=complex)
    overlap = 0.5 * (overlap + overlap.conj().T)
    eigvals = np.linalg.eigvalsh(overlap)
    singular_values = np.linalg.svd(overlap, compute_uv=False)
    if singular_values.size == 0 or singular_values[-1] <= 0.0:
        condition = float("inf")
    else:
        condition = float(singular_values[0] / singular_values[-1])
    min_eigenvalue = float(np.min(eigvals).real) if eigvals.size else 0.0
    max_eigenvalue = float(np.max(eigvals).real) if eigvals.size else 0.0
    return {
        "overlap_condition": condition,
        "overlap_min_eigenvalue": min_eigenvalue,
        "overlap_max_eigenvalue": max_eigenvalue,
        "stability_state": (
            "stable"
            if np.isfinite(condition)
            and condition <= _HARDWARE_OVERLAP_CONDITION_LIMIT
            and min_eigenvalue > 0.0
            else "invalid"
        ),
        "regularization": float(regularization),
    }


def solve_action_subspace(
    action: HamiltonianAction,
    basis_matrix: np.ndarray,
    *,
    residual_tolerance: float,
    regularization: float = 1e-8,
) -> tuple[np.ndarray, np.ndarray, dict[str, float], dict[str, float], np.ndarray | None]:
    """Solve the lowest projected eigensystem for a matrix-free Hamiltonian action."""
    orthonormal_basis, rank = orthonormalize_columns(basis_matrix)
    projected = action.project(orthonormal_basis)
    raw_eigenvalues, raw_eigenvectors = np.linalg.eigh(projected)
    order = np.argsort(np.real_if_close(raw_eigenvalues).astype(float))
    eigenvalues = np.real_if_close(raw_eigenvalues[order]).astype(float)
    eigenvectors = raw_eigenvectors[:, order]
    residual_diagnostics, ritz_state = action.residual_diagnostics(
        orthonormal_basis,
        residual_tolerance=residual_tolerance,
    )
    residual_diagnostics["basis_numerical_rank"] = float(rank)
    diagnostics = overlap_diagnostics(basis_matrix, regularization=regularization)
    return eigenvalues, eigenvectors, diagnostics, residual_diagnostics, ritz_state
