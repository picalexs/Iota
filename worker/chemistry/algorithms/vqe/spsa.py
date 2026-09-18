"""SPSA optimization loop for the VQE algorithm package."""

from __future__ import annotations

from typing import Any

import numpy as np

_MIN_STABLE_ENERGY_POINTS = 5


def is_delta_converged(
    trace: list[float],
    *,
    threshold: float,
    window: int = _MIN_STABLE_ENERGY_POINTS,
) -> bool:
    """Return True when a recent energy window is stable below the threshold."""
    if len(trace) < window:
        return False
    recent = trace[-window:]
    return all(
        abs(curr - prev) <= threshold for prev, curr in zip(recent, recent[1:], strict=False)
    )


def run_spsa(
    *,
    objective: Any,
    initial_point: np.ndarray,
    max_iterations: int,
    options: dict[str, Any] | None,
    threshold: float,
    seed: int | None,
    convergence_trace: list[float],
    parameter_bounds: list[tuple[float, float]] | None,
) -> tuple[np.ndarray, int, bool, dict[str, Any]]:
    """Run a lightweight SPSA loop against the objective callback."""
    spsa_options = dict(options or {})
    learning_rate = float(spsa_options.get("learning_rate", 0.1))
    perturbation = float(spsa_options.get("perturbation", 0.05))
    blocking = bool(spsa_options.get("blocking", False))
    allowed_increase = float(spsa_options.get("allowed_increase", 0.0))

    rng = np.random.default_rng(seed)
    theta = initial_point.copy()
    best_theta = theta.copy()
    best_energy = objective(theta)
    accepted_energy_trace = [float(best_energy)]
    accepted_steps = 0

    for step in range(max_iterations):
        ck = perturbation / float((step + 1) ** 0.101)
        ak = learning_rate / float((step + 1) ** 0.602)
        delta = rng.choice(np.array([-1.0, 1.0]), size=theta.shape[0])

        energy_plus = objective(theta + ck * delta)
        energy_minus = objective(theta - ck * delta)
        gradient = ((energy_plus - energy_minus) / (2.0 * ck)) * delta

        candidate = theta - ak * gradient
        if parameter_bounds is not None:
            lower = np.asarray([pair[0] for pair in parameter_bounds], dtype=float)
            upper = np.asarray([pair[1] for pair in parameter_bounds], dtype=float)
            candidate = np.clip(candidate, lower, upper)
        candidate_energy = objective(candidate)
        if blocking and candidate_energy > best_energy + allowed_increase:
            continue

        theta = candidate
        accepted_steps += 1
        accepted_energy_trace.append(float(candidate_energy))
        if candidate_energy < best_energy:
            best_energy = candidate_energy
            best_theta = candidate.copy()
        if is_delta_converged(accepted_energy_trace, threshold=threshold):
            break

    iterations = max(len(convergence_trace), accepted_steps, 1)
    converged = is_delta_converged(accepted_energy_trace, threshold=threshold)
    diagnostics = {
        "optimizer_kind": "spsa",
        "accepted_steps": accepted_steps,
        "accepted_energy_trace": accepted_energy_trace,
        "function_evaluations": len(convergence_trace),
        "objective_evaluations": len(convergence_trace),
        "optimizer_iterations": accepted_steps,
        "convergence_threshold": threshold,
    }
    return best_theta, iterations, converged, diagnostics
