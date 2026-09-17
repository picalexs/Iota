"""SQD selected-CI recovery loop and progress normalization for the algorithm package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from worker.chemistry.algorithms.sqd.config import SQDOptions
from worker.chemistry.algorithms.sqd.sampling import aggregate_bitstring_frequencies
from worker.chemistry.algorithms.sqd.selection import (
    extract_carryover_ci_strings,
    selected_ci_fraction,
    selected_ci_strings_from_bitstrings,
)
from worker.chemistry.progress import ProgressCallback


@dataclass(frozen=True)
class SQDDependencies:
    """qiskit-addon-sqd entrypoints used by SQD recovery."""

    recover_configurations: Any
    postselect_by_hamming_right_and_left: Any
    solve_fermion: Any
    subsample: Any


@dataclass
class SQDBatchOutcome:
    """Selected-CI solve outputs for one SQD recovery iteration."""

    energy_value: float
    best_sci_state: Any | None
    selected_occupancies: tuple[np.ndarray, np.ndarray]
    last_spin_sq: float
    last_selected_ci_summary: dict[str, Any]
    carryover_ci_strings: tuple[np.ndarray, np.ndarray]
    last_carryover_summary: dict[str, Any]
    last_batch_energies: list[float]
    effective_samples_per_batch: int
    selected_ci_dimensions: list[int]
    selected_ci_fractions: list[float]


def _emit_progress(
    progress_callback: ProgressCallback | None,
    payload: dict[str, Any],
) -> None:
    if progress_callback is not None:
        progress_callback(payload)


def _emit_selected_ci_progress(
    *,
    iteration: int,
    batch_index: int,
    options: SQDOptions,
    ci_summary: dict[str, Any],
    progress_callback: ProgressCallback | None,
) -> None:
    """Emit the pre-solve selected-CI progress payload for a batch."""
    _emit_progress(
        progress_callback,
        {
            "algorithm": "sqd",
            "stage": "progress",
            "step": "selected_ci_solve",
            "iteration": iteration,
            "completed_iterations": iteration - 1,
            "total_iterations": options.max_iterations,
            "energy": None,
            "sci_batch": batch_index,
            "sci_batches": options.num_batches,
            "selected_ci_dimension": int(ci_summary["sci_dimension"]),
            "full_sci_dimension": int(options.selected_ci_limit_summary["full_sci_dimension"]),
            "selected_ci_fraction": round(
                selected_ci_fraction(
                    ci_summary["sci_dimension"],
                    full_sci_dimension=options.selected_ci_limit_summary["full_sci_dimension"],
                ),
                6,
            ),
            "selected_ci_cap_active": bool(
                options.selected_ci_limit_summary["cap_active"]
                or ci_summary["cap_active_for_batch"]
            ),
            "selected_ci_spin_symmetrized": bool(options.symmetrize_spin),
            "selected_ci_carryover_alpha": int(ci_summary["carryover_strings_alpha"]),
            "selected_ci_carryover_beta": int(ci_summary["carryover_strings_beta"]),
        },
    )


def _emit_selected_ci_batch_completed_progress(
    *,
    iteration: int,
    batch_index: int,
    options: SQDOptions,
    ci_summary: dict[str, Any],
    total_energy: float,
    progress_callback: ProgressCallback | None,
) -> None:
    """Emit the post-solve selected-CI batch completion payload."""
    _emit_progress(
        progress_callback,
        {
            "algorithm": "sqd",
            "stage": "progress",
            "step": "selected_ci_batch_completed",
            "iteration": iteration,
            "completed_iterations": iteration - 1,
            "total_iterations": options.max_iterations,
            "energy": None,
            "batch_energy": round(total_energy, 8),
            "sci_batch": batch_index,
            "sci_batches": options.num_batches,
            "selected_ci_dimension": int(ci_summary["sci_dimension"]),
        },
    )


def run_selected_ci_batches(
    *,
    iteration: int,
    deps: SQDDependencies,
    options: SQDOptions,
    rng: np.random.Generator,
    selected_bits: np.ndarray,
    selected_probs: np.ndarray,
    carryover_ci_strings: tuple[np.ndarray, np.ndarray],
    progress_callback: ProgressCallback | None,
) -> SQDBatchOutcome:
    """Run selected-CI batch solves for one SQD recovery iteration."""
    effective_samples_per_batch = min(options.samples_per_batch, int(selected_bits.shape[0]))
    selected_batches = deps.subsample(
        selected_bits,
        selected_probs,
        samples_per_batch=effective_samples_per_batch,
        num_batches=options.num_batches,
        rand_seed=rng,
    )

    batch_energies: list[float] = []
    batch_summaries: list[dict[str, Any]] = []
    selected_ci_dimensions: list[int] = []
    selected_ci_fractions: list[float] = []
    best_batch_index = 0
    best_batch_energy = float("inf")
    best_batch_state: Any = None
    best_batch_ci_strings: tuple[np.ndarray, np.ndarray] | None = None
    best_batch_spin_sq = 0.0
    best_batch_summary: dict[str, Any] | None = None
    best_batch_fraction = 0.0
    full_sci_dimension = options.selected_ci_limit_summary["full_sci_dimension"]
    batch_occupancy_values: list[tuple[np.ndarray, np.ndarray]] = []

    for batch_index, batch in enumerate(selected_batches, start=1):
        batch_bits, batch_probs, _batch_counts = aggregate_bitstring_frequencies(batch)
        ci_strings, ci_summary = selected_ci_strings_from_bitstrings(
            batch_bits,
            batch_probs,
            max_dim=options.selected_ci_limits,
            open_shell=options.open_shell,
            symmetrize_spin=options.symmetrize_spin,
            carryover_ci_strings=carryover_ci_strings,
        )
        batch_summaries.append(ci_summary)
        selected_ci_dimensions.append(int(ci_summary["sci_dimension"]))
        selected_ci_fractions.append(
            selected_ci_fraction(
                ci_summary["sci_dimension"],
                full_sci_dimension=full_sci_dimension,
            )
        )
        _emit_selected_ci_progress(
            iteration=iteration,
            batch_index=batch_index,
            options=options,
            ci_summary=ci_summary,
            progress_callback=progress_callback,
        )

        energy, batch_state, batch_occupancies, spin_sq = deps.solve_fermion(
            ci_strings,
            options.one_body,
            options.two_body,
            open_shell=options.open_shell,
            spin_sq=options.target_spin_sq,
            **options.sci_solver_options,
        )
        total_energy = float(energy) + options.hamiltonian_constant
        batch_energies.append(total_energy)
        current_occupancies = (
            np.asarray(batch_occupancies[0], dtype=float).copy(),
            np.asarray(batch_occupancies[1], dtype=float).copy(),
        )
        batch_occupancy_values.append(current_occupancies)
        if total_energy < best_batch_energy:
            best_batch_energy = total_energy
            best_batch_index = batch_index - 1
            best_batch_state = batch_state
            best_batch_ci_strings = (
                np.asarray(ci_strings[0], dtype=np.int64).copy(),
                np.asarray(ci_strings[1], dtype=np.int64).copy(),
            )
            best_batch_spin_sq = float(spin_sq)
            best_batch_summary = dict(ci_summary)
            best_batch_fraction = selected_ci_fractions[-1]

        _emit_selected_ci_batch_completed_progress(
            iteration=iteration,
            batch_index=batch_index,
            options=options,
            ci_summary=ci_summary,
            total_energy=total_energy,
            progress_callback=progress_callback,
        )

    if not batch_energies:
        raise ValueError("SQD selected-CI solve did not produce any batch energies")
    if best_batch_summary is None or best_batch_ci_strings is None or not batch_occupancy_values:
        raise ValueError("SQD selected-CI solve did not preserve the best batch diagnostics")

    energy_value = float(best_batch_energy)
    average_occupancies = (
        np.mean(np.stack([values[0] for values in batch_occupancy_values]), axis=0),
        np.mean(np.stack([values[1] for values in batch_occupancy_values]), axis=0),
    )
    last_selected_ci_summary = {
        **options.selected_ci_limit_summary,
        **best_batch_summary,
        "best_batch": int(best_batch_index + 1),
        "best_batch_energy": round(energy_value, 8),
        "selected_ci_dimension": int(best_batch_summary["sci_dimension"]),
        "selected_ci_fraction": round(best_batch_fraction, 6),
        "batch_sci_dimensions": [int(summary["sci_dimension"]) for summary in batch_summaries],
        "batch_selected_ci_fractions": [
            round(
                selected_ci_fraction(
                    summary["sci_dimension"],
                    full_sci_dimension=full_sci_dimension,
                ),
                6,
            )
            for summary in batch_summaries
        ],
        "mean_sci_dimension": round(
            float(np.mean([summary["sci_dimension"] for summary in batch_summaries])),
            4,
        ),
        "max_sci_dimension": int(max(summary["sci_dimension"] for summary in batch_summaries)),
        "exact_sector_solve": bool(
            int(best_batch_summary["sci_dimension"]) >= int(full_sci_dimension)
        ),
        "occupancies_source": "mean_over_batches",
        "average_occupancies_alpha": average_occupancies[0].tolist(),
        "average_occupancies_beta": average_occupancies[1].tolist(),
        "selected_ci_strings_alpha": best_batch_ci_strings[0].tolist(),
        "selected_ci_strings_beta": best_batch_ci_strings[1].tolist(),
    }
    carryover_ci_strings, last_carryover_summary = extract_carryover_ci_strings(
        best_batch_state,
        carryover_threshold=options.carryover_threshold,
        symmetrize_spin=options.symmetrize_spin,
        open_shell=options.open_shell,
    )
    last_selected_ci_summary.update(last_carryover_summary)
    return SQDBatchOutcome(
        energy_value=energy_value,
        best_sci_state=best_batch_state,
        selected_occupancies=average_occupancies,
        last_spin_sq=best_batch_spin_sq,
        last_selected_ci_summary=last_selected_ci_summary,
        carryover_ci_strings=carryover_ci_strings,
        last_carryover_summary=last_carryover_summary,
        last_batch_energies=[round(float(value), 8) for value in batch_energies],
        effective_samples_per_batch=effective_samples_per_batch,
        selected_ci_dimensions=selected_ci_dimensions,
        selected_ci_fractions=selected_ci_fractions,
    )
