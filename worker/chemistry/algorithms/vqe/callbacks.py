"""VQE progress callback helpers for the algorithm package."""

from __future__ import annotations

import logging
import time

import numpy as np

from worker.chemistry.progress import ProgressCallback

logger = logging.getLogger(__name__)


def _emit_progress_event(
    *,
    progress_callback: ProgressCallback | None,
    evaluation_count: int,
    previous_energy: float | None,
    iter_start: list[float],
    ansatz_name: str,
    optimizer_name: str,
    optimizer_kind: str,
    max_iterations: int,
    max_function_evaluations: int | None,
    parameter_count: int,
    num_qubits: int,
    energy: float,
    parameter_values: np.ndarray,
) -> float | None:
    """Emit a canonical VQE progress event and return the updated previous energy."""
    if progress_callback is None:
        return float(energy)

    delta_energy = None
    if previous_energy is not None:
        delta_energy = float(energy) - previous_energy

    iter_elapsed = time.monotonic() - iter_start[0]
    iter_start[0] = time.monotonic()
    logger.debug(
        "VQE iter=%d energy=%.8f delta=%s param_norm=%.4f elapsed=%.3fs",
        evaluation_count,
        energy,
        f"{delta_energy:.2e}" if delta_energy is not None else "N/A",
        float(np.linalg.norm(parameter_values)),
        iter_elapsed,
    )
    progress_callback(
        {
            "algorithm": "vqe",
            "stage": "progress",
            "step": "optimize",
            "iteration": evaluation_count,
            "completed_iterations": evaluation_count,
            "iteration_unit": "objective_evaluations",
            "energy": float(energy),
            "evaluation": evaluation_count,
            "objective_evaluations": evaluation_count,
            "ansatz": ansatz_name,
            "optimizer": optimizer_name,
            "optimizer_kind": optimizer_kind,
            "max_iterations": max_iterations,
            "max_function_evaluations": max_function_evaluations,
            "parameter_count": parameter_count,
            "num_qubits": num_qubits,
            "parameter_l2_norm": float(np.linalg.norm(parameter_values)),
            "delta_energy": delta_energy,
            "iter_wall_seconds": round(iter_elapsed, 4),
        }
    )
    return float(energy)
