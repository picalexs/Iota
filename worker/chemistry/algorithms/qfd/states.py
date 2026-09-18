"""Time-grid state and progress helpers for the QFD algorithm package."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np

from worker.chemistry.eigensolver import solve_generalized_eigenproblem
from worker.chemistry.hamiltonian_action import HamiltonianAction
from worker.chemistry.overlap import build_overlap_matrix
from worker.chemistry.progress import ProgressCallback
from worker.chemistry.projected_energy import generalized_projected_ground_energy
from worker.chemistry.state_vectors import normalize_state_vector
from worker.chemistry.time_evolution import (
    aer_pauli_time_evolution_state,
    exact_time_evolution_state_from_spectrum,
)


def build_sector_qfd_states(
    action: HamiltonianAction,
    reference_state: np.ndarray,
    time_grid: np.ndarray,
    *,
    max_time: float,
    time_grid_type: str,
    progress_callback: ProgressCallback | None,
    normalize_state_fn: Callable[..., np.ndarray] = normalize_state_vector,
    overlap_builder_fn: Callable[..., np.ndarray] = build_overlap_matrix,
    eigensolver_fn: Callable[..., tuple[np.ndarray, Any]] = solve_generalized_eigenproblem,
) -> list[np.ndarray]:
    """Build QFD time-grid states inside the fixed electron sector."""
    reference = normalize_state_fn(
        reference_state,
        error_message="QFD sector reference state must be non-zero",
    )

    states: list[np.ndarray] = []
    total = len(time_grid)
    for index, time_point in enumerate(time_grid, start=1):
        state = (
            reference.copy()
            if np.isclose(time_point, 0.0)
            else action.time_evolve(
                reference,
                time_point=float(time_point),
            )
        )
        norm = float(np.linalg.norm(state))
        if np.isclose(norm, 0.0):
            continue
        states.append(state / norm)

        if len(states) == 1:
            partial_energy: float | None = action.expectation(states[0])
        else:
            partial_matrix = np.column_stack(states)
            partial_h = action.project(partial_matrix)
            partial_s = overlap_builder_fn(states)
            partial_eigs, _ = eigensolver_fn(partial_h, partial_s)
            partial_energy = float(partial_eigs[0]) if partial_eigs.size else None
        if progress_callback is not None:
            progress_callback(
                {
                    "algorithm": "qfd",
                    "stage": "progress",
                    "step": "time_evolution",
                    "iteration": index,
                    "completed_iterations": len(states),
                    "total_iterations": total,
                    "energy": partial_energy,
                    "time_point": float(time_point),
                    "max_time": float(max_time),
                    "time_grid_type": time_grid_type,
                    "time_evolution_backend": "sector_matrix_free",
                    "implemented_evolution_method": "sector_expm_multiply",
                    "sector_dimension": action.dimension,
                }
            )

    if not states:
        states.append(reference)
    return states


def evolve_dense_qfd_state(
    *,
    evolution_context: Any,
    time_point: float,
    aer_time_evolution_fn: Callable[..., np.ndarray] = aer_pauli_time_evolution_state,
    exact_time_evolution_fn: Callable[..., np.ndarray] = exact_time_evolution_state_from_spectrum,
) -> np.ndarray:
    """Evolve the QFD reference state to one time point."""
    if np.isclose(time_point, 0.0):
        return evolution_context.reference_state
    if evolution_context.use_aer:
        return aer_time_evolution_fn(
            evolution_context.hamiltonian,
            evolution_context.reference_state,
            time_step=time_point,
            trotter_steps=evolution_context.trotter_steps,
            context=evolution_context.backend_context,
        )
    if evolution_context.eigenvalues is None or evolution_context.eigenvectors is None:
        raise RuntimeError("QFD exact evolution spectrum was not prepared")
    return exact_time_evolution_fn(
        evolution_context.eigenvalues,
        evolution_context.eigenvectors,
        evolution_context.reference_state,
        time_step=time_point,
        state_projection=evolution_context.reference_projection,
    )


def dense_qfd_partial_energy(
    operator: np.ndarray,
    dense_states: list[np.ndarray],
    *,
    projected_ground_energy_fn: Callable[..., float | None] = generalized_projected_ground_energy,
    overlap_builder_fn: Callable[..., np.ndarray] = build_overlap_matrix,
    eigensolver_fn: Callable[..., tuple[np.ndarray, Any]] = solve_generalized_eigenproblem,
) -> float | None:
    """Return the current dense projected ground estimate for progress reporting."""
    return projected_ground_energy_fn(
        operator,
        dense_states,
        direct_single_state=True,
        overlap_builder=overlap_builder_fn,
        eigensolver=eigensolver_fn,
    )


def emit_dense_qfd_progress(
    *,
    progress_callback: ProgressCallback | None,
    index: int,
    total_iterations: int,
    partial_energy: float | None,
    time_point: float,
    max_time: float,
    time_grid_type: str,
    use_aer: bool,
    trotter_steps: int,
) -> None:
    """Emit dense QFD time-evolution progress."""
    if progress_callback is None:
        return
    progress_callback(
        {
            "algorithm": "qfd",
            "stage": "progress",
            "step": "time_evolution",
            "iteration": index,
            "completed_iterations": index,
            "total_iterations": total_iterations,
            "energy": partial_energy,
            "time_point": time_point,
            "max_time": float(max_time),
            "time_grid_type": time_grid_type,
            "time_evolution_backend": "aer_simulator" if use_aer else "dense_matrix",
            "aer_trotter_steps": trotter_steps if use_aer else None,
        }
    )


def build_dense_qfd_states(
    *,
    evolution_context: Any,
    time_grid: np.ndarray,
    num_time_points: int,
    max_time: float,
    time_grid_type: str,
    progress_callback: ProgressCallback | None,
    evolve_state_fn: Callable[..., np.ndarray] = evolve_dense_qfd_state,
    partial_energy_fn: Callable[..., float | None] = dense_qfd_partial_energy,
    emit_progress_fn: Callable[..., None] = emit_dense_qfd_progress,
) -> list[np.ndarray]:
    """Build dense QFD time-grid states and emit live progress."""
    dense_states: list[np.ndarray] = []
    for index, time_point in enumerate(time_grid, start=1):
        dense_states.append(
            evolve_state_fn(
                evolution_context=evolution_context,
                time_point=float(time_point),
            )
        )
        partial_energy = partial_energy_fn(evolution_context.operator, dense_states)
        emit_progress_fn(
            progress_callback=progress_callback,
            index=index,
            total_iterations=num_time_points,
            partial_energy=partial_energy,
            time_point=float(time_point),
            max_time=max_time,
            time_grid_type=time_grid_type,
            use_aer=evolution_context.use_aer,
            trotter_steps=evolution_context.trotter_steps,
        )
    return dense_states


__all__ = [
    "build_dense_qfd_states",
    "build_sector_qfd_states",
    "dense_qfd_partial_energy",
    "emit_dense_qfd_progress",
    "evolve_dense_qfd_state",
]
