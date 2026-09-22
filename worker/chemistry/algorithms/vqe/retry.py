"""Warm-start retry policy for VQE optimizers in the algorithm package."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
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


def _iteration_count(diagnostics: dict[str, Any]) -> int | None:
    value = diagnostics.get("optimizer_iterations")
    if isinstance(value, (int, np.integer)) and not isinstance(value, bool) and value >= 0:
        return int(value)
    return None


def _optimizer_with_iteration_limit(optimizer: Any, iteration_limit: int) -> Any:
    """Return an optimizer config capped to one retry's remaining budget."""
    options = dict(getattr(optimizer, "options", None) or {})
    options["maxiter"] = iteration_limit
    return replace(optimizer, max_iterations=iteration_limit, options=options)


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
    selected_optimizer_iterations = _iteration_count(retry_diagnostics)
    iteration_counts: list[int | None] = [selected_optimizer_iterations]
    raw_iteration_budget = getattr(optimizer, "max_iterations", None)
    iteration_budget = (
        int(raw_iteration_budget)
        if isinstance(raw_iteration_budget, (int, np.integer))
        and not isinstance(raw_iteration_budget, bool)
        and raw_iteration_budget > 0
        else None
    )
    retry_attempted_indices: list[int] = []
    retry_selected_index: int | None = None
    last_retry_termination_reason: str | None = None
    for retry_index in warm_start_retry_indices(
        candidate_points=candidate_points,
        selected_initial_diagnostics=selected_initial_diagnostics,
    ):
        if any(count is None for count in iteration_counts):
            last_retry_termination_reason = "optimizer_iteration_count_unavailable"
            break
        total_before_retry = sum(int(count) for count in iteration_counts)
        remaining_iterations = (
            iteration_budget - total_before_retry if iteration_budget is not None else None
        )
        if remaining_iterations is not None and remaining_iterations <= 0:
            last_retry_termination_reason = "max_iterations"
            break
        retry_attempted_indices.append(retry_index)
        best_energy_before_retry = objective.best_energy
        retry_optimizer = (
            _optimizer_with_iteration_limit(optimizer, remaining_iterations)
            if remaining_iterations is not None
            else optimizer
        )
        retry_optimizer_diagnostics = {
            **optimizer_diagnostics,
            "optimizer_iteration_budget": iteration_budget,
            "optimizer_attempt_max_iterations": remaining_iterations,
        }
        (
            retry_optimal_point,
            retry_final_energy,
            retry_iterations,
            retry_converged,
            retry_result_diagnostics,
        ) = run_optimizer_fn(
            objective=objective,
            initial_point=candidate_points[retry_index],
            optimizer=retry_optimizer,
            optimizer_diagnostics=retry_optimizer_diagnostics,
            convergence_trace=convergence_trace,
            parameter_bounds=parameter_bounds,
            best_point_getter=lambda: objective.best_point,
            best_energy_getter=lambda: objective.best_energy,
        )
        retry_iterations_used = _iteration_count(retry_result_diagnostics)
        iteration_counts.append(retry_iterations_used)
        last_retry_termination_reason = retry_result_diagnostics.get("termination_reason")
        best_energy_after_retry = objective.best_energy
        improved = not (
            best_energy_before_retry is None
            or best_energy_after_retry is None
            or best_energy_after_retry >= best_energy_before_retry - _WARM_START_RETRY_TOLERANCE
        )
        if not improved:
            if retry_iterations_used is None:
                last_retry_termination_reason = "optimizer_iteration_count_unavailable"
                break
            if last_retry_termination_reason == "max_function_evaluations":
                break
            continue
        optimal_point = retry_optimal_point
        final_energy = retry_final_energy
        iterations = retry_iterations
        converged = retry_converged
        retry_diagnostics = retry_result_diagnostics
        selected_optimizer_iterations = retry_iterations_used
        retry_selected_index = retry_index
        break

    known_iterations = [count for count in iteration_counts if count is not None]
    total_iterations = (
        sum(known_iterations) if len(known_iterations) == len(iteration_counts) else None
    )
    terminal_iteration_reason = (
        "max_function_evaluations"
        if last_retry_termination_reason == "max_function_evaluations"
        else "optimizer_iteration_count_unavailable"
        if last_retry_termination_reason == "optimizer_iteration_count_unavailable"
        else "max_iterations"
        if iteration_budget is not None
        and total_iterations is not None
        and total_iterations >= iteration_budget
        else "stationary_initial_point"
    )
    retry_diagnostics = {
        **retry_diagnostics,
        "optimizer_iterations": total_iterations,
        "optimizer_iterations_total": total_iterations,
        "optimizer_iterations_by_attempt": iteration_counts,
        "selected_optimizer_iterations": selected_optimizer_iterations,
        "optimizer_iteration_budget": iteration_budget,
        "effective_max_iterations": (
            iteration_budget
            if iteration_budget is not None
            else retry_diagnostics.get("effective_max_iterations")
        ),
        "effective_optimizer_max_iterations": (
            iteration_budget
            if iteration_budget is not None
            else retry_diagnostics.get("effective_optimizer_max_iterations")
        ),
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
        "termination_reason": terminal_iteration_reason,
        "message": (
            "Gradient-based VQE stopped without an alternate start that improved "
            "the observed energy."
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

    if _iteration_count(retry_diagnostics) is None:
        retry_diagnostics = {
            **retry_diagnostics,
            "success": False,
            "termination_reason": "optimizer_iteration_count_unavailable",
            "warm_start_retry_reason": "stationary_zero_candidate",
            "warm_start_retry_count": 0,
            "warm_start_retry_attempted_indices": [],
            "warm_start_retry_selected_index": None,
            "warm_start_retry_skipped_reason": "optimizer_iteration_count_unavailable",
        }
        return optimal_point, final_energy, iterations, False, retry_diagnostics

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
