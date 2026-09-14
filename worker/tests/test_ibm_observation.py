"""Unit tests for IBM Runtime observation normalization."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from worker.jobs.ibm_observation import (
    build_ibm_timing,
    extract_ibm_status,
    extract_observation_metadata,
    extract_queue_position,
    is_ibm_final_status,
    normalize_ibm_status,
    replace_result_timeout,
    request_ibm_job_cancel,
    result_timeout,
)


def test_extract_runtime_status_and_queue_position_across_client_shapes() -> None:
    class RuntimeStatus:
        name = "running"

    assert extract_ibm_status(SimpleNamespace(status=lambda: RuntimeStatus())) == "RUNNING"
    assert extract_ibm_status(SimpleNamespace(status=lambda: "JobStatus.DONE")) == "JOBSTATUS.DONE"
    assert extract_queue_position(SimpleNamespace(queue_info=lambda: {"position": 4})) == 4
    assert (
        extract_queue_position(
            SimpleNamespace(queue_info=lambda: SimpleNamespace(queue_position=7))
        )
        == 7
    )


def test_normalize_ibm_status_accepts_qualified_and_final_values() -> None:
    assert normalize_ibm_status("JobStatus.DONE") == "DONE"
    assert normalize_ibm_status("running") == "RUNNING"
    assert is_ibm_final_status("JobStatus.CANCELLED") is True
    assert is_ibm_final_status("QUEUED") is False


def test_build_ibm_timing_derives_pending_and_usage_durations() -> None:
    timing = build_ibm_timing(
        {
            "timestamps": {
                "created": "2026-09-04T12:00:00Z",
                "running": "2026-09-04T12:00:05Z",
                "finished": "2026-09-04T12:00:20Z",
            }
        },
        object(),
    )

    assert timing == {
        "created_at": "2026-09-04T12:00:00+00:00",
        "running_at": "2026-09-04T12:00:05+00:00",
        "finished_at": "2026-09-04T12:00:20+00:00",
        "pending_seconds": 5.0,
        "usage_seconds": 15.0,
        "total_seconds": 20.0,
    }


def test_observation_metadata_and_result_timeout_are_normalized() -> None:
    observation = extract_observation_metadata(
        {"job_id": 123, "backend": "ibm_brisbane", "pub_count": 2.0, "shots": True}
    )
    assert observation.job_id == "123"
    assert observation.backend_name == "ibm_brisbane"
    assert observation.pub_count == 2
    assert observation.shots is None

    assert result_timeout((4.5,), {}) == 4.5
    assert result_timeout((), {"timeout": 3}) == 3.0
    assert replace_result_timeout((1,), {"mode": "sync"}, 2.5) == (
        (2.5,),
        {"mode": "sync"},
    )
    assert replace_result_timeout((), {"timeout": 1}, 2.5) == ((), {"timeout": 2.5})


def test_ibm_job_cancel_request_is_best_effort() -> None:
    job = MagicMock()

    request_ibm_job_cancel(job, "run-123", "job-456")

    job.cancel.assert_called_once_with()


def test_ibm_job_cancel_request_ignores_client_cancellation_errors() -> None:
    job = MagicMock()
    job.cancel.side_effect = RuntimeError("remote unavailable")

    request_ibm_job_cancel(job, "run-123", "job-456")

    job.cancel.assert_called_once_with()


def test_ibm_job_cancel_request_accepts_jobs_without_cancel() -> None:
    request_ibm_job_cancel(SimpleNamespace(), "run-123", None)
