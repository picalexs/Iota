"""Outer recovery-loop orchestration for SQD."""

from __future__ import annotations

import logging
from collections.abc import Callable

import numpy as np

from worker.chemistry.algorithms.sqd.config import SQDOptions
from worker.chemistry.algorithms.sqd.iteration import SQDIterationOutcome
from worker.chemistry.algorithms.sqd.recovery import SQDDependencies
from worker.chemistry.algorithms.sqd.state import SQDRunState
from worker.chemistry.progress import ProgressCallback

logger = logging.getLogger(__name__)


def run_sqd_recovery_loop(
    *,
    backend: object,
    deps: SQDDependencies,
    options: SQDOptions,
    rng: np.random.Generator,
    progress_callback: ProgressCallback | None,
    initialize_state: Callable[[SQDOptions], SQDRunState],
    execute_iteration: Callable[..., SQDIterationOutcome],
    emit_progress: Callable[..., None],
    is_converged: Callable[..., bool],
    is_stalled: Callable[..., bool] | None = None,
    sampling_circuit_factory: Callable[..., object] | None = None,
) -> SQDRunState:
    """Run SQD iterations until convergence or the configured limit."""
    state = initialize_state(options)
    for iteration in range(1, options.max_iterations + 1):
        previous_signature = state.last_iteration_signature
        outcome = execute_iteration(
            iteration=iteration,
            backend=backend,
            deps=deps,
            options=options,
            rng=rng,
            state=state,
            progress_callback=progress_callback,
            sampling_circuit_factory=sampling_circuit_factory,
        )
        logger.debug(
            "SQD iter=%d energy=%.8f delta_energy=%.2e occ_delta=%.2e "
            "selected=%d/%d (%.1f%%) elapsed=%.3fs",
            iteration,
            outcome.batch_outcome.energy_value,
            outcome.delta_energy if np.isfinite(outcome.delta_energy) else 0.0,
            outcome.occupancy_delta if np.isfinite(outcome.occupancy_delta) else 0.0,
            int(outcome.sampling.selected_bits.shape[0]),
            int(outcome.sampling.raw_bitstring_matrix.shape[0]),
            100.0 * outcome.sampling.postselection_weight,
            outcome.iter_elapsed,
        )
        converged = is_converged(
            iteration=iteration,
            delta_energy=outcome.delta_energy,
            occupancy_delta=outcome.occupancy_delta,
            selected_count=int(outcome.sampling.selected_bits.shape[0]),
            options=options,
        )
        if converged:
            state.termination_reason = "converged"
            state.converged = True
        elif is_stalled is not None and is_stalled(
            iteration=iteration,
            delta_energy=outcome.delta_energy,
            occupancy_delta=outcome.occupancy_delta,
            selected_count=int(outcome.sampling.selected_bits.shape[0]),
            options=options,
            previous_signature=previous_signature,
            current_signature=state.last_iteration_signature,
        ):
            state.termination_reason = "fixed_point_insufficient_selected_configurations"
        elif iteration >= options.max_iterations:
            state.termination_reason = "max_iterations"

        emit_progress(
            iteration=iteration,
            options=options,
            sampling=outcome.sampling,
            state=state,
            energy_value=outcome.batch_outcome.energy_value,
            delta_energy=outcome.delta_energy,
            occupancy_delta=outcome.occupancy_delta,
            iter_elapsed=outcome.iter_elapsed,
            termination_reason=state.termination_reason,
            progress_callback=progress_callback,
        )

        if converged or state.termination_reason is not None:
            break

    return state
