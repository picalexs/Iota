"""Krylov-basis construction helpers for the KQD algorithm package."""

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
    is_zero_time,
    prepare_exact_time_evolution,
    trotterized_time_evolution_state,
)


def prepare_dense_krylov_spectrum(
    *,
    operator_matrix: np.ndarray,
    reference: np.ndarray,
    evolution_method: str,
    use_aer: bool,
    prepare_exact_time_evolution_fn: Callable[..., tuple[np.ndarray, np.ndarray]] = (
        prepare_exact_time_evolution
    ),
) -> tuple[np.ndarray | None, np.ndarray | None, np.ndarray | None]:
    """Prepare exact dense evolution data when KQD can reuse it."""
    if evolution_method != "exact":
        return None, None, None
    eigenvalues, eigenvectors = prepare_exact_time_evolution_fn(operator_matrix)
    return eigenvalues, eigenvectors, eigenvectors.conj().T @ reference


def evolve_dense_krylov_state(
    *,
    hamiltonian: object,
    operator_matrix: np.ndarray,
    reference: np.ndarray,
    time_point: float,
    evolution_method: str,
    use_aer: bool,
    trotter_steps: int,
    eigenvalues: np.ndarray | None,
    eigenvectors: np.ndarray | None,
    reference_projection: np.ndarray | None,
    backend_context: Any | None,
    **evolution_dependencies: Any,
) -> np.ndarray:
    """Evolve the KQD reference state to one Krylov time point."""
    aer_time_evolution_fn = evolution_dependencies.get(
        "aer_time_evolution_fn", aer_pauli_time_evolution_state
    )
    exact_time_evolution_fn = evolution_dependencies.get(
        "exact_time_evolution_fn", exact_time_evolution_state_from_spectrum
    )
    trotterized_time_evolution_fn = evolution_dependencies.get(
        "trotterized_time_evolution_fn", trotterized_time_evolution_state
    )
    if is_zero_time(time_point):
        return reference.copy()
    if evolution_method == "exact":
        if eigenvalues is None or eigenvectors is None:
            raise RuntimeError("KQD exact evolution spectrum was not prepared")
        return exact_time_evolution_fn(
            eigenvalues,
            eigenvectors,
            reference,
            time_step=time_point,
            state_projection=reference_projection,
        )
    if use_aer:
        return aer_time_evolution_fn(
            hamiltonian,
            reference,
            time_step=time_point,
            trotter_steps=trotter_steps,
            context=backend_context,
        )
    return trotterized_time_evolution_fn(
        operator_matrix,
        reference,
        time_step=time_point,
        trotter_steps=trotter_steps,
    )


def dense_krylov_partial_energy(
    operator_matrix: np.ndarray,
    basis: list[np.ndarray],
    *,
    projected_ground_energy_fn: Callable[..., float | None] = generalized_projected_ground_energy,
    overlap_builder: Callable[..., np.ndarray] = build_overlap_matrix,
    eigensolver: Callable[..., tuple[np.ndarray, Any]] = solve_generalized_eigenproblem,
) -> float | None:
    """Return the current dense projected ground estimate for KQD progress."""
    return projected_ground_energy_fn(
        operator_matrix,
        basis,
        overlap_builder=overlap_builder,
        eigensolver=eigensolver,
    )


def sector_krylov_partial_energy(
    action: HamiltonianAction,
    basis: list[np.ndarray],
    *,
    overlap_builder: Callable[..., np.ndarray] = build_overlap_matrix,
    eigensolver: Callable[..., tuple[np.ndarray, Any]] = solve_generalized_eigenproblem,
) -> float | None:
    """Return the current sector projected ground estimate for KQD progress."""
    partial_basis_matrix = np.column_stack(basis)
    partial_h = action.project(partial_basis_matrix)
    partial_s = overlap_builder(basis)
    partial_ritz, _ = eigensolver(partial_h, partial_s)
    return float(partial_ritz[0]) if partial_ritz.size else None


def emit_dense_krylov_progress(
    *,
    progress_callback: ProgressCallback | None,
    iteration: int,
    completed_iterations: int,
    total_iterations: int,
    partial_ground: float | None,
    candidate_norm: float,
    evolution_method: str,
    time_point: float,
    time_step: float,
    trotter_steps: int,
    use_aer: bool,
) -> None:
    """Emit dense KQD time-evolution progress."""
    if progress_callback is None:
        return
    progress_callback(
        {
            "algorithm": "kqd",
            "stage": "progress",
            "step": "time_evolution",
            "iteration": iteration,
            "completed_iterations": completed_iterations,
            "total_iterations": total_iterations,
            "energy": partial_ground,
            "candidate_norm": candidate_norm,
            "evolution_method": evolution_method,
            "time_evolution_backend": "aer_simulator" if use_aer else "dense_matrix",
            "time_point": time_point,
            "time_step": time_step,
            "trotter_steps": trotter_steps,
        }
    )


def emit_sector_krylov_progress(
    *,
    progress_callback: ProgressCallback | None,
    iteration: int,
    completed_iterations: int,
    total_iterations: int,
    partial_ground: float | None,
    candidate_norm: float,
    evolution_method: str,
    time_point: float,
    time_step: float,
    trotter_steps: int,
    sector_dimension: int,
    implemented_evolution_method: str = "sector_expm_multiply",
) -> None:
    """Emit sector KQD time-evolution progress."""
    if progress_callback is None:
        return
    progress_callback(
        {
            "algorithm": "kqd",
            "stage": "progress",
            "step": "time_evolution",
            "iteration": iteration,
            "completed_iterations": completed_iterations,
            "total_iterations": total_iterations,
            "energy": partial_ground,
            "candidate_norm": candidate_norm,
            "evolution_method": evolution_method,
            "implemented_evolution_method": implemented_evolution_method,
            "time_evolution_backend": "sector_matrix_free",
            "time_point": time_point,
            "time_step": time_step,
            "trotter_steps": trotter_steps,
            "sector_dimension": sector_dimension,
        }
    )


def build_krylov_basis(
    hamiltonian: object,
    operator_matrix: np.ndarray,
    reference_state: np.ndarray,
    *,
    target_rank: int,
    evolution_method: str,
    time_step: float,
    trotter_steps: int,
    progress_callback: ProgressCallback | None,
    backend_context: Any | None = None,
    **basis_dependencies: Any,
) -> list[np.ndarray]:
    """Build a Krylov basis from real-time evolved reference states."""
    normalize_reference_fn = basis_dependencies.get("normalize_reference_fn", normalize_state_vector)
    prepare_spectrum_fn = basis_dependencies.get(
        "prepare_spectrum_fn", prepare_dense_krylov_spectrum
    )
    evolve_state_fn = basis_dependencies.get("evolve_state_fn", evolve_dense_krylov_state)
    partial_energy_fn = basis_dependencies.get("partial_energy_fn", dense_krylov_partial_energy)
    emit_progress_fn = basis_dependencies.get("emit_progress_fn", emit_dense_krylov_progress)
    basis: list[np.ndarray] = []
    reference = normalize_reference_fn(
        reference_state,
        error_message="KQD reference state must be non-zero",
    )
    use_aer = getattr(backend_context, "backend_target", None) == "aer_simulator"
    eigenvalues, eigenvectors, reference_projection = prepare_spectrum_fn(
        operator_matrix=operator_matrix,
        reference=reference,
        evolution_method=evolution_method,
        use_aer=use_aer,
    )
    for step in range(target_rank):
        time_point = float(step * time_step)
        vector = evolve_state_fn(
            hamiltonian=hamiltonian,
            operator_matrix=operator_matrix,
            reference=reference,
            time_point=time_point,
            evolution_method=evolution_method,
            use_aer=use_aer,
            trotter_steps=trotter_steps,
            eigenvalues=eigenvalues,
            eigenvectors=eigenvectors,
            reference_projection=reference_projection,
            backend_context=backend_context,
        )
        norm = float(np.linalg.norm(vector))
        if np.isclose(norm, 0.0):
            continue

        basis.append(vector / norm)
        partial_ground = partial_energy_fn(operator_matrix, basis)
        emit_progress_fn(
            progress_callback=progress_callback,
            iteration=step + 1,
            completed_iterations=len(basis),
            total_iterations=target_rank,
            partial_ground=partial_ground,
            candidate_norm=norm,
            evolution_method=evolution_method,
            time_point=time_point,
            time_step=time_step,
            trotter_steps=trotter_steps,
            use_aer=use_aer and evolution_method != "exact",
        )

    if not basis:
        basis.append(reference)

    return basis


def build_sector_krylov_basis(
    action: HamiltonianAction,
    reference_state: np.ndarray,
    *,
    target_rank: int,
    evolution_method: str,
    time_step: float,
    trotter_steps: int,
    progress_callback: ProgressCallback | None,
    normalize_reference_fn: Callable[..., np.ndarray] = normalize_state_vector,
    partial_energy_fn: Callable[..., float | None] = sector_krylov_partial_energy,
    emit_progress_fn: Callable[..., None] = emit_sector_krylov_progress,
) -> list[np.ndarray]:
    """Build a Krylov basis inside the fixed electron sector."""
    basis: list[np.ndarray] = []
    reference = normalize_reference_fn(
        reference_state,
        error_message="KQD sector reference state must be non-zero",
    )
    sector_matrix: np.ndarray | None = None
    if evolution_method == "trotter":
        to_matrix = getattr(action, "to_matrix", None)
        if not callable(to_matrix):
            raise ValueError(
                "KQD sector Trotter evolution requires a materializable sector Hamiltonian"
            )
        sector_matrix = np.asarray(to_matrix(), dtype=complex)

    for step in range(target_rank):
        time_point = float(step * time_step)
        if is_zero_time(time_point):
            vector = reference.copy()
        elif evolution_method == "exact":
            vector = action.time_evolve(reference, time_point=time_point)
        else:
            assert sector_matrix is not None
            vector = trotterized_time_evolution_state(
                sector_matrix,
                reference,
                time_step=time_point,
                trotter_steps=trotter_steps,
            )
        norm = float(np.linalg.norm(vector))
        if np.isclose(norm, 0.0):
            continue

        basis.append(vector / norm)
        partial_ground = partial_energy_fn(action, basis)
        emit_progress_fn(
            progress_callback=progress_callback,
            iteration=step + 1,
            completed_iterations=len(basis),
            total_iterations=target_rank,
            partial_ground=partial_ground,
            candidate_norm=norm,
            evolution_method=evolution_method,
            time_point=time_point,
            time_step=time_step,
            trotter_steps=trotter_steps,
            sector_dimension=action.dimension,
            implemented_evolution_method=(
                "sector_expm_multiply"
                if evolution_method == "exact"
                else "sector_diagonal_residual_trotter"
            ),
        )

    if not basis:
        basis.append(reference)

    return basis


__all__ = [
    "build_krylov_basis",
    "build_sector_krylov_basis",
    "dense_krylov_partial_energy",
    "emit_dense_krylov_progress",
    "emit_sector_krylov_progress",
    "evolve_dense_krylov_state",
    "prepare_dense_krylov_spectrum",
    "sector_krylov_partial_energy",
]
