"""Tests for restart recovery of worker execution segments."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from worker.jobs.recovery import recover_interrupted_runs


def _session_factory(session: MagicMock):
    context = MagicMock()
    context.__enter__.return_value = session
    context.__exit__.return_value = False
    return lambda: context


def _segment(*, status: str = "RUNNING", job_id: str | None = None) -> dict:
    return {
        "id": "segment-1",
        "run_id": "run-1",
        "execution_generation": 2,
        "rq_job_id": job_id,
        "last_heartbeat_at": datetime(2026, 1, 1, tzinfo=UTC),
        "last_heartbeat_duration_seconds": 4.25,
        "run_status": status,
    }


def test_recover_interrupted_running_run_uses_last_heartbeat_duration() -> None:
    session = MagicMock()
    repository = MagicMock()
    repository.list_open_execution_segments.return_value = [_segment()]
    repository.get_closed_execution_duration.return_value = 0.0
    repository.recover_execution_segment.return_value = 1
    repository.recover_interrupted_run.return_value = 1
    recovered_at = datetime(2026, 1, 2, tzinfo=UTC)

    with patch("worker.jobs.recovery.SqlRunRepository", return_value=repository):
        recovered = recover_interrupted_runs(
            worker_ttl_seconds=60,
            session_factory=_session_factory(session),
            now=recovered_at,
        )

    assert recovered == 1
    repository.recover_execution_segment.assert_called_once_with(
        "segment-1",
        duration_seconds=4.25,
        worker_finished_at=recovered_at,
        termination_reason="worker_stack_restart",
    )
    repository.recover_interrupted_run.assert_called_once_with(
        "run-1",
        2,
        status="FAILED",
        runtime_metadata={
            "runtime_seconds": 4.25,
            "runtime_basis": "worker_execution_segment_monotonic_heartbeat",
            "runtime_complete": False,
            "interruption_reason": "worker_stack_restart",
            "interrupted_at": recovered_at.isoformat(),
        },
    )
    repository.append_event.assert_called_once()
    session.commit.assert_called_once()


def test_recover_pausing_run_as_paused() -> None:
    session = MagicMock()
    repository = MagicMock()
    repository.list_open_execution_segments.return_value = [_segment(status="PAUSING")]
    repository.get_closed_execution_duration.return_value = 0.0
    repository.recover_execution_segment.return_value = 1
    repository.recover_interrupted_run.return_value = 1
    recovered_at = datetime(2026, 1, 2, tzinfo=UTC)

    with patch("worker.jobs.recovery.SqlRunRepository", return_value=repository):
        recovered = recover_interrupted_runs(
            worker_ttl_seconds=60,
            session_factory=_session_factory(session),
            now=recovered_at,
        )

    assert recovered == 1
    assert repository.recover_interrupted_run.call_args.kwargs["status"] == "PAUSED"
    assert (
        repository.recover_execution_segment.call_args.kwargs["termination_reason"]
        == "pause_request_interrupted_by_stack_restart"
    )


def test_recover_cancelled_run_without_reopening_it() -> None:
    session = MagicMock()
    repository = MagicMock()
    repository.list_open_execution_segments.return_value = [_segment(status="CANCELLED")]
    repository.get_closed_execution_duration.return_value = 0.0
    repository.recover_execution_segment.return_value = 1
    repository.recover_interrupted_run.return_value = 1
    recovered_at = datetime(2026, 1, 2, tzinfo=UTC)

    with patch("worker.jobs.recovery.SqlRunRepository", return_value=repository):
        recovered = recover_interrupted_runs(
            worker_ttl_seconds=60,
            session_factory=_session_factory(session),
            now=recovered_at,
        )

    assert recovered == 1
    assert repository.recover_interrupted_run.call_args.kwargs["status"] == "CANCELLED"


def test_recovery_keeps_a_segment_with_a_fresh_rq_heartbeat_open() -> None:
    session = MagicMock()
    repository = MagicMock()
    repository.list_open_execution_segments.return_value = [_segment(job_id="rq-job-1")]
    repository.get_closed_execution_duration.return_value = 0.0
    now = datetime(2026, 1, 2, tzinfo=UTC)
    live_job = MagicMock()
    live_job.get_status.return_value = "started"
    live_job.last_heartbeat = now - timedelta(seconds=1)

    with (
        patch("worker.jobs.recovery.SqlRunRepository", return_value=repository),
        patch("worker.jobs.recovery.Job.fetch", return_value=live_job),
    ):
        recovered = recover_interrupted_runs(
            redis_client=MagicMock(),
            worker_ttl_seconds=60,
            session_factory=_session_factory(session),
            now=now,
        )

    assert recovered == 0
    repository.recover_execution_segment.assert_not_called()
    repository.recover_interrupted_run.assert_not_called()
    session.commit.assert_called_once()
