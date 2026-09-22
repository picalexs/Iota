"""Pure SQD recovery-iteration convergence helpers for the algorithm package."""

from __future__ import annotations

from typing import Any

import numpy as np


def compute_iteration_deltas(
    *,
    previous_energy: float | None,
    previous_occupancies: np.ndarray | None,
    occupancy_vector: np.ndarray,
    energy_value: float,
) -> tuple[float, float]:
    """Compute energy and occupancy deltas against the previous iteration."""
    if previous_energy is None:
        return float("inf"), float("inf")

    delta_energy = abs(energy_value - previous_energy)
    if previous_occupancies is None:
        return delta_energy, float("inf")
    occupancy_delta = float(np.max(np.abs(occupancy_vector - previous_occupancies)))
    return delta_energy, occupancy_delta


def iteration_values_are_finite(
    *,
    energy_value: float,
    delta_energy: float,
    occupancy_delta: float,
    occupancy_vector: np.ndarray,
    deltas_available: bool = True,
) -> bool:
    """Return whether one SQD iteration has finite convergence inputs."""
    delta_values_are_valid = (
        bool(np.isfinite(delta_energy) and np.isfinite(occupancy_delta))
        if deltas_available
        else bool(not np.isnan(delta_energy) and not np.isnan(occupancy_delta))
    )
    return bool(
        np.isfinite(energy_value)
        and delta_values_are_valid
        and np.all(np.isfinite(np.asarray(occupancy_vector, dtype=float)))
    )


def is_iteration_converged(
    *,
    iteration: int,
    delta_energy: float,
    occupancy_delta: float,
    selected_count: int,
    energy_tolerance: float,
    occupancy_tolerance: float,
    min_selected_configurations: int,
) -> bool:
    """Return whether one SQD recovery iteration satisfies the convergence gate."""
    return bool(
        iteration > 1
        and np.isfinite(delta_energy)
        and np.isfinite(occupancy_delta)
        and delta_energy <= energy_tolerance
        and occupancy_delta <= occupancy_tolerance
        and selected_count >= min_selected_configurations
    )


def build_iteration_signature(
    *,
    selected_distribution: list[dict[str, Any]],
    selected_ci_summary: dict[str, Any],
    occupancy_vector: np.ndarray,
    recovery_applied: bool,
) -> tuple[Any, ...]:
    """Build a stable signature for one SQD selected-space iteration.

    Energy and occupation deltas alone do not prove that an SQD iteration made
    no progress. The selected determinant distribution and selected-CI strings
    must also remain unchanged before a stalled run can stop.
    """

    distribution_signature = tuple(
        (
            str(entry.get("bitstring", "")),
            round(float(entry.get("probability", 0.0)), 12),
        )
        for entry in selected_distribution
    )
    alpha_strings = tuple(
        int(value) for value in selected_ci_summary.get("selected_ci_strings_alpha", [])
    )
    beta_strings = tuple(
        int(value) for value in selected_ci_summary.get("selected_ci_strings_beta", [])
    )
    occupations = tuple(float(value) for value in np.round(occupancy_vector, 12))
    return (
        distribution_signature,
        alpha_strings,
        beta_strings,
        occupations,
        bool(recovery_applied),
    )


def is_iteration_stalled(
    *,
    iteration: int,
    delta_energy: float,
    occupancy_delta: float,
    selected_count: int,
    min_selected_configurations: int,
    energy_tolerance: float,
    occupancy_tolerance: float,
    previous_signature: tuple[Any, ...] | None,
    current_signature: tuple[Any, ...] | None,
) -> bool:
    """Return whether SQD is a reproducible fixed point below its space floor."""
    return (
        iteration > 1
        and previous_signature is not None
        and current_signature == previous_signature
        and delta_energy <= energy_tolerance
        and occupancy_delta <= occupancy_tolerance
        and selected_count < min_selected_configurations
    )


__all__ = [
    "build_iteration_signature",
    "compute_iteration_deltas",
    "iteration_values_are_finite",
    "is_iteration_converged",
    "is_iteration_stalled",
]
