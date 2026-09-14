"""IBM Runtime status, timeout, and timing normalization helpers."""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, NamedTuple

from worker.contracts import RunRepositoryContract

from .run_execution.contracts import RepositoryFactory, SessionFactory

_IBM_FINAL_STATUSES = {"DONE", "ERROR", "CANCELLED"}
_IBM_STATUS_POLL_INTERVAL_SECONDS = 15.0
_UNKNOWN_JOB_ID = "<unknown>"
logger = logging.getLogger(__name__)


class IBMObservationMetadata(NamedTuple):
    """Normalized metadata attached to an observed primitive job."""

    job_id: str | None
    backend_name: str | None
    pub_count: int | None
    shots: int | None


IBMObservationRecorder = Callable[
    [str, dict[str, Any], IBMObservationMetadata, Any],
    None,
]
IBMJobCancelRequester = Callable[[Any, str, str | None], None]


def request_ibm_job_cancel(job: Any, run_id: str, job_id: str | None) -> None:
    """Best-effort cancellation for an in-flight IBM Runtime job."""
    cancel = getattr(job, "cancel", None)
    if not callable(cancel):
        logger.warning(
            "Run %s cancellation requested but IBM job %s does not expose cancel()",
            run_id,
            job_id or _UNKNOWN_JOB_ID,
        )
        return
    try:
        cancel()
    except Exception:
        logger.warning(
            "Failed to request cancellation for IBM job %s on run %s",
            job_id or _UNKNOWN_JOB_ID,
            run_id,
            exc_info=True,
        )
    else:
        logger.info(
            "Requested cancellation for IBM job %s on run %s",
            job_id or _UNKNOWN_JOB_ID,
            run_id,
        )


def call_noarg(value: Any) -> Any:
    """Call a no-argument Runtime attribute when it is callable."""
    if callable(value):
        try:
            return value()
        except Exception:
            return None
    return value


def extract_ibm_status(job: Any) -> str | None:
    """Best-effort Runtime job status extraction across client versions."""
    status = call_noarg(getattr(job, "status", None))
    if status is None:
        return None
    for attr in ("name", "value"):
        candidate = getattr(status, attr, None)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip().upper()
    status_text = str(status).strip()
    return status_text.upper() if status_text else None


def extract_queue_position(job: Any) -> int | None:
    """Best-effort queue-position extraction across Runtime client versions."""
    queue_info = call_noarg(getattr(job, "queue_info", None))
    if queue_info is None:
        return None
    if isinstance(queue_info, dict):
        for key in ("position", "queue_position"):
            value = queue_info.get(key)
            if isinstance(value, int):
                return value
        return None
    for attr in ("position", "queue_position"):
        value = getattr(queue_info, attr, None)
        if isinstance(value, int):
            return value
    return None


def number_or_none(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    parsed = float(value)
    return parsed if math.isfinite(parsed) else None


def parse_ibm_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(UTC)
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def iso_or_none(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def duration_seconds(start: datetime | None, end: datetime | None) -> float | None:
    if start is None or end is None:
        return None
    seconds = (end - start).total_seconds()
    return seconds if seconds >= 0 else None


def pick_timestamp(timestamps: dict[str, Any], *keys: str) -> datetime | None:
    lowered = {key.lower(): value for key, value in timestamps.items()}
    for key in keys:
        parsed = parse_ibm_datetime(lowered.get(key.lower()))
        if parsed is not None:
            return parsed
    return None


def extract_ibm_usage_seconds(metrics: dict[str, Any], job: Any) -> float | None:
    usage = metrics.get("usage")
    if isinstance(usage, dict):
        for key in ("quantum_seconds", "seconds", "usage_seconds"):
            value = number_or_none(usage.get(key))
            if value is not None:
                return value
    usage_method = getattr(job, "usage", None)
    if callable(usage_method):
        try:
            value = number_or_none(usage_method())
        except Exception:
            return None
        if value is not None:
            return value
    return None


def extract_ibm_metrics(job: Any) -> dict[str, Any]:
    metrics_method = getattr(job, "metrics", None)
    if not callable(metrics_method):
        return {}
    try:
        metrics = metrics_method()
    except Exception:
        return {}
    return metrics if isinstance(metrics, dict) else {}


def normalize_ibm_status(status: str | None) -> str | None:
    if status is None:
        return None
    normalized = status.rsplit(".", maxsplit=1)[-1].upper()
    return normalized if normalized else None


def is_ibm_final_status(status: str | None) -> bool:
    normalized = normalize_ibm_status(status)
    return normalized in _IBM_FINAL_STATUSES if normalized is not None else False


def build_ibm_timing(metrics: dict[str, Any], job: Any) -> dict[str, Any] | None:
    timestamps = metrics.get("timestamps")
    timestamps = timestamps if isinstance(timestamps, dict) else {}

    created_at = pick_timestamp(
        timestamps,
        "created",
        "created_at",
        "creation_date",
        "submitted",
        "submitted_at",
    )
    running_at = pick_timestamp(
        timestamps,
        "running",
        "running_at",
        "started",
        "started_at",
        "in_progress",
        "in_progress_at",
    )
    finished_at = pick_timestamp(
        timestamps,
        "finished",
        "finished_at",
        "completed",
        "completed_at",
        "ended",
        "ended_at",
    )

    usage_seconds = extract_ibm_usage_seconds(metrics, job)
    pending_seconds = duration_seconds(created_at, running_at)
    total_seconds = duration_seconds(created_at, finished_at)
    run_seconds = duration_seconds(running_at, finished_at)
    if usage_seconds is None:
        usage_seconds = run_seconds

    timing = {
        "created_at": iso_or_none(created_at),
        "running_at": iso_or_none(running_at),
        "finished_at": iso_or_none(finished_at),
        "pending_seconds": pending_seconds,
        "usage_seconds": usage_seconds,
        "total_seconds": total_seconds,
    }
    useful = any(value is not None for value in timing.values())
    return timing if useful else None


def result_timeout(args: tuple[Any, ...], kwargs: dict[str, Any]) -> float | None:
    if "timeout" in kwargs:
        raw = kwargs.get("timeout")
    elif args:
        raw = args[0]
    else:
        raw = None
    return number_or_none(raw)


def replace_result_timeout(
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    timeout: float,
) -> tuple[tuple[Any, ...], dict[str, Any]]:
    next_kwargs = dict(kwargs)
    if "timeout" in next_kwargs:
        next_kwargs["timeout"] = timeout
        return args, next_kwargs
    if args:
        return (timeout, *args[1:]), next_kwargs
    return args, {**next_kwargs, "timeout": timeout}


def coerce_int(value: object) -> int | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)
    return None


def coerce_str(value: object) -> str | None:
    return str(value) if value is not None else None


def extract_observation_metadata(metadata: dict[str, Any]) -> IBMObservationMetadata:
    return IBMObservationMetadata(
        job_id=coerce_str(metadata.get("job_id")),
        backend_name=coerce_str(metadata.get("backend")),
        pub_count=coerce_int(metadata.get("pub_count")),
        shots=coerce_int(metadata.get("shots")),
    )


def runtime_metadata_for_snapshot(
    observation: IBMObservationMetadata,
    *,
    ibm_status: str | None,
    queue_position: int | None,
    timing: dict[str, Any] | None,
) -> dict[str, Any]:
    runtime_metadata: dict[str, Any] = {
        "ibm_backend": observation.backend_name,
        "ibm_job_id": observation.job_id,
        "ibm_status": ibm_status,
        "ibm_queue_position": queue_position,
        "ibm_pub_count": observation.pub_count,
        "ibm_shots": observation.shots,
    }
    if timing is not None:
        runtime_metadata["ibm_timing"] = timing
    return runtime_metadata


def event_payload_for_snapshot(
    observation: IBMObservationMetadata,
    *,
    ibm_status: str | None,
    queue_position: int | None,
    elapsed_seconds: float,
    phase: str,
    timing: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "ibm_job_id": observation.job_id,
        "backend": observation.backend_name,
        "ibm_status": ibm_status,
        "queued_count": queue_position,
        "queue_position": queue_position,
        "elapsed_seconds": elapsed_seconds,
        "phase": phase,
        "pub_count": observation.pub_count,
        "shots": observation.shots,
        "ibm_timing": timing,
    }


def next_ibm_run_status(current_status: str | None, ibm_status: str | None) -> str:
    if ibm_status == "CANCELLED" or current_status == "CANCELLED":
        return "CANCELLED"
    if current_status == "PAUSING":
        return "PAUSING"
    return "SUBMITTED_TO_IBM"


def primitive_type_from_snapshot(snapshot: dict[str, Any]) -> str | None:
    return coerce_str(
        snapshot.get("primitive_type")
        or snapshot.get("primitive_family")
        or snapshot.get("backend_target")
    )


def emit_ibm_runtime_snapshot_events(
    repository: RunRepositoryContract,
    *,
    run_id: str,
    current_status: str | None,
    next_run_status: str,
    phase: str,
    job_id: str | None,
    event_payload: dict[str, Any],
) -> None:
    """Append lifecycle and Runtime events for one observed job snapshot."""
    if next_run_status == "CANCELLED":
        if current_status != "CANCELLED":
            repository.append_event(
                run_id,
                "status_changed",
                {
                    "status": "CANCELLED",
                    "ibm_job_id": job_id,
                    "reason": "ibm_job_cancelled",
                },
            )
    elif current_status not in {"SUBMITTED_TO_IBM", "PAUSING"}:
        repository.append_event(
            run_id,
            "status_changed",
            {"status": "SUBMITTED_TO_IBM", "ibm_job_id": job_id},
        )

    if phase == "submitted":
        repository.append_event(run_id, "ibm_job_submitted", event_payload)

    if (
        event_payload.get("ibm_status") is not None
        or event_payload.get("queue_position") is not None
        or event_payload.get("ibm_timing") is not None
        or phase == "poll"
    ):
        repository.append_event(run_id, "ibm_status_poll", event_payload)


def persist_ibm_runtime_snapshot(
    *,
    run_id: str,
    run_wall_start: float,
    phase: str,
    snapshot: dict[str, Any],
    observation: IBMObservationMetadata,
    job: Any,
    session_factory: SessionFactory,
    repository_factory: RepositoryFactory,
    request_job_cancel: IBMJobCancelRequester,
    cancellation_error_factory: Callable[[str], RuntimeError],
) -> None:
    """Persist one Runtime snapshot and enforce local cancellation authority."""
    ibm_status = normalize_ibm_status(coerce_str(snapshot.get("ibm_status")))
    queue_position = coerce_int(snapshot.get("queue_position"))
    timing = snapshot.get("ibm_timing")
    timing = timing if isinstance(timing, dict) else None
    elapsed_seconds = max(0.0, time.monotonic() - run_wall_start)
    now = datetime.now(UTC)
    runtime_metadata = runtime_metadata_for_snapshot(
        observation,
        ibm_status=ibm_status,
        queue_position=queue_position,
        timing=timing,
    )
    event_payload = event_payload_for_snapshot(
        observation,
        ibm_status=ibm_status,
        queue_position=queue_position,
        elapsed_seconds=elapsed_seconds,
        phase=phase,
        timing=timing,
    )

    local_cancel_requested = False
    with session_factory() as session:
        repository = repository_factory(session)
        control_snapshot = repository.get_run_control_snapshot(run_id, for_update=True)
        current_status, current_generation = control_snapshot or (None, 1)
        local_cancel_requested = current_status == "CANCELLED"
        next_run_status = next_ibm_run_status(current_status, ibm_status)

        if observation.job_id is not None:
            completed_at = now if phase == "complete" or is_ibm_final_status(ibm_status) else None
            submitted_at = now if phase == "submitted" else None
            job_metadata = {
                **runtime_metadata,
                "phase": phase,
                "backend_target": snapshot.get("backend_target"),
                "selection_policy": snapshot.get("selection_policy"),
            }
            repository.record_ibm_job(
                run_id,
                current_generation,
                observation.job_id,
                primitive_type=primitive_type_from_snapshot(snapshot),
                backend_name=observation.backend_name,
                status=ibm_status,
                submitted_at=submitted_at,
                completed_at=completed_at,
                metadata=job_metadata,
                now=now,
            )
        repository.update_ibm_runtime_snapshot(
            run_id,
            status=next_run_status,
            ibm_job_id=observation.job_id,
            runtime_metadata=runtime_metadata,
            now=now,
        )
        emit_ibm_runtime_snapshot_events(
            repository,
            run_id=run_id,
            current_status=current_status,
            next_run_status=next_run_status,
            phase=phase,
            job_id=observation.job_id,
            event_payload=event_payload,
        )
        session.commit()

    if local_cancel_requested:
        if not is_ibm_final_status(ibm_status):
            request_job_cancel(job, run_id, observation.job_id)
        raise cancellation_error_factory(run_id)


class ObservedIBMJob:
    """Proxy an IBM Runtime job while recording status around ``result``."""

    def __init__(
        self,
        job: Any,
        *,
        record_snapshot: IBMObservationRecorder,
        metadata: dict[str, Any],
        observation: IBMObservationMetadata,
        cancellation_error_factory: Callable[[str], RuntimeError],
    ) -> None:
        self._job = job
        self._record_snapshot = record_snapshot
        self._metadata = metadata
        self._observation = observation
        self._cancellation_error_factory = cancellation_error_factory

    def __getattr__(self, name: str) -> Any:
        return getattr(self._job, name)

    def result(self, *args: Any, **kwargs: Any) -> Any:
        timeout = result_timeout(args, kwargs)
        wait_start = time.monotonic()

        while True:
            status = extract_ibm_status(self._job)
            queue_position = extract_queue_position(self._job)
            self._record_snapshot(
                "poll",
                {
                    **self._metadata,
                    "ibm_status": status,
                    "queue_position": queue_position,
                },
                self._observation,
                self._job,
            )
            if status is None or is_ibm_final_status(status):
                break

            if timeout is not None:
                remaining = timeout - (time.monotonic() - wait_start)
                if remaining <= 0:
                    break
                sleep_seconds = min(_IBM_STATUS_POLL_INTERVAL_SECONDS, remaining)
            else:
                sleep_seconds = _IBM_STATUS_POLL_INTERVAL_SECONDS
            time.sleep(sleep_seconds)

        if normalize_ibm_status(status) == "CANCELLED":
            raise self._cancellation_error_factory(
                str(self._metadata.get("job_id") or "ibm_job_cancelled")
            )

        result_args = args
        result_kwargs = kwargs
        if timeout is not None:
            remaining = max(0.0, timeout - (time.monotonic() - wait_start))
            result_args, result_kwargs = replace_result_timeout(args, kwargs, remaining)

        try:
            return self._job.result(*result_args, **result_kwargs)
        finally:
            metrics = extract_ibm_metrics(self._job)
            timing = build_ibm_timing(metrics, self._job)
            self._record_snapshot(
                "complete",
                {
                    **self._metadata,
                    "ibm_status": extract_ibm_status(self._job),
                    "queue_position": extract_queue_position(self._job),
                    "ibm_timing": timing,
                },
                self._observation,
                self._job,
            )


def build_ibm_primitive_job_observer(
    *,
    record_snapshot: IBMObservationRecorder,
    cancellation_error_factory: Callable[[str], RuntimeError],
) -> Callable[[Any, dict[str, Any]], Any | None]:
    """Build the IBM Runtime observer while leaving persistence injectable."""

    def observe(job: Any, metadata: dict[str, Any]) -> Any | None:
        observation = extract_observation_metadata(metadata)

        initial_metadata = {
            "job_id": observation.job_id,
            "backend": observation.backend_name,
            "pub_count": observation.pub_count,
            "shots": observation.shots,
        }
        record_snapshot(
            "submitted",
            {
                **initial_metadata,
                "ibm_status": extract_ibm_status(job),
                "queue_position": extract_queue_position(job),
            },
            observation,
            job,
        )

        return ObservedIBMJob(
            job,
            record_snapshot=record_snapshot,
            metadata=initial_metadata,
            observation=observation,
            cancellation_error_factory=cancellation_error_factory,
        )

    return observe
