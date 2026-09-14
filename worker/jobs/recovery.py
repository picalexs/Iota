"""Recovery of worker execution segments abandoned by a stack restart."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from rq.job import Job

from worker.db import get_db_session
from worker.persistence.run_repository import SqlRunRepository

logger = logging.getLogger(__name__)


def _as_utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    return value.astimezone(UTC) if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _job_is_live(redis_client: Any, job_id: str | None, *, stale_before: datetime) -> bool:
    """Return whether Redis still reports a worker job with a fresh lease."""
    if redis_client is None or not job_id:
        return False

    try:
        job = Job.fetch(job_id, connection=redis_client)
        status = str(job.get_status(refresh=True)).lower()
        if status in {"queued", "deferred", "scheduled"}:
            return True
        if status != "started":
            return False
        job_heartbeat = _as_utc(getattr(job, "last_heartbeat", None))
        return job_heartbeat is not None and job_heartbeat >= stale_before
    except Exception:
        logger.info("Could not find a live RQ job for execution segment %s", job_id)
        return False


def _segment_is_fresh_without_job(
    segment: dict[str, Any],
    *,
    stale_before: datetime,
) -> bool:
    if segment.get("rq_job_id") is not None:
        return False
    heartbeat = _as_utc(segment.get("last_heartbeat_at"))
    return heartbeat is not None and heartbeat >= stale_before


def _recovery_status(run_status: Any) -> tuple[str, str]:
    if run_status in {"PAUSING", "PAUSED"}:
        return "PAUSED", "pause_request_interrupted_by_stack_restart"
    if run_status == "CANCELLED":
        return "CANCELLED", "worker_stack_restart"
    return "FAILED", "worker_stack_restart"


def _recover_segment(
    repository: SqlRunRepository,
    segment: dict[str, Any],
    *,
    recovered_at: datetime,
) -> bool:
    duration = segment.get("last_heartbeat_duration_seconds")
    duration_seconds = float(duration) if isinstance(duration, (int, float)) else 0.0
    closed_duration = repository.get_closed_execution_duration(segment["run_id"])
    cumulative_duration = max(closed_duration + duration_seconds, 0.0)
    next_status, reason = _recovery_status(segment.get("run_status"))
    if repository.recover_execution_segment(
        segment["id"],
        duration_seconds=duration_seconds,
        worker_finished_at=recovered_at,
        termination_reason=reason,
    ) == 0:
        return False
    runtime_metadata = {
        "runtime_seconds": cumulative_duration,
        "runtime_basis": "worker_execution_segment_monotonic_heartbeat",
        "runtime_complete": False,
        "interruption_reason": reason,
        "interrupted_at": recovered_at.isoformat(),
    }
    if not repository.recover_interrupted_run(
        segment["run_id"],
        segment["execution_generation"],
        status=next_status,
        runtime_metadata=runtime_metadata,
    ):
        return False
    repository.append_event(
        segment["run_id"],
        "status_changed",
        {
            "status": next_status,
            "execution_generation": segment["execution_generation"],
            "reason": reason,
        },
    )
    return True


def recover_interrupted_runs(
    *,
    redis_client: Any = None,
    worker_ttl_seconds: int = 420,
    session_factory: Any = get_db_session,
    now: datetime | None = None,
) -> int:
    """Recover abandoned segments and return the number of recovered runs."""
    recovered = 0
    recovered_at = (now or datetime.now(UTC)).astimezone(UTC)
    stale_before = recovered_at - timedelta(seconds=max(worker_ttl_seconds, 1))

    with session_factory() as session:
        repository = SqlRunRepository(session)
        for segment in repository.list_open_execution_segments():
            if _job_is_live(
                redis_client,
                segment.get("rq_job_id"),
                stale_before=stale_before,
            ):
                continue
            if _segment_is_fresh_without_job(segment, stale_before=stale_before):
                continue
            if _recover_segment(repository, segment, recovered_at=recovered_at):
                recovered += 1

        session.commit()

    return recovered


__all__ = ["recover_interrupted_runs"]
