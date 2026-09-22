"""Tests for queue-wait and algorithm timing normalization."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from worker.jobs.execution_segments import _queue_wait_seconds
from worker.jobs.orchestrator import _algorithm_stage_timing


def test_queue_wait_uses_enqueue_metadata_and_never_goes_negative() -> None:
    worker_started = datetime(2026, 9, 22, 12, 0, 5, tzinfo=UTC)
    job = SimpleNamespace(
        meta={"qss_enqueued_at": "2026-09-22T12:00:00+00:00"}
    )

    assert _queue_wait_seconds(job, worker_started) == 5.0
    assert _queue_wait_seconds(
        job,
        worker_started - timedelta(seconds=10),
    ) == 0.0


def test_queue_wait_is_unavailable_without_valid_enqueue_metadata() -> None:
    worker_started = datetime(2026, 9, 22, 12, 0, 5, tzinfo=UTC)

    assert _queue_wait_seconds(SimpleNamespace(meta={}), worker_started) is None
    assert _queue_wait_seconds(
        SimpleNamespace(meta={"qss_enqueued_at": "invalid"}),
        worker_started,
    ) is None


def test_algorithm_stage_timing_normalizes_nested_qfd_and_sqd_fields() -> None:
    timing = _algorithm_stage_timing(
        {
            "algorithm_metrics": {
                "matrix_element_summary": {
                    "timing_breakdown": {
                        "matrix_element_estimation_seconds": 1.5,
                        "projected_solve_seconds": 0.5,
                    }
                },
                "sci_result_package": {
                    "timing_breakdown": {
                        "sampling_seconds": 2.0,
                        "selected_ci_seconds": 3.0,
                    }
                },
            }
        }
    )

    assert timing["state_generation_or_sampling_seconds"] == 1.5
    assert timing["projected_solve_seconds"] == 0.5
    assert timing["selected_ci_seconds"] == 3.0
