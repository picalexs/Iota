"""Dense and sector Krylov-extension kernels for the SKQD algorithm package."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np

from worker.chemistry.eigensolver import projected_ritz_diagnostics
from worker.chemistry.hamiltonian_action import HamiltonianAction
from worker.chemistry.progress import ProgressCallback
from worker.chemistry.projected_energy import (
    matrix_free_projected_ground_energy,
    orthonormal_projected_ground_energy,
)
from worker.chemistry.projected_subspace import (
    orthonormalize_candidate,
    solve_action_subspace,
)
from worker.chemistry.time_evolution import (
    exact_time_evolution_state_from_spectrum,
    prepare_exact_time_evolution,
)

DenseProgressEmitter = Callable[..., None]
DenseOrthonormalizer = Callable[[np.ndarray, list[np.ndarray]], tuple[np.ndarray | None, float]]
DensePartialEnergy = Callable[[np.ndarray, list[np.ndarray]], float | None]
SectorPartialEnergy = Callable[..., float | None]


def build_krylov_extension(
    operator: np.ndarray,
    *,
    reference_state: np.ndarray,
    seeded_from_sqd: bool,
    target_rank: int,
    time_step: float,
    residual_tolerance: float,
    progress_callback: ProgressCallback | None,
    orthonormalize_fn: DenseOrthonormalizer = orthonormalize_candidate,
    partial_energy_fn: DensePartialEnergy = orthonormal_projected_ground_energy,
    prepare_spectrum_fn: Callable[
        [np.ndarray], tuple[np.ndarray, np.ndarray]
    ] = prepare_exact_time_evolution,
    evolve_state_fn: Callable[..., np.ndarray] = exact_time_evolution_state_from_spectrum,
    emit_progress_fn: DenseProgressEmitter | None = None,
    projected_ritz_diagnostics_fn: Callable[..., dict[str, float]] = projected_ritz_diagnostics,
) -> tuple[np.ndarray, int, dict[str, float], np.ndarray | None]:
    """Build a dense SKQD Krylov subspace and solve its projected problem."""
    basis: list[np.ndarray] = []
    spectrum = prepare_spectrum_fn(operator)
    seed_projection = spectrum[1].conj().T @ np.asarray(reference_state, dtype=complex)

    for step in range(target_rank):
        current_time = float(step * time_step)
        if np.isclose(current_time, 0.0):
            candidate = np.asarray(reference_state, dtype=complex)
        else:
            candidate = evolve_state_fn(
                spectrum[0],
                spectrum[1],
                reference_state,
                time_step=current_time,
                state_projection=seed_projection,
            )
        basis_vector, candidate_norm = orthonormalize_fn(candidate, basis)
        if basis_vector is None:
            break

        basis.append(basis_vector)
        partial_energy = partial_energy_fn(operator, basis)
        if emit_progress_fn is not None:
            emit_progress_fn(
                progress_callback=progress_callback,
                iteration=step + 1,
                completed_iterations=len(basis),
                energy=partial_energy,
                total_iterations=target_rank,
                candidate_norm=candidate_norm,
                seeded_from_sqd=seeded_from_sqd,
            )

    if not basis:
        basis.append(np.asarray(reference_state, dtype=complex))

    basis_matrix = np.column_stack(basis)
    q_matrix, r_matrix = np.linalg.qr(basis_matrix)
    diag = np.abs(np.diag(r_matrix)) if r_matrix.size else np.array([], dtype=float)
    rank = int(np.sum(diag > 1e-10))
    if rank < 1:
        raise ValueError("SKQD projected basis has zero numerical rank")

    orthonormal_basis = q_matrix[:, :rank]
    projected = orthonormal_basis.conj().T @ operator @ orthonormal_basis
    projected = 0.5 * (projected + projected.conj().T)
    raw_eigenvalues, raw_eigenvectors = np.linalg.eigh(projected)
    order = np.argsort(np.real_if_close(raw_eigenvalues).astype(float))
    eigenvalues = np.real_if_close(raw_eigenvalues[order]).astype(float)
    ground_state = None
    if raw_eigenvectors.size:
        ground_state = orthonormal_basis @ raw_eigenvectors[:, order[0]]
        ground_norm = float(np.linalg.norm(ground_state))
        if not np.isclose(ground_norm, 0.0):
            ground_state = ground_state / ground_norm
    residual_diagnostics = projected_ritz_diagnostics_fn(
        operator,
        orthonormal_basis,
        residual_tolerance=residual_tolerance,
    )
    return eigenvalues, rank, residual_diagnostics, ground_state


def build_sector_krylov_extension(
    action: HamiltonianAction,
    *,
    reference_state: np.ndarray,
    seeded_from_sqd: bool,
    target_rank: int,
    time_step: float,
    residual_tolerance: float,
    progress_callback: ProgressCallback | None,
    orthonormalize_fn: DenseOrthonormalizer = orthonormalize_candidate,
    partial_energy_fn: SectorPartialEnergy = matrix_free_projected_ground_energy,
    solve_action_subspace_fn: Callable[..., tuple[Any, ...]] = solve_action_subspace,
    emit_progress_fn: DenseProgressEmitter | None = None,
) -> tuple[np.ndarray, int, dict[str, float], np.ndarray | None]:
    """Build a fixed-particle-sector SKQD Krylov extension."""
    basis: list[np.ndarray] = []

    for step in range(target_rank):
        current_time = float(step * time_step)
        candidate = (
            reference_state.copy()
            if np.isclose(current_time, 0.0)
            else action.time_evolve(reference_state, time_point=current_time)
        )
        basis_vector, candidate_norm = orthonormalize_fn(candidate, basis)
        if basis_vector is None:
            break

        basis.append(basis_vector)
        partial_energy = partial_energy_fn(
            action,
            basis,
            residual_tolerance=residual_tolerance,
        )
        if emit_progress_fn is not None:
            emit_progress_fn(
                progress_callback=progress_callback,
                iteration=step + 1,
                completed_iterations=len(basis),
                energy=partial_energy,
                total_iterations=target_rank,
                candidate_norm=candidate_norm,
                seeded_from_sqd=seeded_from_sqd,
                execution_mode="sector_matrix_free",
            )

    if not basis:
        basis.append(reference_state)

    basis_matrix = np.column_stack(basis)
    eigenvalues, _, _, residual_diagnostics, ground_state = solve_action_subspace_fn(
        action,
        basis_matrix,
        residual_tolerance=residual_tolerance,
    )
    basis_rank = int(residual_diagnostics["basis_numerical_rank"])
    return eigenvalues, basis_rank, residual_diagnostics, ground_state


def emit_skqd_krylov_progress(
    *,
    progress_callback: ProgressCallback | None,
    iteration: int,
    completed_iterations: int,
    energy: float | None,
    total_iterations: int,
    candidate_norm: float,
    seeded_from_sqd: bool,
    execution_mode: str | None = None,
) -> None:
    """Emit SKQD Krylov-extension progress events."""
    if progress_callback is None:
        return
    payload: dict[str, Any] = {
        "algorithm": "skqd",
        "stage": "progress",
        "step": "krylov_extension",
        "iteration": iteration,
        "completed_iterations": completed_iterations,
        "energy": energy,
        "total_iterations": total_iterations,
        "candidate_norm": candidate_norm,
        "seeded_from_sqd_occupancies": seeded_from_sqd,
    }
    if execution_mode is not None:
        payload["execution_mode"] = execution_mode
    progress_callback(payload)


__all__ = [
    "build_krylov_extension",
    "build_sector_krylov_extension",
    "emit_skqd_krylov_progress",
]
