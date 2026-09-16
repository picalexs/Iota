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
    timing_components["algorithm_dispatch_seconds"] = algorithm_seconds
    timing_components["segment_wall_seconds"] = segment_wall
    timing_components["total_wall_seconds"] = total_wall
    measured_seconds = sum(
        value
        for key, value in timing_components.items()
        if key
        not in {
            "total_wall_seconds",
            "segment_wall_seconds",
            "unattributed_lifecycle_seconds",
        }
        and isinstance(value, (int, float))
    )
    timing_components["unattributed_lifecycle_seconds"] = max(segment_wall - measured_seconds, 0.0)
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
