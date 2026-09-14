"""QFD result and completion-payload helpers for the algorithm package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from worker.chemistry.progress import ProgressCallback
from worker.chemistry.projected_subspace import projected_convergence_reason
from worker.chemistry.types import QFDResult


@dataclass(frozen=True)
class QFDCompletionPayload:
    """Completed QFD progress values."""

    num_time_points: int
    primary_energy: float
    time_grid_type: str
    qfd_variant: str
    time_evolution_backend: str
    aer_trotter_steps: int | None
    min_filter_eigenvalue: float | None
    max_filter_eigenvalue: float | None
    overlap_condition: float
    stability_state: Any
    relative_residual: float
    residual_tolerance: float
    termination_reason: str
    matrix_element_strategy: Any
    wall_seconds: float


def build_qfd_completion_payload(
    *,
    num_time_points: int,
    primary_energy: float,
    filter_eigenvalues: np.ndarray,
    diagnostics: dict[str, Any],
    residual_diagnostics: dict[str, float],
    residual_tolerance: float,
    qfd_elapsed: float,
    time_grid_type: str,
    time_evolution_backend: str,
    aer_trotter_steps: int | None,
    matrix_element_strategy: Any | None,
    qfd_variant: str = "qfd_chemistry_forward",
) -> QFDCompletionPayload:
    """Build the completed QFD progress payload object."""
    return QFDCompletionPayload(
        num_time_points=num_time_points,
        primary_energy=primary_energy,
        time_grid_type=time_grid_type,
        qfd_variant=qfd_variant,
        time_evolution_backend=time_evolution_backend,
        aer_trotter_steps=aer_trotter_steps,
        min_filter_eigenvalue=(float(filter_eigenvalues[0]) if filter_eigenvalues.size else None),
        max_filter_eigenvalue=(float(filter_eigenvalues[-1]) if filter_eigenvalues.size else None),
        overlap_condition=float(diagnostics.get("overlap_condition", 0.0)),
        stability_state=diagnostics.get("stability_state"),
        relative_residual=residual_diagnostics["relative_ritz_residual"],
        residual_tolerance=residual_tolerance,
        termination_reason=projected_convergence_reason(
            diagnostics,
            relative_residual=residual_diagnostics["relative_ritz_residual"],
            residual_tolerance=residual_tolerance,
        ),
        matrix_element_strategy=matrix_element_strategy,
        wall_seconds=round(qfd_elapsed, 4),
    )


def emit_qfd_completion(
    progress_callback: ProgressCallback | None,
    payload: QFDCompletionPayload,
) -> None:
    """Emit a completed QFD progress event when a callback is configured."""
    if progress_callback is None:
        return
    diagnostic_only = (
        payload.stability_state != "stable" or payload.termination_reason != "converged"
    )
    progress_callback(
        {
            "algorithm": "qfd",
            "stage": "completed",
            "step": "solve",
            "iteration": payload.num_time_points,
            "energy": payload.primary_energy if not diagnostic_only else None,
            "diagnostic_energy": payload.primary_energy if diagnostic_only else None,
            "energy_state": "diagnostic" if diagnostic_only else "reportable",
            "convergence_iteration": payload.num_time_points,
            "completed_iterations": payload.num_time_points,
            "total_iterations": payload.num_time_points,
            "time_grid_type": payload.time_grid_type,
            "qfd_variant": payload.qfd_variant,
            "time_evolution_backend": payload.time_evolution_backend,
            "aer_trotter_steps": payload.aer_trotter_steps,
            "min_filter_eigenvalue": payload.min_filter_eigenvalue,
            "max_filter_eigenvalue": payload.max_filter_eigenvalue,
            "overlap_condition": payload.overlap_condition,
            "stability_state": payload.stability_state,
            "relative_residual": payload.relative_residual,
            "residual_tolerance": payload.residual_tolerance,
            "termination_reason": payload.termination_reason,
            "matrix_element_strategy": payload.matrix_element_strategy,
            "wall_seconds": payload.wall_seconds,
        }
    )


def build_qfd_result(
    *,
    filter_eigenvalues: np.ndarray,
    raw_filter_eigenvalues: np.ndarray,
    num_time_points: int,
    conditioning_summary: dict[str, Any],
    residual_diagnostics: dict[str, float],
    diagnostics: dict[str, Any],
    converged: bool,
    matrix_element_summary: dict[str, Any] | None = None,
) -> QFDResult:
    """Build the public QFD result from completed projected-solve data."""
    if filter_eigenvalues.size == 0:
        raise ValueError("QFD projected solve produced no filter eigenvalues")
    primary_energy = float(filter_eigenvalues[0])
    termination_reason = projected_convergence_reason(
        diagnostics,
        relative_residual=residual_diagnostics["relative_ritz_residual"],
        residual_tolerance=residual_diagnostics.get("residual_convergence_threshold", 0.0),
    )
    rank_reduced = int(diagnostics.get("dropped_rank", 0) or 0) > 0
    diagnostic_only = bool(diagnostics.get("diagnostic_only", False)) or rank_reduced
    return QFDResult(
        algorithm="qfd",
        primary_energy=primary_energy,
        primary_iterations=num_time_points,
        converged=bool(converged) and not rank_reduced,
        filter_eigenvalues=[float(value) for value in filter_eigenvalues],
        conditioning_summary={
            **conditioning_summary,
            **residual_diagnostics,
            "termination_reason": termination_reason,
        },
        matrix_element_summary=matrix_element_summary or {},
        raw_filter_eigenvalues=[float(value) for value in raw_filter_eigenvalues],
        stability_summary={
            **diagnostics,
            "diagnostic_only": diagnostic_only,
            "energy_state": "diagnostic" if diagnostic_only else "reportable",
            "termination_reason": termination_reason,
        },
    )


__all__ = [
    "QFDCompletionPayload",
    "build_qfd_completion_payload",
    "build_qfd_result",
    "emit_qfd_completion",
]
