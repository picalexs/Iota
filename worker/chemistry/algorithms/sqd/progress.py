"""Progress payloads and recovery-trace diagnostics for the SQD algorithm package."""

from __future__ import annotations

from typing import Any, Protocol

import numpy as np

from worker.chemistry.algorithms.sqd.config import SQDOptions
from worker.chemistry.algorithms.sqd.sampling_execution import SQDIterationSampling
from worker.chemistry.algorithms.sqd.selection import selected_ci_fraction
from worker.chemistry.progress import ProgressCallback


class SQDProgressState(Protocol):
    """State fields required to build SQD diagnostics."""

    last_selected_ci_summary: dict[str, Any]
    last_carryover_summary: dict[str, Any]
    best_observed_energy: float
    best_observed_iteration: int
    last_batch_energies: list[float]


def _finite_or_none(value: float) -> float | None:
    return float(value) if np.isfinite(value) else None


def emit_sqd_progress(
    progress_callback: ProgressCallback | None,
    payload: dict[str, Any],
) -> None:
    """Emit an SQD progress payload when a callback is configured."""
    if progress_callback is not None:
        progress_callback(payload)


def build_recovery_trace_entry(
    *,
    iteration: int,
    num_batches: int,
    symmetrize_spin: bool,
    sampling: SQDIterationSampling,
    state: SQDProgressState,
    energy_value: float,
    delta_energy: float,
    occupancy_delta: float,
) -> dict[str, Any]:
    """Build the persisted recovery-trace entry for one SQD iteration."""
    selected_ci_dimension = float(
        state.last_selected_ci_summary.get(
            "selected_ci_dimension",
            state.last_selected_ci_summary.get("max_sci_dimension", 0),
        )
    )
    full_sci_dimension = float(state.last_selected_ci_summary.get("full_sci_dimension", 1))
    selected_ci_fraction_value = state.last_selected_ci_summary.get("selected_ci_fraction")
    if not isinstance(selected_ci_fraction_value, (int, float)):
        selected_ci_fraction_value = selected_ci_fraction(
            selected_ci_dimension,
            full_sci_dimension=full_sci_dimension,
        )
    accepted_bits = getattr(sampling, "accepted_bits", sampling.selected_bits)
    invalid_bits = getattr(sampling, "invalid_bits", np.empty((0, 0), dtype=bool))
    recovered_bits = getattr(sampling, "recovered_bits", np.empty((0, 0), dtype=bool))
    batch_energies = [float(value) for value in getattr(state, "last_batch_energies", [])]
    occupations = getattr(state, "avg_occupancies", None)
    return {
        "iteration": iteration,
        # Preserve the historical field as the final selected count. The
        # explicit fields below separate raw accepted and recovered rows.
        "accepted_samples": int(sampling.selected_bits.shape[0]),
        "selected_samples": int(sampling.selected_bits.shape[0]),
        "raw_valid_configurations": int(accepted_bits.shape[0]),
        "raw_invalid_configurations": int(invalid_bits.shape[0]),
        "recovered_configurations": int(recovered_bits.shape[0]),
        "raw_valid_probability_mass": round(float(sampling.postselection_weight), 12),
        "raw_invalid_probability_mass": round(
            float(np.sum(getattr(sampling, "invalid_probs", np.asarray([], dtype=float)))),
            12,
        ),
        "recovered_probability_mass": round(
            float(np.sum(getattr(sampling, "recovered_probs", np.asarray([], dtype=float)))),
            12,
        ),
        "sampled_bitstrings": int(sampling.raw_bitstring_matrix.shape[0]),
        "sampled_configurations": int(sampling.bitstring_matrix.shape[0]),
        "batch_count": num_batches,
        "energy": round(energy_value, 8),
        "delta_energy": _finite_or_none(round(delta_energy, 8)),
        "occupancy_delta": _finite_or_none(round(occupancy_delta, 8)),
        "postselection_weight": round(sampling.postselection_weight, 8),
        "recovery_applied": bool(getattr(sampling, "recovery_applied", False)),
        "first_solve_source": getattr(sampling, "first_solve_source", "unknown"),
        "raw_bitstring_distribution": list(
            getattr(
                sampling,
                "raw_distribution",
                getattr(sampling, "last_sampled_distribution", []),
            )
        ),
        "accepted_bitstring_distribution": list(
            getattr(sampling, "accepted_distribution", [])
        ),
        "invalid_bitstring_distribution": list(
            getattr(sampling, "invalid_distribution", [])
        ),
        "recovered_bitstring_distribution": list(
            getattr(sampling, "recovered_distribution", [])
        ),
        "selected_bitstring_distribution": list(
            getattr(
                sampling,
                "selected_distribution",
                getattr(sampling, "last_selected_distribution", []),
            )
        ),
        "selected_ci_dimension": int(selected_ci_dimension),
        "full_sci_dimension": int(state.last_selected_ci_summary.get("full_sci_dimension", 0)),
        "selected_ci_fraction": round(float(selected_ci_fraction_value), 6),
        "selected_ci_cap_active": bool(state.last_selected_ci_summary.get("cap_active")),
        "selected_ci_spin_symmetrized": bool(symmetrize_spin),
        "carryover_strings_alpha": int(
            state.last_carryover_summary.get("carryover_strings_alpha", 0)
        ),
        "carryover_strings_beta": int(
            state.last_carryover_summary.get("carryover_strings_beta", 0)
        ),
        "selected_ci_strings_alpha": list(
            state.last_selected_ci_summary.get("selected_ci_strings_alpha", [])
        ),
        "selected_ci_strings_beta": list(
            state.last_selected_ci_summary.get("selected_ci_strings_beta", [])
        ),
        "batch_energies": batch_energies,
        "batch_energy_std": round(float(np.std(batch_energies)), 12)
        if batch_energies
        else None,
        "occupancies_alpha": (
            np.asarray(occupations[0], dtype=float).tolist() if occupations is not None else []
        ),
        "occupancies_beta": (
            np.asarray(occupations[1], dtype=float).tolist() if occupations is not None else []
        ),
        "best_energy": round(state.best_observed_energy, 8),
        "best_iteration": state.best_observed_iteration,
    }


def emit_configuration_recovery_progress(
    *,
    iteration: int,
    options: SQDOptions,
    sampling: SQDIterationSampling,
    state: SQDProgressState,
    energy_value: float,
    delta_energy: float,
    occupancy_delta: float,
    iter_elapsed: float,
    progress_callback: ProgressCallback | None,
    termination_reason: str | None = None,
) -> None:
    """Emit the end-of-iteration SQD recovery progress payload."""
    stable_energy_and_occupancy = (
        iteration > 1
        and delta_energy <= options.energy_tol
        and occupancy_delta <= options.occupancies_tol
    )
    selected_count = int(sampling.selected_bits.shape[0])
    converged_candidate = (
        stable_energy_and_occupancy and selected_count >= options.min_selected_configurations
    )
    convergence_blocked_reason = None
    if stable_energy_and_occupancy and selected_count < options.min_selected_configurations:
        convergence_blocked_reason = "insufficient_selected_configurations"
    selected_ci_dimension = int(
        state.last_selected_ci_summary.get(
            "selected_ci_dimension",
            state.last_selected_ci_summary.get("max_sci_dimension", 0),
        )
    )
    selected_ci_fraction_value = state.last_selected_ci_summary.get("selected_ci_fraction")
    if not isinstance(selected_ci_fraction_value, (int, float)):
        selected_ci_fraction_value = selected_ci_fraction(
            selected_ci_dimension,
            full_sci_dimension=state.last_selected_ci_summary.get("full_sci_dimension", 1),
        )

    emit_sqd_progress(
        progress_callback,
        {
            "algorithm": "sqd",
            "stage": (
                "completed"
                if termination_reason is not None or iteration >= options.max_iterations
                else "progress"
            ),
            "iteration": iteration,
            "completed_iterations": iteration,
            "step": "configuration_recovery",
            "energy": round(energy_value, 8),
            "delta_energy": _finite_or_none(round(delta_energy, 8)),
            "occupancy_delta": _finite_or_none(round(occupancy_delta, 8)),
            "postselection_weight": round(sampling.postselection_weight, 8),
            "selected_samples": selected_count,
            "selected_fraction": round(sampling.postselection_weight, 4),
            "sampled_bitstrings": int(sampling.raw_bitstring_matrix.shape[0]),
            "sampled_configurations": int(sampling.bitstring_matrix.shape[0]),
            "samples_per_batch": options.samples_per_batch,
            "num_batches": options.num_batches,
            "selected_ci_dimension": selected_ci_dimension,
            "full_sci_dimension": int(state.last_selected_ci_summary.get("full_sci_dimension", 0)),
            "selected_ci_fraction": round(float(selected_ci_fraction_value), 6),
            "selected_ci_cap_active": bool(state.last_selected_ci_summary.get("cap_active")),
            "selected_ci_spin_symmetrized": bool(options.symmetrize_spin),
            "carryover_strings_alpha": int(
                state.last_carryover_summary.get("carryover_strings_alpha", 0)
            ),
            "carryover_strings_beta": int(
                state.last_carryover_summary.get("carryover_strings_beta", 0)
            ),
            "energy_tol": options.energy_tol,
            "occupancies_tol": options.occupancies_tol,
            "min_selected_configurations": options.min_selected_configurations,
            "converged_candidate": converged_candidate,
            "convergence_blocked_reason": convergence_blocked_reason,
            "termination_reason": termination_reason,
            "iter_wall_seconds": round(iter_elapsed, 4),
        },
    )
