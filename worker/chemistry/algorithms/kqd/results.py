"""KQD result and completion-payload helpers for the algorithm package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from worker.chemistry.overlap import overlap_metrics
from worker.chemistry.progress import ProgressCallback
from worker.chemistry.projected_subspace import projected_convergence_reason
from worker.chemistry.types import KQDResult


@dataclass(frozen=True)
class KQDCompletionPayload:
    """Completed KQD progress values."""

    basis_rank: int
    primary_energy: float
    krylov_dim: int
    evolution_method: str
    time_evolution_backend: str
    time_step: float
    trotter_steps: int
    relative_residual: float
    residual_tolerance: float
    termination_reason: str
    matrix_element_strategy: Any
    min_ritz: float | None
    max_ritz: float | None
    overlap_condition: float
    stability_state: Any
    wall_seconds: float


def build_kqd_completion_payload(
    *,
    solve_data: Any,
    ritz_values: np.ndarray,
    diagnostics: dict[str, Any],
    matrix_element_summary: dict[str, Any],
    kqd_config: Any,
    primary_energy: float,
    time_evolution_backend: str,
    kqd_elapsed: float,
) -> KQDCompletionPayload:
    """Build the completed KQD progress payload object."""
    return KQDCompletionPayload(
        basis_rank=solve_data.basis_rank,
        primary_energy=primary_energy,
        krylov_dim=kqd_config.krylov_dim,
        evolution_method=kqd_config.evolution_method,
        time_evolution_backend=time_evolution_backend,
        time_step=kqd_config.time_step,
        trotter_steps=kqd_config.trotter_steps,
        relative_residual=solve_data.residual_diagnostics["relative_ritz_residual"],
        residual_tolerance=kqd_config.residual_tolerance,
        termination_reason=projected_convergence_reason(
            diagnostics,
            relative_residual=solve_data.residual_diagnostics["relative_ritz_residual"],
            residual_tolerance=kqd_config.residual_tolerance,
        ),
        matrix_element_strategy=matrix_element_summary.get("matrix_element_strategy"),
        min_ritz=float(ritz_values[0]) if ritz_values.size else None,
        max_ritz=float(ritz_values[-1]) if ritz_values.size else None,
        overlap_condition=float(diagnostics.get("overlap_condition", 0.0)),
        stability_state=diagnostics.get("stability_state"),
        wall_seconds=round(kqd_elapsed, 4),
    )


def emit_kqd_completion(
    progress_callback: ProgressCallback | None,
    payload: KQDCompletionPayload,
) -> None:
    """Emit a completed KQD progress event when a callback is configured."""
    if progress_callback is None:
        return
    diagnostic_only = (
        payload.stability_state != "stable" or payload.termination_reason != "converged"
    )
    progress_callback(
        {
            "algorithm": "kqd",
            "stage": "completed",
            "step": "solve",
            "iteration": payload.basis_rank,
            "energy": payload.primary_energy if not diagnostic_only else None,
            "diagnostic_energy": payload.primary_energy if diagnostic_only else None,
            "energy_state": "diagnostic" if diagnostic_only else "reportable",
            "convergence_iteration": payload.basis_rank,
            "completed_iterations": payload.basis_rank,
            "total_iterations": payload.basis_rank,
            "krylov_dim": payload.krylov_dim,
            "basis_rank": payload.basis_rank,
            "evolution_method": payload.evolution_method,
            "time_evolution_backend": payload.time_evolution_backend,
            "time_step": payload.time_step,
            "trotter_steps": payload.trotter_steps,
            "min_ritz": payload.min_ritz,
            "max_ritz": payload.max_ritz,
            "overlap_condition": payload.overlap_condition,
            "stability_state": payload.stability_state,
            "relative_residual": payload.relative_residual,
            "residual_tolerance": payload.residual_tolerance,
            "termination_reason": payload.termination_reason,
            "matrix_element_strategy": payload.matrix_element_strategy,
            "wall_seconds": payload.wall_seconds,
        }
    )


def build_kqd_result(
    *,
    solve_data: Any,
    ritz_values: np.ndarray,
    raw_ritz_values: np.ndarray,
    diagnostics: dict[str, Any],
    matrix_element_summary: dict[str, Any],
    converged: bool,
    kqd_config: Any,
    sector_dimension: int | None,
    circuit_artifacts: list[dict[str, Any]],
) -> KQDResult:
    """Build the public KQD result from completed projected-solve data."""
    if ritz_values.size == 0:
        raise ValueError("KQD projected solve produced no Ritz values")
    orthogonality = overlap_metrics(solve_data.overlap)
    orthogonality_metrics = {
        **orthogonality,
        "basis_rank": float(solve_data.basis_rank),
        "time_step": float(kqd_config.time_step),
        "trotter_steps": float(kqd_config.trotter_steps),
    }
    if sector_dimension is not None:
        orthogonality_metrics["sector_dimension"] = float(sector_dimension)

    primary_energy = float(ritz_values[0])
    termination_reason = projected_convergence_reason(
        diagnostics,
        relative_residual=solve_data.residual_diagnostics["relative_ritz_residual"],
        residual_tolerance=kqd_config.residual_tolerance,
    )
    rank_reduced = int(diagnostics.get("dropped_rank", 0) or 0) > 0
    diagnostic_only = bool(diagnostics.get("diagnostic_only", False)) or rank_reduced
    return KQDResult(
        algorithm="kqd",
        primary_energy=primary_energy,
        primary_iterations=solve_data.basis_rank,
        converged=bool(converged) and not rank_reduced,
        ritz_values=[float(value) for value in ritz_values],
        krylov_rank=solve_data.basis_rank,
        orthogonality_metrics={
            **orthogonality_metrics,
            **diagnostics,
            **solve_data.residual_diagnostics,
        },
        matrix_element_summary=matrix_element_summary,
        raw_ritz_values=[float(value) for value in raw_ritz_values],
        stability_summary={
            **diagnostics,
            "diagnostic_only": diagnostic_only,
            "energy_state": "diagnostic" if diagnostic_only else "reportable",
            "termination_reason": termination_reason,
        },
        circuit_artifacts=circuit_artifacts,
    )


__all__ = [
    "KQDCompletionPayload",
    "build_kqd_completion_payload",
    "build_kqd_result",
    "emit_kqd_completion",
]
