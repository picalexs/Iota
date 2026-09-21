"""SQD workflow orchestration."""

from __future__ import annotations

import logging
import time
from dataclasses import replace
from typing import Any

import numpy as np

from worker.chemistry.algorithms.sqd.config import (
    SQDOptions,
    resolve_sqd_hamiltonian_inputs,
)
from worker.chemistry.algorithms.sqd.config import (
    resolve_sqd_options as _resolve_sqd_options,
)
from worker.chemistry.algorithms.sqd.controller import run_sqd_recovery_loop
from worker.chemistry.algorithms.sqd.convergence import (
    compute_iteration_deltas,
    is_iteration_converged,
    is_iteration_stalled,
)
from worker.chemistry.algorithms.sqd.iteration import (
    SQDIterationOutcome,
    execute_sqd_iteration,
    update_best_observed_state,
)
from worker.chemistry.algorithms.sqd.progress import (
    build_recovery_trace_entry,
    emit_configuration_recovery_progress,
    emit_sqd_progress,
)
from worker.chemistry.algorithms.sqd.recovery import (
    SQDBatchOutcome,
    SQDDependencies,
    run_selected_ci_batches,
)
from worker.chemistry.algorithms.sqd.results import (
    build_sqd_circuit_artifacts,
    build_sqd_result,
    serialize_sqd_circuit_preview,
)
from worker.chemistry.algorithms.sqd.sampling import (
    aggregate_bitstring_frequencies,
    bitstring_from_row,
    bitstrings_to_matrix,
    extract_sampler_bitstrings,
    resolve_measurement_register,
    summarize_bitstring_distribution,
)
from worker.chemistry.algorithms.sqd.sampling_execution import (
    SQDIterationSampling,
    build_hf_reference_circuit,
    run_sqd_sampling_iteration,
    sample_bitstring_matrix,
)
from worker.chemistry.algorithms.sqd.sampling_execution import (
    _is_control_flow_exception as is_control_flow_exception,
)
from worker.chemistry.algorithms.sqd.sampling_execution import (
    _run_sampler_attempt as run_sampler_attempt,
)
from worker.chemistry.algorithms.sqd.selection import (
    extract_carryover_ci_strings,
    postselection_weight,
    resolve_selected_ci_limits,
    selected_ci_fraction,
    selected_ci_strings_from_bitstrings,
)
from worker.chemistry.algorithms.sqd.state import (
    SQDRunState,
    import_sqd_dependencies,
    initial_sqd_run_state,
    log_sqd_setup,
)
from worker.chemistry.progress import ProgressCallback
from worker.chemistry.types import SQDResult

logger = logging.getLogger(__name__)

# Re-export private names for existing solver tests and importers.
_aggregate_bitstring_frequencies = aggregate_bitstring_frequencies
_bitstring_from_sqd_row = bitstring_from_row
_bitstrings_to_matrix = bitstrings_to_matrix
_extract_sqd_sampler_bitstrings = extract_sampler_bitstrings
_resolve_sqd_measurement_register = resolve_measurement_register
_summarize_bitstring_distribution = summarize_bitstring_distribution
_compute_iteration_deltas = compute_iteration_deltas
_selected_ci_fraction = selected_ci_fraction
_postselection_weight = postselection_weight
_SQDOptions = SQDOptions
_resolve_sqd_hamiltonian_inputs = resolve_sqd_hamiltonian_inputs
_resolve_selected_ci_limits = resolve_selected_ci_limits
_extract_carryover_ci_strings = extract_carryover_ci_strings
_selected_ci_strings_from_bitstrings = selected_ci_strings_from_bitstrings
_build_sqd_circuit_artifacts = build_sqd_circuit_artifacts
_build_sqd_result = build_sqd_result
_serialize_circuit_preview = serialize_sqd_circuit_preview
_SQDBatchOutcome = SQDBatchOutcome
_SQDDependencies = SQDDependencies
_run_selected_ci_batches = run_selected_ci_batches
_SQDIterationSampling = SQDIterationSampling
_build_hf_reference_circuit = build_hf_reference_circuit
_sample_bitstring_matrix = sample_bitstring_matrix
_run_sqd_sampler_attempt = run_sampler_attempt
_is_control_flow_exception = is_control_flow_exception
_build_recovery_trace_entry = build_recovery_trace_entry
_emit_configuration_recovery_progress = emit_configuration_recovery_progress
_emit_sqd_progress = emit_sqd_progress
_SQDRunState = SQDRunState
_import_sqd_dependencies = import_sqd_dependencies
_initial_sqd_run_state = initial_sqd_run_state
_log_sqd_setup = log_sqd_setup
_SQDIterationOutcome = SQDIterationOutcome
_update_best_observed_state = update_best_observed_state
_run_sqd_recovery_loop = run_sqd_recovery_loop


def _run_sqd_sampling_iteration(
    *,
    iteration: int,
    backend: object,
    deps: _SQDDependencies,
    options: _SQDOptions,
    rng: np.random.Generator,
    avg_occupancies: tuple[np.ndarray, np.ndarray],
    progress_callback: ProgressCallback | None,
    sampling_circuit_factory: Any | None = None,
    work_ledger: dict[str, int] | None = None,
    measured_bitstring_matrix: np.ndarray | None = None,
    measured_circuit: Any | None = None,
) -> _SQDIterationSampling:
    """Adapt sampling inputs to the focused sampling module."""
    return run_sqd_sampling_iteration(
        iteration=iteration,
        backend=backend,
        deps=deps,
        options=options,
        rng=rng,
        avg_occupancies=avg_occupancies,
        progress_callback=progress_callback,
        sample_bitstrings=_sample_bitstring_matrix,
        sampling_circuit_factory=sampling_circuit_factory,
        work_ledger=work_ledger,
        measured_bitstring_matrix=measured_bitstring_matrix,
        measured_circuit=measured_circuit,
    )


def _is_sqd_iteration_converged(
    *,
    iteration: int,
    delta_energy: float,
    occupancy_delta: float,
    selected_count: int,
    options: _SQDOptions,
) -> bool:
    """Return whether the current SQD iteration satisfies the convergence gate."""
    return is_iteration_converged(
        iteration=iteration,
        delta_energy=delta_energy,
        occupancy_delta=occupancy_delta,
        selected_count=selected_count,
        energy_tolerance=options.energy_tol,
        occupancy_tolerance=options.occupancies_tol,
        min_selected_configurations=options.min_selected_configurations,
    )


def _is_sqd_iteration_stalled(
    *,
    iteration: int,
    delta_energy: float,
    occupancy_delta: float,
    selected_count: int,
    options: _SQDOptions,
    previous_signature: tuple[Any, ...] | None,
    current_signature: tuple[Any, ...] | None,
) -> bool:
    """Return whether SQD reached an unchanged selected-space fixed point."""
    return is_iteration_stalled(
        iteration=iteration,
        delta_energy=delta_energy,
        occupancy_delta=occupancy_delta,
        selected_count=selected_count,
        min_selected_configurations=options.min_selected_configurations,
        energy_tolerance=options.energy_tol,
        occupancy_tolerance=options.occupancies_tol,
        previous_signature=previous_signature,
        current_signature=current_signature,
    )


def _execute_sqd_iteration(
    *,
    iteration: int,
    backend: object,
    deps: _SQDDependencies,
    options: _SQDOptions,
    rng: np.random.Generator,
    state: _SQDRunState,
    progress_callback: ProgressCallback | None,
    sampling_circuit_factory: Any | None = None,
) -> _SQDIterationOutcome:
    """Adapt iteration inputs to the focused iteration module."""
    return execute_sqd_iteration(
        iteration=iteration,
        backend=backend,
        deps=deps,
        options=options,
        rng=rng,
        state=state,
        progress_callback=progress_callback,
        sampling_iteration=_run_sqd_sampling_iteration,
        selected_ci_batches=_run_selected_ci_batches,
        iteration_deltas=_compute_iteration_deltas,
        best_state_updater=_update_best_observed_state,
        trace_builder=_build_recovery_trace_entry,
        sampling_circuit_factory=sampling_circuit_factory,
    )


def run_sqd(
    *,
    hamiltonian: object,
    backend: object,
    config: dict[str, Any],
    progress_callback: ProgressCallback | None = None,
    backend_context: Any | None = None,
    sampling_circuit_factory: Any | None = None,
    sampling_source: str | None = None,
    sampling_provider: dict[str, Any] | None = None,
) -> SQDResult:
    """Run an SQD loop using HamiltonianBundle tensors and addon-sqd APIs."""
    sample_budget = getattr(backend_context, "shots", None)
    options = _resolve_sqd_options(config, hamiltonian, sample_budget=sample_budget)
    chemistry_options = getattr(backend_context, "chemistry_options", {}) or {}
    selected_ci_device = chemistry_options.get("selected_ci_device")
    if selected_ci_device in {None, "", "CPU"}:
        deps = _import_sqd_dependencies()
    else:
        deps = _import_sqd_dependencies(selected_ci_device=selected_ci_device)
    options = replace(
        options,
        selected_ci_requested_device=deps.selected_ci_requested_device,
        selected_ci_actual_device=deps.selected_ci_actual_device,
        selected_ci_provider=deps.selected_ci_provider,
        selected_ci_fallback_reason=deps.selected_ci_fallback_reason,
    )
    _log_sqd_setup(options)

    sqd_wall_start = time.monotonic()
    rng = np.random.default_rng(options.seed)
    state = _run_sqd_recovery_loop(
        backend=backend,
        deps=deps,
        options=options,
        rng=rng,
        progress_callback=progress_callback,
        initialize_state=_initial_sqd_run_state,
        execute_iteration=_execute_sqd_iteration,
        emit_progress=_emit_configuration_recovery_progress,
        is_converged=_is_sqd_iteration_converged,
        is_stalled=_is_sqd_iteration_stalled,
        sampling_circuit_factory=sampling_circuit_factory,
    )

    return _build_sqd_result(
        backend=backend,
        options=options,
        state=state,
        sqd_total_elapsed=time.monotonic() - sqd_wall_start,
        sampling_source=(
            sampling_source
            or ("provided_circuit" if sampling_circuit_factory is not None else "hf_single_determinant")
        ),
        sampling_provider=sampling_provider,
    )
