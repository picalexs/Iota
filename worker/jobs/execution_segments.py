"""Worker execution-segment timing and heartbeat helpers."""

from __future__ import annotations

import logging
import math
import time
from datetime import UTC, datetime
from typing import Any

from worker.persistence.run_repository import SqlRunRepository

logger = logging.getLogger(__name__)

SEGMENT_ID_KEY = "_execution_segment_id"
SEGMENT_PRIOR_DURATION_KEY = "_execution_segment_prior_duration_seconds"
SEGMENT_STARTED_KEY = "_execution_segment_started_monotonic"


def current_rq_job_id() -> str | None:
    """Return the current RQ job identifier when called inside an RQ job."""
    try:
        from rq import get_current_job
    except ImportError:
        return None

    job = get_current_job()
    job_id = getattr(job, "id", None)
    return str(job_id) if job_id else None


def start_execution_segment(
    session: Any,
    *,
    run_id: str,
    execution_generation: int,
    worker_started_at: datetime,
    progress_state: dict[str, Any],
) -> str:
    """Create a segment and start its monotonic worker clock."""
    repository = SqlRunRepository(session)
    segment_id = repository.start_execution_segment(
        run_id,
        execution_generation,
        worker_started_at,
        rq_job_id=current_rq_job_id(),
    )
    progress_state[SEGMENT_PRIOR_DURATION_KEY] = repository.get_closed_execution_duration(run_id)
    progress_state[SEGMENT_ID_KEY] = segment_id
    progress_state[SEGMENT_STARTED_KEY] = time.monotonic()
    return segment_id


def segment_duration_seconds(progress_state: dict[str, Any]) -> float | None:
    """Return elapsed monotonic seconds for the current segment."""
    started = segment_started_monotonic(progress_state)
    if started is None:
        return None
    return max(time.monotonic() - started, 0.0)


def segment_started_monotonic(progress_state: dict[str, Any]) -> float | None:
    """Return the monotonic start reading for the current segment."""
    started = progress_state.get(SEGMENT_STARTED_KEY)
    if not isinstance(started, (int, float)) or not math.isfinite(float(started)):
        return None
    return float(started)


def heartbeat_execution_segment(
    session: Any,
    *,
    progress_state: dict[str, Any],
    run_id: str | None = None,
    execution_generation: int | None = None,
    heartbeat_at: datetime | None = None,
) -> None:
    """Persist the latest monotonic duration without ending the segment."""
    segment_id = progress_state.get(SEGMENT_ID_KEY)
    duration = segment_duration_seconds(progress_state)
    if not isinstance(segment_id, str) or duration is None:
        return

    repository = SqlRunRepository(session)
    rowcount = repository.heartbeat_execution_segment(
        segment_id,
        duration,
        heartbeat_at or datetime.now(UTC),
    )
    if rowcount == 0:
        logger.info("Execution segment %s is no longer open", segment_id)
        return
    if run_id is not None and execution_generation is not None:
        repository.update_execution_runtime(
            run_id,
            execution_generation,
            runtime_seconds=execution_duration_seconds(progress_state),
            runtime_complete=False,
        )


def execution_duration_seconds(progress_state: dict[str, Any]) -> float:
    """Return cumulative closed-plus-current execution seconds."""
    prior = progress_state.get(SEGMENT_PRIOR_DURATION_KEY, 0.0)
    prior_seconds = float(prior) if isinstance(prior, (int, float)) else 0.0
    return max(prior_seconds, 0.0) + (segment_duration_seconds(progress_state) or 0.0)


def finish_execution_segment(
    session_factory: Any,
    *,
    progress_state: dict[str, Any],
    run_id: str | None = None,
    execution_generation: int | None = None,
    status: str,
    termination_reason: str | None = None,
    duration_seconds: float | None = None,
) -> None:
    """Close the current segment in a short independent transaction."""
    segment_id = progress_state.get(SEGMENT_ID_KEY)
    measured_duration = segment_duration_seconds(progress_state)
    if not isinstance(segment_id, str) or measured_duration is None:
        return

    if isinstance(duration_seconds, (int, float)) and math.isfinite(float(duration_seconds)):
        measured_duration = max(float(duration_seconds), 0.0)

    with session_factory() as session:
        repository = SqlRunRepository(session)
        rowcount = repository.finish_execution_segment(
            segment_id,
            status=status,
            duration_seconds=measured_duration,
            worker_finished_at=datetime.now(UTC),
            termination_reason=termination_reason,
        )
        if rowcount == 0:
            logger.info("Execution segment %s was already closed", segment_id)
            return
        if run_id is not None and execution_generation is not None:
            repository.update_execution_runtime(
                run_id,
                execution_generation,
                runtime_seconds=(
                    max(
                        float(progress_state.get(SEGMENT_PRIOR_DURATION_KEY, 0.0)),
                        0.0,
                    )
                    + measured_duration
                ),
                runtime_complete=status != "interrupted",
            )


__all__ = [
    "SEGMENT_ID_KEY",
    "SEGMENT_PRIOR_DURATION_KEY",
    "SEGMENT_STARTED_KEY",
    "current_rq_job_id",
    "execution_duration_seconds",
    "finish_execution_segment",
    "heartbeat_execution_segment",
    "segment_started_monotonic",
    "segment_duration_seconds",
    "start_execution_segment",
]
