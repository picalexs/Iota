"""Shared linear algebra helpers for worker chemistry solvers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from worker.chemistry.operator_matrices import (
    clear_operator_matrix_cache as _clear_operator_matrix_cache,
)
from worker.chemistry.operator_matrices import (
    operator_matrix_cache_info as _operator_matrix_cache_info,
)
from worker.chemistry.operator_matrices import resolve_operator_matrix as _resolve_operator_matrix
from worker.chemistry.projected_subspace import overlap_matrix_diagnostics
from worker.chemistry.reference_states import (
    build_hf_reference_state as _build_hf_reference_state,
)
from worker.chemistry.reference_states import build_reference_state as _build_reference_state

_NOISY_PROJECTED_OVERLAP_CONDITION_LIMIT = 1e3

# Keep historical eigensolver imports available while implementations live in
# focused chemistry modules.
build_hf_reference_state = _build_hf_reference_state
build_reference_state = _build_reference_state
clear_operator_matrix_cache = _clear_operator_matrix_cache
operator_matrix_cache_info = _operator_matrix_cache_info
resolve_operator_matrix = _resolve_operator_matrix


@dataclass(frozen=True)
class StabilizedGeneralizedEigenproblemResult:
    """Diagnostics-rich retained-subspace solve for noisy projected problems."""

    eigenvalues: np.ndarray
    raw_eigenvalues: np.ndarray
    diagnostics: dict[str, Any]


def _validate_projected_matrices(
    hamiltonian_matrix: np.ndarray,
    overlap_matrix: np.ndarray,
    *,
    solver_name: str,
) -> tuple[np.ndarray, np.ndarray]:
    """Return finite equal square projected matrices or raise a hard failure."""
    hamiltonian = np.asarray(hamiltonian_matrix, dtype=complex)
    overlap = np.asarray(overlap_matrix, dtype=complex)
    if (
        hamiltonian.ndim != 2
        or overlap.ndim != 2
        or hamiltonian.shape[0] != hamiltonian.shape[1]
        or overlap.shape != hamiltonian.shape
    ):
        raise ValueError(f"{solver_name} matrices must be equal square matrices")
    if not np.all(np.isfinite(hamiltonian)) or not np.all(np.isfinite(overlap)):
        raise ValueError(f"{solver_name} matrices must contain only finite values")
    return hamiltonian, overlap


def solve_exact_generalized_eigenproblem(
    hamiltonian_matrix: np.ndarray,
    overlap_matrix: np.ndarray,
    *,
    rank_tolerance: float = 1e-10,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Solve an exact projected problem with explicit metric rank handling."""
    eigenvalues, _eigenvectors, diagnostics = solve_exact_generalized_eigensystem(
        hamiltonian_matrix,
        overlap_matrix,
        rank_tolerance=rank_tolerance,
    )
    return eigenvalues, diagnostics


def solve_exact_generalized_eigensystem(
    hamiltonian_matrix: np.ndarray,
    overlap_matrix: np.ndarray,
    *,
    rank_tolerance: float = 1e-10,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Solve an exact Hermitian generalized eigensystem with metric diagnostics.

    The returned coefficient columns satisfy ``C.conj().T @ S @ C = I`` on
    the retained positive-overlap subspace.  Exact projected problems must not
    receive the noisy-path diagonal regularization; small metric modes are
    removed only after the raw matrices are assembled.
    """
    hamiltonian, overlap = _validate_projected_matrices(
        hamiltonian_matrix,
        overlap_matrix,
        solver_name="exact generalized eigenproblem",
    )
    if rank_tolerance <= 0.0:
        raise ValueError("rank_tolerance must be positive")

    hamiltonian_hermiticity_error = _relative_antihermitian_norm(hamiltonian)
    overlap_hermiticity_error = _relative_antihermitian_norm(overlap)
    hamiltonian = 0.5 * (hamiltonian + hamiltonian.conj().T)
    overlap = 0.5 * (overlap + overlap.conj().T)
    overlap_eigenvalues, overlap_eigenvectors = np.linalg.eigh(overlap)
    overlap_eigenvalues = np.real_if_close(overlap_eigenvalues).astype(float)
    scale = max(float(np.max(np.abs(overlap_eigenvalues), initial=0.0)), 1.0)
    threshold = float(rank_tolerance * scale)
    retained_mask = overlap_eigenvalues > threshold
    retained_eigenvalues = overlap_eigenvalues[retained_mask]
    retained_vectors = overlap_eigenvectors[:, retained_mask]
    raw_minimum = float(np.min(overlap_eigenvalues)) if overlap_eigenvalues.size else 0.0
    negative_metric = raw_minimum < -threshold
    raw_singular_values = np.linalg.svd(overlap, compute_uv=False)
    diagnostics: dict[str, Any] = {
        "stability_state": "invalid",
        "regularization": 0.0,
        "rank_tolerance": float(rank_tolerance),
        "threshold": threshold,
        "retained_rank": int(retained_eigenvalues.size),
        "dropped_rank": int(overlap_eigenvalues.size - retained_eigenvalues.size),
        "raw_overlap_min_eigenvalue": raw_minimum,
        "raw_overlap_max_eigenvalue": (
            float(np.max(overlap_eigenvalues)) if overlap_eigenvalues.size else 0.0
        ),
        "raw_overlap_condition": _condition_number_from_singular_values(raw_singular_values),
        "overlap_min_eigenvalue": (
            float(np.min(retained_eigenvalues)) if retained_eigenvalues.size else 0.0
        ),
        "overlap_max_eigenvalue": (
            float(np.max(retained_eigenvalues)) if retained_eigenvalues.size else 0.0
        ),
        "overlap_condition": _condition_number_from_eigenvalues(np.sort(retained_eigenvalues)),
        "hamiltonian_hermiticity_error": hamiltonian_hermiticity_error,
        "overlap_hermiticity_error": overlap_hermiticity_error,
        "overlap_psd": not negative_metric,
        "overlap_psd_min_eigenvalue": raw_minimum,
        "metric_normalization_error": None,
        "generalized_residual_norm": None,
        "relative_generalized_residual": None,
        "max_generalized_residual_norm": None,
        "max_relative_generalized_residual": None,
    }
    if negative_metric:
        diagnostics["metric_failure"] = "negative_overlap"
        return (
            np.asarray([], dtype=float),
            np.empty((hamiltonian.shape[0], 0), dtype=complex),
            diagnostics,
        )
    if retained_eigenvalues.size == 0:
        raise ValueError("exact generalized eigenproblem overlap has zero retained rank")

    whitening = retained_vectors @ np.diag(np.reciprocal(np.sqrt(retained_eigenvalues)))
    effective_hamiltonian = whitening.conj().T @ hamiltonian @ whitening
    effective_hamiltonian = 0.5 * (effective_hamiltonian + effective_hamiltonian.conj().T)
    eigenvalues, effective_eigenvectors = np.linalg.eigh(effective_hamiltonian)
    eigenvalues = np.real_if_close(eigenvalues).astype(float)
    generalized_eigenvectors = whitening @ effective_eigenvectors
    metric_identity = generalized_eigenvectors.conj().T @ overlap @ generalized_eigenvectors
    metric_error = float(np.linalg.norm(metric_identity - np.eye(metric_identity.shape[0])))
    residual_matrix = hamiltonian @ generalized_eigenvectors - overlap @ (
        generalized_eigenvectors * eigenvalues[np.newaxis, :]
    )
    residual_norms = np.linalg.norm(residual_matrix, axis=0)
    hamiltonian_state_norms = np.linalg.norm(hamiltonian @ generalized_eigenvectors, axis=0)
    overlap_state_norms = np.linalg.norm(overlap @ generalized_eigenvectors, axis=0)
    relative_residuals = residual_norms / np.maximum(
        1.0,
        hamiltonian_state_norms,
        np.abs(eigenvalues) * overlap_state_norms,
    )
    diagnostics["metric_normalization_error"] = metric_error
    diagnostics["generalized_residual_norm"] = float(residual_norms[0])
    diagnostics["relative_generalized_residual"] = float(relative_residuals[0])
    diagnostics["max_generalized_residual_norm"] = float(np.max(residual_norms))
    diagnostics["max_relative_generalized_residual"] = float(np.max(relative_residuals))
    diagnostics["stability_state"] = "stable" if diagnostics["dropped_rank"] == 0 else "invalid"
    return eigenvalues, generalized_eigenvectors, diagnostics


def _relative_antihermitian_norm(matrix: np.ndarray) -> float:
    """Return a scale-independent Hermiticity error for a square matrix."""
    denominator = max(1.0, float(np.linalg.norm(matrix)))
    return float(np.linalg.norm(matrix - matrix.conj().T) / denominator)


def solve_generalized_eigenproblem(
    hamiltonian_matrix: np.ndarray,
    overlap_matrix: np.ndarray,
    *,
    regularization: float = 1e-8,
) -> tuple[np.ndarray, dict[str, float]]:
    """Solve a small generalized Hermitian eigenproblem with regularization."""
    hamiltonian, overlap = _validate_projected_matrices(
        hamiltonian_matrix,
        overlap_matrix,
        solver_name="generalized eigenproblem",
    )

    hamiltonian = 0.5 * (hamiltonian + hamiltonian.conj().T)
    overlap = 0.5 * (overlap + overlap.conj().T)
    input_diagnostics = overlap_matrix_diagnostics(overlap, regularization=regularization)
    overlap = overlap + regularization * np.eye(overlap.shape[0], dtype=complex)

    overlap_eigvals, overlap_eigvecs = np.linalg.eigh(overlap)
    safe_eigvals = np.asarray(np.clip(overlap_eigvals, regularization, None), dtype=float)
    inv_sqrt = np.diag(np.reciprocal(np.sqrt(safe_eigvals)))
    whitening = overlap_eigvecs @ inv_sqrt @ overlap_eigvecs.conj().T
    effective_hamiltonian = whitening.conj().T @ hamiltonian @ whitening
    effective_hamiltonian = 0.5 * (effective_hamiltonian + effective_hamiltonian.conj().T)
    eigenvalues = np.linalg.eigvalsh(effective_hamiltonian)
    eigenvalues = np.sort(np.real_if_close(eigenvalues).astype(float))

    diagnostics: dict[str, Any] = dict(input_diagnostics)
    return eigenvalues, diagnostics


def _condition_number_from_singular_values(singular_values: np.ndarray) -> float:
    if singular_values.size == 0 or singular_values[-1] <= 0.0:
        return float("inf")
    return float(singular_values[0] / singular_values[-1])


def _condition_number_from_eigenvalues(eigenvalues: np.ndarray) -> float:
    if eigenvalues.size == 0:
        return float("inf")
    positive = np.asarray(eigenvalues[eigenvalues > 0.0], dtype=float)
    if positive.size == 0 or positive[0] <= 0.0:
        return float("inf")
    return float(positive[-1] / positive[0])


def solve_stabilized_generalized_eigenproblem(
    hamiltonian_matrix: np.ndarray,
    overlap_matrix: np.ndarray,
    *,
    regularization: float = 1e-8,
    max_standard_error: float | None = None,
) -> StabilizedGeneralizedEigenproblemResult:
    """Solve a noisy projected generalized eigenproblem on a retained PSD overlap subspace."""
    hamiltonian, overlap = _validate_projected_matrices(
        hamiltonian_matrix,
        overlap_matrix,
        solver_name="stabilized generalized eigenproblem",
    )

    hamiltonian = 0.5 * (hamiltonian + hamiltonian.conj().T)
    overlap = 0.5 * (overlap + overlap.conj().T)

    raw_eigenvalues, _ = solve_generalized_eigenproblem(
        hamiltonian,
        overlap,
        regularization=regularization,
    )
    overlap_eigvals, overlap_eigvecs = np.linalg.eigh(overlap)
    overlap_eigvals = np.real_if_close(overlap_eigvals).astype(float)
    psd_overlap_eigvals = np.clip(overlap_eigvals, 0.0, None)
    overlap_max_eigenvalue = (
        float(np.max(psd_overlap_eigvals)) if psd_overlap_eigvals.size else float(regularization)
    )
    projected_floor = max(
        float(regularization),
        1e-6 * overlap_max_eigenvalue,
        overlap_max_eigenvalue / _NOISY_PROJECTED_OVERLAP_CONDITION_LIMIT,
    )
    threshold = projected_floor
    if isinstance(max_standard_error, (int, float)) and np.isfinite(float(max_standard_error)):
        threshold = max(threshold, 4.0 * float(max_standard_error))
        resolved_max_standard_error: float | None = float(max_standard_error)
        uncertainty_cutoff_method = "four_times_max_overlap_entry_standard_error_heuristic"
    else:
        resolved_max_standard_error = None
        uncertainty_cutoff_method = "regularization_and_condition_floor_only"

    retained_mask = psd_overlap_eigvals > threshold
    retained_eigvals = np.asarray(psd_overlap_eigvals[retained_mask], dtype=float)
    retained_vectors = overlap_eigvecs[:, retained_mask]

    raw_singular_values = np.linalg.svd(overlap, compute_uv=False)
    raw_overlap_condition = _condition_number_from_singular_values(raw_singular_values)
    psd_projected = bool(np.any(overlap_eigvals < 0.0))
    retained_rank = int(retained_eigvals.size)
    dropped_rank = int(psd_overlap_eigvals.size - retained_rank)
    projected_overlap_condition = _condition_number_from_eigenvalues(np.sort(retained_eigvals))
    projected_overlap_min = float(np.min(retained_eigvals)) if retained_rank else 0.0
    projected_overlap_max = float(np.max(retained_eigvals)) if retained_rank else 0.0

    diagnostics: dict[str, Any] = {
        "stability_state": "invalid",
        "raw_spectrum_definition": "regularized_unfiltered_generalized_spectrum",
        "psd_projected": psd_projected,
        "threshold": float(threshold),
        "raw_projected_rank": int(overlap_eigvals.size),
        "retained_rank": retained_rank,
        "stabilized_projected_rank": retained_rank,
        "dropped_rank": dropped_rank,
        "raw_overlap_min_eigenvalue": float(np.min(overlap_eigvals))
        if overlap_eigvals.size
        else 0.0,
        "projected_overlap_min_eigenvalue": projected_overlap_min,
        "raw_overlap_condition": raw_overlap_condition,
        "projected_overlap_condition": projected_overlap_condition,
        "stabilized_overlap_condition": projected_overlap_condition,
        "raw_overlap_max_eigenvalue": float(np.max(overlap_eigvals))
        if overlap_eigvals.size
        else 0.0,
        "projected_overlap_max_eigenvalue": projected_overlap_max,
        "max_standard_error": resolved_max_standard_error,
        "overlap_uncertainty_cutoff_method": uncertainty_cutoff_method,
        "overlap_uncertainty_is_matrix_level_bound": False,
        "regularization": float(regularization),
        "condition_limit": float(_NOISY_PROJECTED_OVERLAP_CONDITION_LIMIT),
        # Keep the common keys aligned with the retained projected solve.
        "overlap_condition": projected_overlap_condition,
        "overlap_min_eigenvalue": projected_overlap_min,
        "overlap_max_eigenvalue": projected_overlap_max,
        "projected_ritz_residual_norm": None,
        "relative_projected_ritz_residual": None,
        "stabilized_ritz_residual_norm": None,
        "stabilized_relative_ritz_residual": None,
    }
    if retained_rank == 0:
        raise ValueError("stabilized generalized eigenproblem overlap has zero retained rank")

    inv_sqrt = np.diag(np.reciprocal(np.sqrt(retained_eigvals)))
    whitening = retained_vectors @ inv_sqrt
    effective_hamiltonian = whitening.conj().T @ hamiltonian @ whitening
    effective_hamiltonian = 0.5 * (effective_hamiltonian + effective_hamiltonian.conj().T)
    retained_spectrum = np.sort(
        np.real_if_close(np.linalg.eigvalsh(effective_hamiltonian)).astype(float)
    )
    if retained_spectrum.size == 0 or not np.all(np.isfinite(retained_spectrum)):
        raise ValueError("stabilized generalized eigenproblem produced non-finite Ritz values")

    effective_eigenvalues, effective_eigenvectors = np.linalg.eigh(effective_hamiltonian)
    lowest_energy = float(np.real_if_close(effective_eigenvalues[0]))
    lowest_coefficients = whitening @ effective_eigenvectors[:, 0]
    projected_residual = hamiltonian @ lowest_coefficients - lowest_energy * (
        overlap @ lowest_coefficients
    )
    projected_residual_norm = float(np.linalg.norm(projected_residual))
    projected_hamiltonian_norm = float(np.linalg.norm(hamiltonian @ lowest_coefficients))
    projected_overlap_norm = float(np.linalg.norm(overlap @ lowest_coefficients))
    relative_projected_residual = projected_residual_norm / max(
        1.0,
        projected_hamiltonian_norm,
        abs(lowest_energy) * projected_overlap_norm,
    )
    diagnostics["projected_ritz_residual_norm"] = projected_residual_norm
    diagnostics["relative_projected_ritz_residual"] = float(relative_projected_residual)
    diagnostics["stabilized_ritz_residual_norm"] = projected_residual_norm
    diagnostics["stabilized_relative_ritz_residual"] = float(relative_projected_residual)

    diagnostics["stability_state"] = (
        "stable" if not psd_projected and dropped_rank == 0 else "stabilized"
    )
    return StabilizedGeneralizedEigenproblemResult(
        eigenvalues=retained_spectrum,
        raw_eigenvalues=raw_eigenvalues,
        diagnostics=diagnostics,
    )


def projected_ritz_diagnostics(
    operator_matrix: np.ndarray,
    basis_matrix: np.ndarray,
    *,
    residual_tolerance: float = 1e-6,
    rank_tolerance: float = 1e-10,
) -> dict[str, float]:
    """Return residual diagnostics for the lowest Ritz vector in a projected basis."""
    operator = np.asarray(operator_matrix, dtype=complex)
    basis = np.asarray(basis_matrix, dtype=complex)
    if basis.ndim != 2 or basis.shape[0] != operator.shape[0] or basis.shape[1] < 1:
        raise ValueError("basis_matrix shape is incompatible with operator_matrix")

    q_matrix, r_matrix = np.linalg.qr(basis)
    if r_matrix.size == 0:
        rank = 0
    else:
        diag = np.abs(np.diag(r_matrix))
        rank = int(np.sum(diag > rank_tolerance))

    if rank < 1:
        raise ValueError("projected basis has zero numerical rank")

    q_matrix = q_matrix[:, :rank]
    projected = q_matrix.conj().T @ operator @ q_matrix
    projected = 0.5 * (projected + projected.conj().T)
    eigenvalues, eigenvectors = np.linalg.eigh(projected)
    lowest_energy = float(np.real_if_close(eigenvalues[0]))
    ritz_state = q_matrix @ eigenvectors[:, 0]
    residual_vector = operator @ ritz_state - lowest_energy * ritz_state
    residual_norm = float(np.linalg.norm(residual_vector))
    operator_state_norm = float(np.linalg.norm(operator @ ritz_state))
    relative_residual = residual_norm / max(1.0, abs(lowest_energy), operator_state_norm)

    return {
        "ritz_energy": lowest_energy,
        "ritz_residual_norm": residual_norm,
        "relative_ritz_residual": float(relative_residual),
        "residual_convergence_threshold": float(residual_tolerance),
        "basis_numerical_rank": float(rank),
    }
