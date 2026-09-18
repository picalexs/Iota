"""Warm-start retry policy for VQE optimizers in the algorithm package."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np

OptimizerResult = tuple[np.ndarray, float, int, bool, dict[str, Any]]
OptimizerRunner = Callable[..., OptimizerResult]
RetryRunner = Callable[..., OptimizerResult]

_WARM_START_RETRY_TOLERANCE = 1e-9
_GRADIENT_WARM_START_RETRY_METHODS = frozenset({"L-BFGS-B", "SLSQP"})


def should_retry_stationary_warm_start(
    *,
    optimizer: Any,
    initial_point: np.ndarray,
    candidate_points: list[np.ndarray],
    converged: bool,
    optimizer_diagnostics: dict[str, Any],
) -> bool:
    """Detect a zero-warm-start trap for gradient-based optimizers."""
    if optimizer.scipy_method not in _GRADIENT_WARM_START_RETRY_METHODS:
        return False
    if not converged:
        return False
    if len(candidate_points) <= 1:
        return False
    optimizer_iterations = optimizer_diagnostics.get("optimizer_iterations")
    if optimizer_iterations not in {0, None}:
        return False
    return bool(np.allclose(initial_point, 0.0))


def warm_start_retry_indices(
    *,
    candidate_points: list[np.ndarray],
    selected_initial_diagnostics: dict[str, Any],
) -> list[int]:
    """Return alternate warm starts from best scored to worst."""
    selected_index = int(selected_initial_diagnostics.get("initial_point_best_index") or 0)
    raw_energies = selected_initial_diagnostics.get("initial_point_candidate_energies")
    if (
        isinstance(raw_energies, list)
        and len(raw_energies) == len(candidate_points)
        and all(isinstance(value, (int, float)) for value in raw_energies)
    ):
        ordered_indices = sorted(
            range(len(candidate_points)),
            key=lambda index: (float(raw_energies[index]), index),
        )
    else:
        ordered_indices = list(range(len(candidate_points)))
    return [index for index in ordered_indices if index != selected_index]


def retry_stationary_warm_start(
    *,
    objective: Any,
    optimizer: Any,
    optimizer_diagnostics: dict[str, Any],
    convergence_trace: list[float],
    parameter_bounds: list[tuple[float, float]] | None,
    candidate_points: list[np.ndarray],
    selected_initial_diagnostics: dict[str, Any],
    current_result: OptimizerResult,
    run_optimizer_fn: OptimizerRunner,
) -> OptimizerResult:
    """Retry alternate warm starts until one improves the observed energy."""
    optimal_point, final_energy, iterations, converged, retry_diagnostics = current_result
    retry_attempted_indices: list[int] = []
    retry_selected_index: int | None = None
    for retry_index in warm_start_retry_indices(
        candidate_points=candidate_points,
        selected_initial_diagnostics=selected_initial_diagnostics,
    ):
        retry_attempted_indices.append(retry_index)
        best_energy_before_retry = objective.best_energy
        (
            retry_optimal_point,
            retry_final_energy,
            retry_iterations,
            retry_converged,
            retry_result_diagnostics,
        ) = run_optimizer_fn(
            objective=objective,
            initial_point=candidate_points[retry_index],
            optimizer=optimizer,
            optimizer_diagnostics=optimizer_diagnostics,
            convergence_trace=convergence_trace,
            parameter_bounds=parameter_bounds,
            best_point_getter=lambda: objective.best_point,
            best_energy_getter=lambda: objective.best_energy,
        )
        best_energy_after_retry = objective.best_energy
        if (
            best_energy_before_retry is None
            or best_energy_after_retry is None
            or best_energy_after_retry >= best_energy_before_retry - _WARM_START_RETRY_TOLERANCE
        ):
            continue
        optimal_point = retry_optimal_point
        final_energy = retry_final_energy
        iterations = retry_iterations
        converged = retry_converged
        retry_diagnostics = retry_result_diagnostics
        retry_selected_index = retry_index
        break

    retry_diagnostics = {
        **retry_diagnostics,
        "warm_start_retry_reason": "stationary_zero_candidate",
        "warm_start_retry_count": len(retry_attempted_indices),
        "warm_start_retry_attempted_indices": retry_attempted_indices,
        "warm_start_retry_selected_index": retry_selected_index,
    }
    if retry_selected_index is not None:
        return optimal_point, final_energy, iterations, converged, retry_diagnostics

    retry_diagnostics = {
        **retry_diagnostics,
        "success": False,
        "termination_reason": "stationary_initial_point",
        "message": (
            "Gradient-based VQE stopped at the selected zero warm-start "
            "candidate without improving any alternate warm start."
        ),
    }
    return optimal_point, final_energy, iterations, False, retry_diagnostics


def run_scipy_vqe_with_retry(
    *,
    objective: Any,
    initial_point: np.ndarray,
    optimizer: Any,
    optimizer_diagnostics: dict[str, Any],
    convergence_trace: list[float],
    parameter_bounds: list[tuple[float, float]] | None,
    candidate_points: list[np.ndarray],
    selected_initial_diagnostics: dict[str, Any],
    run_optimizer_fn: OptimizerRunner,
    should_retry_fn: Callable[..., bool] = should_retry_stationary_warm_start,
    retry_fn: RetryRunner = retry_stationary_warm_start,
) -> OptimizerResult:
    """Run SciPy VQE and retry alternate starts after stationary convergence."""
    result = run_optimizer_fn(
        objective=objective,
        initial_point=initial_point,
        optimizer=optimizer,
        optimizer_diagnostics=optimizer_diagnostics,
        convergence_trace=convergence_trace,
        parameter_bounds=parameter_bounds,
        best_point_getter=lambda: objective.best_point,
        best_energy_getter=lambda: objective.best_energy,
    )
    optimal_point, final_energy, iterations, converged, retry_diagnostics = result
    if not should_retry_fn(
        optimizer=optimizer,
        initial_point=initial_point,
        candidate_points=candidate_points,
        converged=converged,
        optimizer_diagnostics=retry_diagnostics,
    ):
        return result

    return retry_fn(
        objective=objective,
        optimizer=optimizer,
        optimizer_diagnostics=optimizer_diagnostics,
        convergence_trace=convergence_trace,
        parameter_bounds=parameter_bounds,
        candidate_points=candidate_points,
        selected_initial_diagnostics=selected_initial_diagnostics,
        current_result=(optimal_point, final_energy, iterations, converged, retry_diagnostics),
        run_optimizer_fn=run_optimizer_fn,
    )


__all__ = [
    "OptimizerResult",
    "OptimizerRunner",
    "RetryRunner",
    "retry_stationary_warm_start",
    "run_scipy_vqe_with_retry",
    "should_retry_stationary_warm_start",
    "warm_start_retry_indices",
]
