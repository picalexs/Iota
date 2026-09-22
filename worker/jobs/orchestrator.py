"""Ordered dispatch and result-finalization story for worker runs."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from functools import partial
from typing import Any

from shared.estimation import estimate_workload_breakdown
from worker.chemistry.projected_execution import resolve_projected_execution_policy

from .execution_segments import execution_duration_seconds
from .result_normalization import WORKER_RUNTIME_BASIS
from .run_execution.contracts import (
    EventInserter,
    PreparedRunContext,
    SessionFactory,
    StartedRunContext,
    TransactionCommitter,
)

logger = logging.getLogger(__name__)

_TIMING_LEDGER_VERSION = 1


def _numeric_seconds(value: Any) -> float | None:
    if isinstance(value, (int, float)) and value >= 0:
        return float(value)
    return None


def _algorithm_stage_timing(result: dict[str, Any]) -> dict[str, float]:
    """Normalize algorithm-reported nested timers without double counting them."""
    metrics = result.get("algorithm_metrics")
    if not isinstance(metrics, dict):
        return {}
    candidates: list[dict[str, Any]] = []
    matrix_summary = metrics.get("matrix_element_summary")
    if isinstance(matrix_summary, dict):
        breakdown = matrix_summary.get("timing_breakdown")
        if isinstance(breakdown, dict):
            candidates.append(breakdown)
    sci_package = metrics.get("sci_result_package")
    if isinstance(sci_package, dict):
        breakdown = sci_package.get("timing_breakdown")
        if isinstance(breakdown, dict):
            candidates.append(breakdown)
    for key in ("timing_breakdown", "timing"):
        breakdown = metrics.get(key)
        if isinstance(breakdown, dict):
            candidates.append(breakdown)

    normalized: dict[str, float] = {}
    aliases = {
        "state_generation_or_sampling_seconds": (
            "state_evolution_seconds",
            "matrix_element_estimation_seconds",
            "sampling_seconds",
        ),
        "selected_ci_seconds": ("selected_ci_seconds",),
        "projected_solve_seconds": ("projected_solve_seconds",),
        "algorithm_preparation_seconds": ("preparation_seconds",),
        "algorithm_solve_postprocess_seconds": ("solve_and_postprocess_seconds",),
        "optimizer_wall_seconds": ("optimizer_wall_time_seconds",),
    }
    for output_key, source_keys in aliases.items():
        for candidate in candidates:
            value = None
            for source_key in source_keys:
                value = _numeric_seconds(candidate.get(source_key))
                if value is not None:
                    break
            if value is not None:
                normalized[output_key] = value
                break
    return normalized


def _cpu_stage_seconds(
    *,
    timing_components: dict[str, Any],
    stage_timing: dict[str, float],
    resource_metadata: dict[str, Any],
) -> float:
    """Sum only known CPU-owned wall times; unknown work stays unattributed."""
    values: list[float] = []
    for key in ("backend_setup_seconds", "casci_seconds", "pauli_build_seconds"):
        value = _numeric_seconds(timing_components.get(key) or resource_metadata.get(key))
        if value is not None:
            values.append(value)
    reference_device = resource_metadata.get("reference_device_actual")
    if reference_device != "GPU":
        value = _numeric_seconds(resource_metadata.get("reference_scf_seconds"))
        if value is not None:
            values.append(value)
    projected = stage_timing.get("projected_solve_seconds")
    if projected is not None:
        values.append(projected)
    return sum(values)


def dispatch_and_finalize_run(
    *,
    run_id_str: str,
    started: StartedRunContext,
    prepared: PreparedRunContext,
    progress_state: dict[str, Any],
    run_wall_start: float,
    session_factory: SessionFactory,
    insert_run_event: EventInserter,
    commit_transaction: TransactionCommitter,
    **execution_dependencies: Any,
) -> dict[str, Any]:
    """Dispatch a prepared run and apply its terminal result metadata.

    Persistence and solver behavior remain owned by injected boundaries. This
    function only makes the ordered execution story explicit.
    """
    estimate_total_iterations = execution_dependencies["estimate_total_iterations"]
    emit_progress_update = execution_dependencies["emit_progress_update"]
    build_telemetry_estimate = execution_dependencies["build_telemetry_estimate"]
    persist_latest_estimate = execution_dependencies["persist_latest_estimate"]
    dispatch_algorithm = execution_dependencies["dispatch_algorithm"]
    pause_after_dispatch = execution_dependencies["pause_after_dispatch"]
    normalize_result = execution_dependencies["normalize_result"]
    apply_result_metadata = execution_dependencies["apply_result_metadata"]
    reconcile_reported_iterations = execution_dependencies["reconcile_reported_iterations"]
    uses_branch_matrix_elements = execution_dependencies["uses_branch_matrix_elements"]
    emit_fallback_completion_progress = execution_dependencies["emit_fallback_completion_progress"]
    projected_branch_path = None
    if started.algorithm in {"kqd", "qfd"}:
        projected_branch_path = (
            resolve_projected_execution_policy(
                hamiltonian=prepared.hamiltonian_bundle,
                backend_context=prepared.backend_context,
            ).actual_path
            == "branch_estimator"
        )
    progress_total = estimate_total_iterations(
        started.algorithm,
        started.algorithm_config,
        num_qubits=prepared.hamiltonian_bundle.num_qubits,
        backend_target=started.backend_target,
        noise_profile_enabled=prepared.backend_context.noise_profile is not None,
        projected_branch_path=projected_branch_path,
    )
    workload_fields = estimate_workload_breakdown(
        algorithm=started.algorithm,
        config_payload=started.algorithm_config,
        num_qubits=prepared.hamiltonian_bundle.num_qubits,
        backend_target=started.backend_target,
        noise_profile_enabled=prepared.backend_context.noise_profile is not None,
        projected_branch_path=projected_branch_path,
    )

    with session_factory() as db:
        progress_callback = partial(
            emit_progress_update,
            db=db,
            run_id=run_id_str,
            execution_generation=started.expected_generation,
            algorithm=started.algorithm,
            progress_state=progress_state,
            progress_total=progress_total,
            hamiltonian_bundle=prepared.hamiltonian_bundle,
            backend_target=started.backend_target,
            eta_seed_seconds_per_iteration=started.eta_seed_seconds_per_iteration,
            eta_seed_confidence=started.eta_seed_confidence,
            workload_fields=workload_fields,
        )

        initial_estimate = build_telemetry_estimate(
            algorithm=started.algorithm,
            total_iterations=progress_total,
            completed_iterations=0,
            hamiltonian_bundle=prepared.hamiltonian_bundle,
            backend_target=started.backend_target,
            elapsed_seconds=None,
            ema_state=progress_state,
            seed_seconds_per_iteration=started.eta_seed_seconds_per_iteration,
            seed_confidence=started.eta_seed_confidence,
            workload_fields=workload_fields,
        )
        persist_latest_estimate(db, run_id_str, initial_estimate)
        insert_run_event(db, run_id_str, "estimate_updated", initial_estimate)
        commit_transaction(db)

        progress_state["start_time"] = time.monotonic()
        logger.info(
            "Run %s: dispatching algorithm=%s total_iterations=%d "
            "num_qubits=%d backend=%s eta_seeded=%s",
            run_id_str,
            started.algorithm,
            progress_total,
            prepared.hamiltonian_bundle.num_qubits,
            started.backend_target,
            "yes" if started.eta_seed_seconds_per_iteration is not None else "no",
        )
        algorithm_started = time.monotonic()
        raw_result = dispatch_algorithm(
            algorithm=started.algorithm,
            backend=prepared.backend_adapter,
            config_snapshot=started.algorithm_config,
            hamiltonian_bundle=prepared.hamiltonian_bundle,
            progress_callback=progress_callback,
            backend_context=prepared.backend_context,
        )
        algorithm_seconds = time.monotonic() - algorithm_started

        pause_after_dispatch(
            db,
            run_id=run_id_str,
            execution_generation=started.expected_generation,
            algorithm=started.algorithm,
            progress_state=progress_state,
        )

        result = normalize_result(raw_result, prepared.hamiltonian_bundle.metadata)
        apply_result_metadata(
            result,
            algorithm=started.algorithm,
            mode=started.mode,
            backend_target=started.backend_target,
            chemistry_input=started.chemistry_input,
            backend_adapter=prepared.backend_adapter,
            backend_context=prepared.backend_context,
        )
        reconcile_reported_iterations(
            result,
            progress_state=progress_state,
            preserve_branch_matrix_elements=uses_branch_matrix_elements(result),
        )
        emit_fallback_completion_progress(
            result,
            progress_state=progress_state,
            algorithm=started.algorithm,
            progress_callback=progress_callback,
        )

    segment_wall = max(time.monotonic() - run_wall_start, 0.0)
    total_wall = execution_duration_seconds(progress_state)
    timing_components = dict(progress_state.get("timing_components") or {})
    timing_metadata = progress_state.get("timing_metadata")
    if isinstance(timing_metadata, dict):
        timing_components.update(timing_metadata)
    timing_components["algorithm_dispatch_seconds"] = algorithm_seconds
    resource_metadata = prepared.backend_context.resource_metadata
    for source_key, timing_key in (
        ("aer_simulation_seconds", "aer_simulation_seconds"),
        ("reference_transfer_seconds", "reference_transfer_seconds"),
    ):
        value = resource_metadata.get(source_key)
        if isinstance(value, (int, float)):
            timing_components[timing_key] = max(float(value), 0.0)
    algorithm_stage_timing = _algorithm_stage_timing(result)
    reference_scf_seconds = _numeric_seconds(resource_metadata.get("reference_scf_seconds"))
    casci_seconds = _numeric_seconds(resource_metadata.get("casci_seconds"))
    pauli_build_seconds = _numeric_seconds(resource_metadata.get("pauli_build_seconds"))
    hamiltonian_total_seconds = _numeric_seconds(
        resource_metadata.get("hamiltonian_total_seconds")
    )
    stage_wall_seconds: dict[str, float | None] = {
        "backend_setup": _numeric_seconds(timing_components.get("backend_setup_seconds")),
        "reference_scf": reference_scf_seconds,
        "hamiltonian_build": hamiltonian_total_seconds
        or _numeric_seconds(timing_components.get("hamiltonian_preparation_seconds")),
        "state_generation_or_sampling": algorithm_stage_timing.get(
            "state_generation_or_sampling_seconds"
        ),
        "selected_ci": algorithm_stage_timing.get("selected_ci_seconds"),
        "projected_solve": algorithm_stage_timing.get("projected_solve_seconds"),
        "finalize": None,
    }
    timing_components["timing_ledger_version"] = _TIMING_LEDGER_VERSION
    timing_components["stage_wall_seconds"] = stage_wall_seconds
    timing_components["algorithm_stage_timing"] = algorithm_stage_timing
    timing_components["aer_simulation_wall_seconds"] = timing_components.get(
        "aer_simulation_seconds"
    )
    timing_components["transfer_wall_seconds"] = timing_components.get(
        "reference_transfer_seconds", 0.0
    )
    chemistry_gpu_seconds = (
        reference_scf_seconds
        if resource_metadata.get("reference_device_actual") == "GPU"
        else 0.0
    )
    timing_components["chemistry_gpu_wall_seconds"] = chemistry_gpu_seconds
    timing_components["cpu_stage_wall_seconds"] = _cpu_stage_seconds(
        timing_components=timing_components,
        stage_timing=algorithm_stage_timing,
        resource_metadata=resource_metadata,
    )
    timing_components["timing_accounting"] = "exclusive_top_level_plus_nested_stage_wall"
    timing_components["segment_wall_seconds"] = segment_wall
    timing_components["worker_wall_seconds"] = segment_wall
    timing_components["total_wall_seconds"] = total_wall
    exclusive_keys = (
        "backend_setup_seconds",
        "hamiltonian_preparation_seconds",
        "algorithm_dispatch_seconds",
    )
    exclusive_seconds = sum(
        value
        for key in exclusive_keys
        for value in [_numeric_seconds(timing_components.get(key))]
        if value is not None
    )
    timing_components["unattributed_worker_seconds"] = max(
        segment_wall - exclusive_seconds, 0.0
    )
    timing_components["unattributed_lifecycle_seconds"] = timing_components[
        "unattributed_worker_seconds"
    ]
    timing_components["idle_gap_seconds"] = None
    timing_components["idle_gap_status"] = "unavailable_without_stage_markers"
    timing_components["timing_basis"] = WORKER_RUNTIME_BASIS
    result["execution_timing"] = timing_components
    result_metrics = result.get("algorithm_metrics")
    if isinstance(result_metrics, dict):
        result_metrics["execution_timing"] = timing_components
    raw_result = result.get("raw_result")
    if isinstance(raw_result, dict):
        raw_result["execution_timing"] = timing_components
        raw_metrics = raw_result.get("algorithm_metrics")
        if isinstance(raw_metrics, dict):
            raw_metrics["execution_timing"] = timing_components
    result["runtime_seconds"] = total_wall
    result["runtime_basis"] = WORKER_RUNTIME_BASIS
    result["run_finished_at"] = datetime.now(UTC).isoformat()
    logger.info(
        "Run %s completed successfully algorithm=%s energy=%s iterations=%s wall_time=%.3fs",
        run_id_str,
        result.get("algorithm", started.algorithm),
        result.get("primary_energy", result.get("energy")),
        result.get("primary_iterations", result.get("iterations")),
        total_wall,
    )
    return result


__all__ = ["dispatch_and_finalize_run"]
