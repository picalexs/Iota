"""SciPy optimization helpers for the VQE algorithm package."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
from scipy.optimize import minimize

from worker.chemistry.algorithms.vqe.telemetry import FunctionEvaluationLimitReached


def best_or_latest_energy(best_energy: float | None, convergence_trace: list[float]) -> float:
    """Return the best observed energy or the latest trace value."""
    if best_energy is not None:
        return float(best_energy)
    if convergence_trace:
        return float(convergence_trace[-1])
    return float("nan")


def run_scipy_vqe_optimizer(
    *,
    objective: Any,
    initial_point: np.ndarray,
    optimizer: Any,
    optimizer_diagnostics: dict[str, Any],
    convergence_trace: list[float],
    parameter_bounds: list[tuple[float, float]] | None,
    best_point_getter: Callable[[], np.ndarray | None],
    best_energy_getter: Callable[[], float | None],
    minimize_fn: Callable[..., Any] = minimize,
) -> tuple[np.ndarray, float, int, bool, dict[str, Any]]:
    """Run SciPy and normalize its result into the worker optimizer contract."""
    try:
        scipy_result = minimize_fn(
            objective,
            x0=initial_point,
            method=optimizer.scipy_method,
            options=optimizer.options or {"maxiter": optimizer.max_iterations},
            bounds=parameter_bounds if optimizer.scipy_method in {"SLSQP", "L-BFGS-B"} else None,
        )
        optimal_point = np.asarray(scipy_result.x, dtype=float)
        final_energy = float(scipy_result.fun)
        iterations = max(len(convergence_trace), 1)
        converged = bool(getattr(scipy_result, "success", False))
        native_iterations = getattr(scipy_result, "nit", None)
        optimizer_iterations = int(native_iterations) if native_iterations is not None else None
        final_delta = (
            abs(convergence_trace[-1] - convergence_trace[-2])
            if len(convergence_trace) >= 2
            else None
        )
        diagnostics = {
            **optimizer_diagnostics,
            "scipy_method": optimizer.scipy_method,
            "success": converged,
            "status": int(getattr(scipy_result, "status", 0) or 0),
            "message": str(getattr(scipy_result, "message", "")),
            "termination_reason": "optimizer_success" if converged else "optimizer_failure",
            "function_evaluations": int(
                getattr(scipy_result, "nfev", len(convergence_trace)) or len(convergence_trace)
            ),
            "optimizer_function_evaluations": int(
                getattr(scipy_result, "nfev", len(convergence_trace))
                or len(convergence_trace)
            ),
            "objective_evaluations": len(convergence_trace),
            "optimizer_iterations": optimizer_iterations,
            "final_delta_energy": float(final_delta) if final_delta is not None else None,
        }
        return optimal_point, final_energy, iterations, converged, diagnostics
    except FunctionEvaluationLimitReached as exc:
        best_point = best_point_getter()
        optimal_point = best_point if best_point is not None else initial_point
        return (
            optimal_point,
            best_or_latest_energy(best_energy_getter(), convergence_trace),
            max(len(convergence_trace), 1),
            False,
            {
                **optimizer_diagnostics,
                "scipy_method": optimizer.scipy_method,
                "success": False,
                "status": 1,
                "message": str(exc),
                "termination_reason": "max_function_evaluations",
                "function_evaluations": len(convergence_trace),
                "objective_evaluations": len(convergence_trace),
                "optimizer_iterations": None,
            },
        )


__all__ = ["best_or_latest_energy", "run_scipy_vqe_optimizer"]
