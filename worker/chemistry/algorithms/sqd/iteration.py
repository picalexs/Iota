"""Execution of one SQD sampling and recovery iteration."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

from worker.chemistry.algorithms.sqd.config import SQDOptions
from worker.chemistry.algorithms.sqd.convergence import (
    build_iteration_signature,
    compute_iteration_deltas,
)
from worker.chemistry.algorithms.sqd.progress import build_recovery_trace_entry
from worker.chemistry.algorithms.sqd.recovery import (
    SQDBatchOutcome,
    SQDDependencies,
    run_selected_ci_batches,
)
from worker.chemistry.algorithms.sqd.sampling_execution import SQDIterationSampling
from worker.chemistry.algorithms.sqd.state import SQDRunState
from worker.chemistry.progress import ProgressCallback


@dataclass
class SQDIterationOutcome:
    """Aggregated SQD iteration bookkeeping used by the outer recovery loop."""

    sampling: SQDIterationSampling
    batch_outcome: SQDBatchOutcome
    delta_energy: float
    occupancy_delta: float
    occupancy_vector: np.ndarray
    iter_elapsed: float


def update_best_observed_state(
    *,
    state: SQDRunState,
    iteration: int,
    energy_value: float,
    last_spin_sq: float,
    sci_state: Any | None,
    occupancy_vector: np.ndarray,
) -> None:
    """Capture the lowest-energy SQD iteration and its associated diagnostics."""
    if energy_value >= state.best_observed_energy:
        return

    state.best_observed_energy = energy_value
    state.best_observed_iteration = iteration
    state.best_observed_spin_sq = last_spin_sq
    state.best_sci_state = sci_state
    state.best_observed_occupancies = occupancy_vector.copy()
    state.best_sampled_distribution = list(state.last_sampled_distribution)
    state.best_sampling_stages = {
        "raw": list(state.last_raw_distribution),
        "accepted": list(state.last_accepted_distribution),
        "invalid": list(state.last_invalid_distribution),
        "recovered": list(state.last_recovered_distribution),
        "selected": list(state.last_selected_stage_distribution),
    }
    state.best_selected_distribution = list(state.last_selected_distribution)
    state.best_selected_ci_summary = dict(state.last_selected_ci_summary)
    state.best_batch_energies = list(state.last_batch_energies)
    state.best_carryover_summary = dict(state.last_carryover_summary)


def execute_sqd_iteration(
    *,
    iteration: int,
    backend: object,
    deps: SQDDependencies,
    options: SQDOptions,
    rng: np.random.Generator,
    state: SQDRunState,
    progress_callback: ProgressCallback | None,
    sampling_iteration: Callable[..., SQDIterationSampling],
    selected_ci_batches: Callable[..., SQDBatchOutcome] = run_selected_ci_batches,
    iteration_deltas: Callable[..., tuple[float, float]] = compute_iteration_deltas,
    best_state_updater: Callable[..., None] = update_best_observed_state,
    trace_builder: Callable[..., dict[str, Any]] = build_recovery_trace_entry,
    sampling_circuit_factory: Callable[..., Any] | None = None,
) -> SQDIterationOutcome:
    """Run one SQD sampling and recovery iteration and update run state."""
    iter_start = time.monotonic()
    reuse_sample_set = state.measured_bitstring_matrix is not None
    sampling = sampling_iteration(
        iteration=iteration,
        backend=backend,
        deps=deps,
        options=options,
        rng=rng,
        avg_occupancies=state.avg_occupancies,
        progress_callback=progress_callback,
        sampling_circuit_factory=sampling_circuit_factory,
        work_ledger=state.work_ledger,
        measured_bitstring_matrix=state.measured_bitstring_matrix,
        measured_circuit=state.measured_circuit,
    )
    if not reuse_sample_set:
        state.measured_bitstring_matrix = sampling.raw_bitstring_matrix
        state.measured_circuit = sampling.sampled_circuit
        if sampling.sampled_circuit is not None:
            state.sampled_circuits.append((iteration, sampling.sampled_circuit))
    state.work_ledger["recovery_iterations"] += 1
    state.last_sampled_circuit = sampling.sampled_circuit
    state.sampled_sizes.append(int(sampling.raw_bitstring_matrix.shape[0]))
    state.last_sampled_distribution = sampling.last_sampled_distribution
    state.last_raw_distribution = sampling.raw_distribution
    state.last_accepted_distribution = sampling.accepted_distribution
    state.last_invalid_distribution = sampling.invalid_distribution
    state.last_recovered_distribution = sampling.recovered_distribution
    state.last_selected_stage_distribution = sampling.selected_distribution

    batch_outcome = selected_ci_batches(
        iteration=iteration,
        deps=deps,
        options=options,
        rng=rng,
        selected_bits=sampling.selected_bits,
        selected_probs=sampling.selected_probs,
        carryover_ci_strings=state.carryover_ci_strings,
        progress_callback=progress_callback,
    )
    state.work_ledger["selected_ci_batch_solves"] += options.num_batches
    state.avg_occupancies = batch_outcome.selected_occupancies
    state.last_spin_sq = batch_outcome.last_spin_sq
    state.last_selected_ci_summary = batch_outcome.last_selected_ci_summary
    state.carryover_ci_strings = batch_outcome.carryover_ci_strings
    state.last_carryover_summary = batch_outcome.last_carryover_summary
    state.last_batch_energies = batch_outcome.last_batch_energies
    state.selected_ci_dimensions.extend(batch_outcome.selected_ci_dimensions)
    state.selected_ci_fractions.extend(batch_outcome.selected_ci_fractions)

    occupancy_vector = np.concatenate(
        [
            np.asarray(state.avg_occupancies[0], dtype=float),
            np.asarray(state.avg_occupancies[1], dtype=float),
        ]
    )
    state.occupation_history.append(
        {
            "iteration": int(iteration),
            "alpha": np.asarray(state.avg_occupancies[0], dtype=float).tolist(),
            "beta": np.asarray(state.avg_occupancies[1], dtype=float).tolist(),
            "source": "mean_over_valid_batch_ci_states",
        }
    )
    delta_energy, occupancy_delta = iteration_deltas(
        previous_energy=state.previous_energy,
        previous_occupancies=state.previous_occupancies,
        occupancy_vector=occupancy_vector,
        energy_value=batch_outcome.energy_value,
    )
    state.last_selected_distribution = sampling.last_selected_distribution
    best_state_updater(
        state=state,
        iteration=iteration,
        energy_value=batch_outcome.energy_value,
        last_spin_sq=state.last_spin_sq,
        sci_state=batch_outcome.best_sci_state,
        occupancy_vector=occupancy_vector,
    )
    state.selected_fractions.append(sampling.postselection_weight)
    state.sci_energies.append(round(batch_outcome.energy_value, 8))
    state.recovery_trace.append(
        trace_builder(
            iteration=iteration,
            num_batches=options.num_batches,
            requested_samples_per_batch=options.samples_per_batch,
            effective_samples_per_batch=batch_outcome.effective_samples_per_batch,
            symmetrize_spin=options.symmetrize_spin,
            sampling=sampling,
            state=state,
            energy_value=batch_outcome.energy_value,
            delta_energy=delta_energy,
            occupancy_delta=occupancy_delta,
        )
    )
    state.previous_energy = batch_outcome.energy_value
    state.previous_occupancies = occupancy_vector
    state.last_iteration_signature = build_iteration_signature(
        selected_distribution=state.last_selected_distribution,
        selected_ci_summary=state.last_selected_ci_summary,
        occupancy_vector=occupancy_vector,
        recovery_applied=sampling.recovery_applied,
    )
    return SQDIterationOutcome(
        sampling=sampling,
        batch_outcome=batch_outcome,
        delta_energy=delta_energy,
        occupancy_delta=occupancy_delta,
        occupancy_vector=occupancy_vector,
        iter_elapsed=time.monotonic() - iter_start,
    )
