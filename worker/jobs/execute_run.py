"""Run execution job entrypoint."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from shared.estimation import (
    estimate_total_iterations as _shared_estimate_total_iterations,
)
from worker.adapters.base import BackendExecutionContext
from worker.adapters.result_adapter import normalize_result
from worker.chemistry.backend_selector import select_backend
from worker.chemistry.types import ChemistryInput, HamiltonianBundle
from worker.db import commit_transaction, get_db_session
from worker.persistence.run_repository import SqlRunRepository

from . import _hamiltonian_cache
from . import ibm_observation as _ibm_observation
from . import local_observation as _local_observation
from ._credential_profiles import inject_profile_credentials
from ._hamiltonian_cache import _HAMILTONIAN_CACHE as _HAMILTONIAN_CACHE
from ._hamiltonian_cache import (
    clear_hamiltonian_bundle_cache as clear_hamiltonian_bundle_cache,
)
from ._progress_tracking import (
    _build_telemetry_estimate,
    _persist_latest_estimate,
)
from ._progress_tracking import (
    _compute_elapsed_seconds as _compute_elapsed_seconds,
)
from .backend_context import (
    build_backend_context_for_run as _build_backend_context,
)
from .control_state import (
    RunCancelled as _ControlRunCancelled,
)
from .control_state import (
    RunPaused as _ControlRunPaused,
)
from .control_state import (
    build_primitive_run_guard as _build_control_primitive_run_guard,
)
from .control_state import (
    check_progress_control_state as _check_control_progress_state,
)
from .control_state import (
    finalize_cooperative_pause as _finalize_controlled_pause,
)
from .control_state import (
    handle_pre_start_control_state as _handle_control_pre_start,
)
from .control_state import (
    handle_setup_control_state as _handle_control_setup,
)
from .control_state import (
    pause_after_dispatch_if_requested as _pause_control_after_dispatch,
)
from .control_state import (
    save_pause_checkpoint as _save_control_pause_checkpoint,
)
from .dispatcher import dispatch_algorithm
from .execution_config import (
    _backend_options_from_config,
    _chemistry_options_from_config,
    _estimate_seed_from_snapshot,
    _extract_run_context,
    _runtime_algorithm_config,
)
from .execution_metadata import (
    active_space_payload as _active_space_payload,
)
from .execution_metadata import (
    apply_result_metadata as _apply_result_metadata,
)
from .execution_metadata import (
    build_hamiltonian_message as _build_hamiltonian_message,
)
from .execution_metadata import (
    build_setup_payload as _build_setup_payload,
)
from .execution_metadata import (
    merge_backend_metadata as _merge_backend_metadata,
)
from .execution_metadata import (
    uses_branch_matrix_elements as _uses_branch_matrix_elements,
)
from .execution_segments import (
    finish_execution_segment as _finish_execution_segment,
)
from .execution_segments import (
    segment_started_monotonic as _segment_started_monotonic,
)
from .execution_segments import (
    start_execution_segment as _start_execution_segment,
)
from .ibm_observation import (
    IBMObservationMetadata as _IBMObservationMetadata,
)
from .ibm_observation import (
    build_ibm_primitive_job_observer as _build_ibm_primitive_job_observer_impl,
)
from .ibm_observation import (
    emit_ibm_runtime_snapshot_events as _emit_ibm_runtime_snapshot_events_impl,
)
from .ibm_observation import (
    persist_ibm_runtime_snapshot as _persist_ibm_runtime_snapshot_impl,
)
from .lifecycle import (
    current_execution_generation as _current_execution_generation,
)
from .lifecycle import (
    force_run_running as _force_run_running,
)
from .lifecycle import (
    load_chemistry_input as _load_chemistry_input,
)
from .lifecycle import (
    load_run_row_snapshot as _load_run_row_snapshot,
)
from .lifecycle import (
    mark_run_running as _mark_run_running,
)
from .local_observation import (
    build_local_primitive_job_observer as _build_local_primitive_job_observer_impl,
)
from .orchestrator import dispatch_and_finalize_run as _dispatch_and_finalize_run_impl
from .preparation import prepare_backend_and_hamiltonian as _prepare_backend_and_hamiltonian_impl
from .progress import (
    emit_fallback_completion_progress as _emit_fallback_completion_progress,
)
from .progress import (
    reconcile_reported_iterations as _reconcile_reported_iterations,
)
from .progress_persistence import emit_progress_update as _emit_progress_update
from .run_execution.contracts import (
    PreparedRunContext,
    StartedRunContext,
)

logger = logging.getLogger(__name__)

_DEFAULT_ITERATIONS = 10
_IBM_STATUS_POLL_INTERVAL_SECONDS = 15.0
_MIN_RELIABLE_SEED_CONFIDENCE = 0.65

_ORIGINAL_BUILD_MOLECULE = _hamiltonian_cache.build_molecule
_ORIGINAL_BUILD_QUBIT_HAMILTONIAN = _hamiltonian_cache.build_qubit_hamiltonian

# Re-exported for tests and import compatibility with the pre-split module.
build_molecule = _ORIGINAL_BUILD_MOLECULE
build_qubit_hamiltonian = _ORIGINAL_BUILD_QUBIT_HAMILTONIAN


_RunCancelled = _ControlRunCancelled
_RunPaused = _ControlRunPaused
_ObservedLocalPrimitiveJob = _local_observation.ObservedLocalPrimitiveJob

# Re-export the pre-split private observation helpers for existing importers.
_ObservedIBMJob = _ibm_observation.ObservedIBMJob
_build_ibm_timing = _ibm_observation.build_ibm_timing
_call_noarg = _ibm_observation.call_noarg
_extract_ibm_metrics = _ibm_observation.extract_ibm_metrics
_extract_ibm_observation_metadata = _ibm_observation.extract_observation_metadata
_extract_ibm_status = _ibm_observation.extract_ibm_status
_extract_queue_position = _ibm_observation.extract_queue_position
_coerce_int = _ibm_observation.coerce_int
_coerce_str = _ibm_observation.coerce_str
_event_payload_for_ibm_snapshot = _ibm_observation.event_payload_for_snapshot
_is_ibm_final_status = _ibm_observation.is_ibm_final_status
_next_ibm_run_status = _ibm_observation.next_ibm_run_status
_normalize_ibm_status = _ibm_observation.normalize_ibm_status
_primitive_type_from_snapshot = _ibm_observation.primitive_type_from_snapshot
_replace_result_timeout = _ibm_observation.replace_result_timeout
_result_timeout = _ibm_observation.result_timeout
_runtime_metadata_for_ibm_snapshot = _ibm_observation.runtime_metadata_for_snapshot
_request_ibm_job_cancel = _ibm_observation.request_ibm_job_cancel


def _append_run_event(
    session: Session,
    run_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    """Append an event through the repository for injected setup callbacks."""
    SqlRunRepository(session).append_event(run_id, event_type, payload)


def _build_primitive_run_guard(run_id: str) -> Callable[[], None]:
    """Stop primitive submissions once the run is cancelled or pausing."""
    return _build_control_primitive_run_guard(
        run_id,
        session_factory=lambda: get_db_session(),
        repository_factory=SqlRunRepository,
    )


def _emit_setup_milestone(
    run_id: str,
    *,
    stage: str,
    algorithm: str,
    mode: str,
    backend_target: str,
    message: str,
    extra: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {
        "stage": "setup",
        "step": stage,
        "algorithm": algorithm,
        "mode": mode,
        "backend_target": backend_target,
        "message": message,
    }
    if extra:
        payload.update(extra)

    with get_db_session() as session:
        _append_run_event(session, run_id, "iteration_update", payload)


def _save_pause_checkpoint(
    session: Any,
    run_id: str,
    *,
    execution_generation: int,
    algorithm: str,
    payload: dict[str, Any],
) -> None:
    """Persist a pause checkpoint and move the run to PAUSED."""
    _save_control_pause_checkpoint(
        session,
        run_id,
        execution_generation=execution_generation,
        algorithm=algorithm,
        payload=payload,
        repository_factory=SqlRunRepository,
    )


def _finalize_cooperative_pause(
    run_id: str,
    *,
    execution_generation: int,
    algorithm: str,
    payload: dict[str, Any],
) -> None:
    """Ensure a guard-triggered pause leaves the run checkpointed as PAUSED."""
    _finalize_controlled_pause(
        run_id,
        execution_generation=execution_generation,
        algorithm=algorithm,
        payload=payload,
        session_factory=get_db_session,
        repository_factory=SqlRunRepository,
    )


def _emit_ibm_runtime_snapshot_events(
    session: Any,
    *,
    run_id: str,
    current_status: str | None,
    next_run_status: str,
    phase: str,
    job_id: str | None,
    event_payload: dict[str, Any],
) -> None:
    _emit_ibm_runtime_snapshot_events_impl(
        SqlRunRepository(session),
        run_id=run_id,
        current_status=current_status,
        next_run_status=next_run_status,
        phase=phase,
        job_id=job_id,
        event_payload=event_payload,
    )


def _record_ibm_runtime_snapshot(
    *,
    run_id: str,
    run_wall_start: float,
    phase: str,
    snapshot: dict[str, Any],
    observation: _IBMObservationMetadata,
    job: Any,
) -> None:
    _persist_ibm_runtime_snapshot_impl(
        run_id=run_id,
        run_wall_start=run_wall_start,
        phase=phase,
        snapshot=snapshot,
        observation=observation,
        job=job,
        session_factory=lambda: get_db_session(),
        repository_factory=SqlRunRepository,
        request_job_cancel=_request_ibm_job_cancel,
        cancellation_error_factory=_RunCancelled,
    )


def _build_ibm_primitive_job_observer(
    *,
    run_id: str,
    run_wall_start: float,
) -> Callable[[Any, dict[str, Any]], Any | None]:
    def record_snapshot(
        phase: str,
        snapshot: dict[str, Any],
        observation: _IBMObservationMetadata,
        job: Any,
    ) -> None:
        _record_ibm_runtime_snapshot(
            run_id=run_id,
            run_wall_start=run_wall_start,
            phase=phase,
            snapshot=snapshot,
            observation=observation,
            job=job,
        )

    return _build_ibm_primitive_job_observer_impl(
        record_snapshot=record_snapshot,
        cancellation_error_factory=_RunCancelled,
    )


def _build_local_primitive_job_observer(
    *,
    run_id: str,
) -> Callable[[Any, dict[str, Any]], Any | None]:
    return _build_local_primitive_job_observer_impl(
        run_id=run_id,
        run_guard_factory=_build_primitive_run_guard,
    )


def _build_hamiltonian_bundle(
    *,
    chemistry_input: ChemistryInput,
    chemistry_options: dict[str, Any] | None = None,
) -> HamiltonianBundle:
    """Compatibility wrapper for the extracted Hamiltonian cache seam."""
    if (
        build_molecule is _ORIGINAL_BUILD_MOLECULE
        and build_qubit_hamiltonian is _ORIGINAL_BUILD_QUBIT_HAMILTONIAN
    ):
        return _hamiltonian_cache._build_hamiltonian_bundle(
            chemistry_input=chemistry_input,
            chemistry_options=chemistry_options,
        )

    original_build_molecule = _hamiltonian_cache.build_molecule
    original_build_qubit_hamiltonian = _hamiltonian_cache.build_qubit_hamiltonian
    _hamiltonian_cache.build_molecule = build_molecule
    _hamiltonian_cache.build_qubit_hamiltonian = build_qubit_hamiltonian
    try:
        return _hamiltonian_cache._build_hamiltonian_bundle(
            chemistry_input=chemistry_input,
            chemistry_options=chemistry_options,
        )
    finally:
        _hamiltonian_cache.build_molecule = original_build_molecule
        _hamiltonian_cache.build_qubit_hamiltonian = original_build_qubit_hamiltonian


def _estimate_total_iterations(
    algorithm: str,
    config_snapshot: dict[str, Any],
    *,
    num_qubits: int | None = None,
    backend_target: str | None = None,
    noise_profile_enabled: bool | None = None,
    projected_branch_path: bool | None = None,
) -> int:
    """Estimate total iterations for live telemetry before dispatch starts."""
    return _shared_estimate_total_iterations(
        algorithm=algorithm,
        config_payload=config_snapshot,
        num_qubits=num_qubits,
        backend_target=backend_target,
        noise_profile_enabled=noise_profile_enabled,
        projected_branch_path=projected_branch_path,
    )


def _stopped_run_result(
    algorithm: str,
    *,
    iterations: int = 0,
    status: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "algorithm": algorithm,
        "primary_energy": None,
        "primary_iterations": iterations,
        "energy": None,
        "iterations": iterations,
        "optimal_parameters": [],
        "converged": False,
    }
    if status is not None:
        result["status"] = status
    return result


def _stale_run_result() -> dict[str, Any]:
    return _stopped_run_result("unknown", status="STALE")


def _handle_pre_start_control_state(
    session: Any,
    *,
    run_id: str,
    execution_generation: int,
    algorithm: str,
    progress_state: dict[str, Any],
) -> dict[str, Any] | None:
    return _handle_control_pre_start(
        session,
        run_id=run_id,
        execution_generation=execution_generation,
        algorithm=algorithm,
        progress_state=progress_state,
        repository_factory=SqlRunRepository,
        stopped_run_result=_stopped_run_result,
    )


def _handle_setup_control_state(
    session: Any,
    *,
    run_id: str,
    execution_generation: int,
    algorithm: str,
    progress_state: dict[str, Any],
    config_snapshot: dict[str, Any],
    hamiltonian_bundle: HamiltonianBundle,
) -> dict[str, Any] | None:
    return _handle_control_setup(
        session,
        run_id=run_id,
        execution_generation=execution_generation,
        algorithm=algorithm,
        progress_state=progress_state,
        config_snapshot=config_snapshot,
        hamiltonian_bundle=hamiltonian_bundle,
        repository_factory=SqlRunRepository,
        stopped_run_result=_stopped_run_result,
    )


def _check_progress_control_state(
    db: Any,
    *,
    run_id: str,
    execution_generation: int,
    algorithm: str,
    progress_state: dict[str, Any],
    payload: dict[str, Any],
) -> None:
    _check_control_progress_state(
        db,
        run_id=run_id,
        execution_generation=execution_generation,
        algorithm=algorithm,
        progress_state=progress_state,
        payload=payload,
        repository_factory=SqlRunRepository,
    )


def _pause_after_dispatch_if_requested(
    db: Any,
    *,
    run_id: str,
    execution_generation: int,
    algorithm: str,
    progress_state: dict[str, Any],
) -> None:
    _pause_control_after_dispatch(
        db,
        run_id=run_id,
        execution_generation=execution_generation,
        algorithm=algorithm,
        progress_state=progress_state,
        repository_factory=SqlRunRepository,
    )


def _start_run_context(
    *,
    run_id_str: str,
    expected_generation: int | None,
    progress_state: dict[str, Any],
) -> tuple[StartedRunContext | None, dict[str, Any] | None]:
    with get_db_session() as session:
        current_generation = _current_execution_generation(session, run_id_str)
        if expected_generation is None:
            expected_generation = current_generation
        if current_generation != expected_generation:
            logger.info(
                "Run %s generation %s is stale; current generation is %s",
                run_id_str,
                expected_generation,
                current_generation,
            )
            return None, _stale_run_result()

        run_started_at = datetime.now(UTC).isoformat()
        rowcount = _mark_run_running(
            session,
            run_id=run_id_str,
            execution_generation=expected_generation,
            run_started_at=run_started_at,
        )
        if rowcount == 0:
            early_result = _handle_pre_start_control_state(
                session,
                run_id=run_id_str,
                execution_generation=expected_generation,
                algorithm="vqe",
                progress_state=progress_state,
            )
            if early_result is not None:
                return None, early_result
            forced_rowcount = _force_run_running(
                session,
                run_id=run_id_str,
                execution_generation=expected_generation,
                run_started_at=run_started_at,
            )
            if forced_rowcount == 0:
                control_status = SqlRunRepository(session).request_control_state(
                    run_id_str,
                    expected_generation,
                )
                if control_status is not None:
                    logger.info(
                        "Run %s was not claimable by generation %s; status=%s",
                        run_id_str,
                        expected_generation,
                        control_status,
                    )
                    return None, _stale_run_result()

        run_row_snapshot = _load_run_row_snapshot(session, run_id_str)
        run_context = _extract_run_context(run_row_snapshot)
        eta_seed_seconds_per_iteration, eta_seed_confidence = _estimate_seed_from_snapshot(
            run_row_snapshot
        )
        algorithm_config = _runtime_algorithm_config(
            run_context.config_snapshot,
            run_context.algorithm,
        )
        backend_options_runtime = _backend_options_from_config(
            run_context.config_snapshot,
            credential_profile_id=(
                run_row_snapshot.get("credential_profile_id") if run_row_snapshot else None
            ),
        )
        chemistry_options_runtime = _chemistry_options_from_config(run_context.config_snapshot)
        if backend_options_runtime.get("credential_profile_id"):
            backend_options_runtime = inject_profile_credentials(session, backend_options_runtime)

        chemistry_input = _load_chemistry_input(
            session,
            run_id=run_id_str,
            config_snapshot=run_context.config_snapshot,
        )
        _start_execution_segment(
            session,
            run_id=run_id_str,
            execution_generation=expected_generation,
            worker_started_at=datetime.now(UTC),
            progress_state=progress_state,
        )
        _append_run_event(session, run_id_str, "status_changed", {"status": "RUNNING"})

    return (
        StartedRunContext(
            expected_generation=expected_generation,
            algorithm=run_context.algorithm,
            mode=run_context.mode,
            backend_target=run_context.backend_target,
            config_snapshot=run_context.config_snapshot,
            algorithm_config=algorithm_config,
            backend_options_runtime=backend_options_runtime,
            chemistry_options_runtime=chemistry_options_runtime,
            chemistry_input=chemistry_input,
            eta_seed_seconds_per_iteration=eta_seed_seconds_per_iteration,
            eta_seed_confidence=eta_seed_confidence,
        ),
        None,
    )


def _build_backend_context_for_run(
    *,
    run_id_str: str,
    backend_target: str,
    backend_options_runtime: dict[str, Any],
    config_snapshot: dict[str, Any],
    run_wall_start: float,
) -> BackendExecutionContext:
    return _build_backend_context(
        run_id=run_id_str,
        backend_target=backend_target,
        backend_options_runtime=backend_options_runtime,
        config_snapshot=config_snapshot,
        run_wall_start=run_wall_start,
        run_guard_factory=_build_primitive_run_guard,
        ibm_job_observer_factory=_build_ibm_primitive_job_observer,
        local_job_observer_factory=_build_local_primitive_job_observer,
    )


def _prepare_backend_and_hamiltonian(
    *,
    run_id_str: str,
    started: StartedRunContext,
    progress_state: dict[str, Any],
    run_wall_start: float,
) -> tuple[PreparedRunContext | None, dict[str, Any] | None]:
    return _prepare_backend_and_hamiltonian_impl(
        run_id_str=run_id_str,
        started=started,
        progress_state=progress_state,
        run_wall_start=run_wall_start,
        build_backend_context=_build_backend_context_for_run,
        select_backend=select_backend,
        build_hamiltonian_bundle=_build_hamiltonian_bundle,
        emit_setup_milestone=_emit_setup_milestone,
        handle_setup_control_state=_handle_setup_control_state,
        build_hamiltonian_message=_build_hamiltonian_message,
        active_space_payload=_active_space_payload,
        merge_backend_metadata=_merge_backend_metadata,
        build_setup_payload=_build_setup_payload,
        session_factory=get_db_session,
        insert_run_event=_append_run_event,
    )


def _dispatch_and_finalize_run(
    *,
    run_id_str: str,
    started: StartedRunContext,
    prepared: PreparedRunContext,
    progress_state: dict[str, Any],
    run_wall_start: float,
) -> dict[str, Any]:
    return _dispatch_and_finalize_run_impl(
        run_id_str=run_id_str,
        started=started,
        prepared=prepared,
        progress_state=progress_state,
        run_wall_start=run_wall_start,
        estimate_total_iterations=_estimate_total_iterations,
        emit_progress_update=_emit_progress_update,
        build_telemetry_estimate=_build_telemetry_estimate,
        persist_latest_estimate=_persist_latest_estimate,
        insert_run_event=_append_run_event,
        dispatch_algorithm=dispatch_algorithm,
        pause_after_dispatch=_pause_after_dispatch_if_requested,
        normalize_result=normalize_result,
        apply_result_metadata=_apply_result_metadata,
        reconcile_reported_iterations=_reconcile_reported_iterations,
        uses_branch_matrix_elements=_uses_branch_matrix_elements,
        emit_fallback_completion_progress=_emit_fallback_completion_progress,
        session_factory=get_db_session,
        commit_transaction=commit_transaction,
    )


def _paused_run_result(
    *,
    run_id_str: str,
    expected_generation: int | None,
    algorithm: str,
    progress_state: dict[str, Any],
) -> dict[str, Any]:
    if expected_generation is not None:
        _finalize_cooperative_pause(
            run_id_str,
            execution_generation=expected_generation,
            algorithm=algorithm,
            payload={
                "stage": "cooperative_pause",
                "progress_state": progress_state,
            },
        )
    logger.info("Run %s reached cooperative pause checkpoint", run_id_str)
    return _stopped_run_result(
        algorithm,
        iterations=int(progress_state.get("monotonic_completed_iterations", 0)),
        status="PAUSED",
    )


def execute_run(run_id: UUID | str, *, execution_generation: int | None = None) -> dict[str, Any]:
    """Execute a queued run end-to-end.

    Routes the run through algorithm and backend selection, emits setup/progress
    events, and returns a normalized result payload compatible with callbacks.
    """
    run_id_str = str(run_id)
    logger.info("Starting execute_run for run %s", run_id_str)
    expected_generation = int(execution_generation) if execution_generation is not None else None

    progress_state: dict[str, Any] = {
        "count": 0,
        "start_time": None,
        "ema_cost": None,
        "phase_offset": 0,
        "last_raw_completed_iterations": None,
        "monotonic_completed_iterations": 0,
    }
    started, early_result = _start_run_context(
        run_id_str=run_id_str,
        expected_generation=expected_generation,
        progress_state=progress_state,
    )
    if early_result is not None or started is None:
        return early_result if early_result is not None else _stale_run_result()

    run_wall_start = _segment_started_monotonic(progress_state)
    if run_wall_start is None:
        logger.error("Run %s has no execution segment start", run_id_str)
        raise RuntimeError(f"Run {run_id_str} has no execution segment start")

    segment_status = "interrupted"
    termination_reason = "worker_exception"
    try:
        prepared, setup_result = _prepare_backend_and_hamiltonian(
            run_id_str=run_id_str,
            started=started,
            progress_state=progress_state,
            run_wall_start=run_wall_start,
        )
        if setup_result is not None or prepared is None:
            result = setup_result if setup_result is not None else _stale_run_result()
            segment_status = "paused" if result.get("status") == "PAUSED" else "cancelled"
            termination_reason = "control_request_during_setup"
            return result

        result = _dispatch_and_finalize_run(
            run_id_str=run_id_str,
            started=started,
            prepared=prepared,
            progress_state=progress_state,
            run_wall_start=run_wall_start,
        )
        segment_status = "completed"
        termination_reason = None
        return result

    except _RunCancelled:
        segment_status = "cancelled"
        termination_reason = "cancel_requested"
        logger.info("Run %s stopped after cancellation request", run_id_str)
        return _stopped_run_result(
            started.algorithm,
            iterations=int(progress_state.get("monotonic_completed_iterations", 0)),
        )

    except _RunPaused:
        segment_status = "paused"
        termination_reason = "pause_requested"
        return _paused_run_result(
            run_id_str=run_id_str,
            expected_generation=started.expected_generation,
            algorithm=started.algorithm,
            progress_state=progress_state,
        )

    except Exception:
        # Re-raise so RQ routes to on_job_failure, which owns error events and status update
        logger.exception("Run %s failed", run_id_str)
        raise
    finally:
        _finish_execution_segment(
            get_db_session,
            progress_state=progress_state,
            run_id=run_id_str,
            execution_generation=started.expected_generation,
            status=segment_status,
            termination_reason=termination_reason,
        )
