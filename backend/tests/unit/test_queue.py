"""
Unit tests for app.services.queue_service.check_redis_health.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import UUID

from app.services.queue_service import (
    QueueFailureReason,
    cancel_queued_job,
    check_redis_health,
    count_workers,
    enqueue_run,
    queue_name_for_run,
)
from redis.exceptions import ConnectionError as RedisConnectionError
from rq.exceptions import InvalidJobOperation, NoSuchJobError

# ---------------------------------------------------------------------------
# check_redis_health
# ---------------------------------------------------------------------------


def test_check_redis_health_with_valid_client_provided():
    """check_redis_health returns True when ping succeeds on provided client."""
    mock_client = MagicMock()
    mock_client.ping.return_value = True

    result = check_redis_health(client=mock_client)

    assert result is True
    mock_client.ping.assert_called_once()
    mock_client.close.assert_not_called()  # Must not close a provided client.


def test_check_redis_health_with_valid_client_ping_fails():
    """check_redis_health returns False when ping raises on provided client."""
    mock_client = MagicMock()
    mock_client.ping.side_effect = Exception("connection refused")

    result = check_redis_health(client=mock_client)

    assert result is False


def test_check_redis_health_classifies_unexpected_client_errors(caplog):
    """Unexpected health-check failures are visible as unknown, not healthy."""
    mock_client = MagicMock()
    mock_client.ping.side_effect = RuntimeError("unexpected failure")

    assert check_redis_health(client=mock_client) is False

    record = caplog.records[-1]
    assert record.queue_operation == "redis_health"
    assert record.queue_failure_reason == QueueFailureReason.UNKNOWN


def test_check_redis_health_with_no_client_creates_and_closes():
    """check_redis_health creates a temporary client, pings it, and closes it."""
    mock_temp = MagicMock()
    mock_temp.ping.return_value = True

    with patch("app.services.queue_service.get_settings") as mock_settings:
        mock_settings.return_value.redis_url = "redis://localhost:6379/0"
        with patch(
            "app.services.queue_service.Redis.from_url", return_value=mock_temp
        ) as mock_from_url:
            result = check_redis_health()

    assert result is True
    mock_from_url.assert_called_once_with("redis://localhost:6379/0")
    mock_temp.close.assert_called_once()


def test_check_redis_health_with_no_redis_url_configured():
    """check_redis_health returns False when REDIS_URL is empty."""
    with patch("app.services.queue_service.get_settings") as mock_settings:
        mock_settings.return_value.redis_url = ""
        result = check_redis_health()

    assert result is False


def test_check_redis_health_with_redis_unavailable():
    """check_redis_health returns False when the temporary client ping raises."""
    mock_temp = MagicMock()
    mock_temp.ping.side_effect = Exception("connection refused")

    with patch("app.services.queue_service.get_settings") as mock_settings:
        mock_settings.return_value.redis_url = "redis://localhost:6379/0"
        with patch("app.services.queue_service.Redis.from_url", return_value=mock_temp):
            result = check_redis_health()

    assert result is False


def test_check_redis_health_closes_created_client_even_on_exception():
    """check_redis_health closes the temporary client even when ping raises."""
    mock_temp = MagicMock()
    mock_temp.ping.side_effect = Exception("timeout")

    with patch("app.services.queue_service.get_settings") as mock_settings:
        mock_settings.return_value.redis_url = "redis://localhost:6379/0"
        with patch("app.services.queue_service.Redis.from_url", return_value=mock_temp):
            result = check_redis_health()

    assert result is False
    mock_temp.close.assert_called_once()


def test_enqueue_run_uses_configured_job_timeout():
    mock_queue = MagicMock()
    mock_job = MagicMock(id="job-1")
    mock_queue.enqueue.return_value = mock_job

    with patch("app.services.queue_service.get_settings") as mock_settings:
        mock_settings.return_value.quantum_job_timeout_seconds = 42
        mock_settings.return_value.queue_name = "custom-queue"
        with patch("rq.Queue", return_value=mock_queue):
            job_id = enqueue_run(UUID("aaaaaaaa-0000-0000-0000-000000000001"), MagicMock())

    assert job_id == "job-1"
    mock_queue.enqueue.assert_called_once()
    assert mock_queue.enqueue.call_args.kwargs["job_timeout"] == 42


def test_queue_name_for_run_routes_explicit_gpu_requests():
    settings = MagicMock(queue_name="quantum", gpu_queue_name="quantum-gpu")
    run = MagicMock(config_json={"backend_options": {"device": "GPU"}})

    assert queue_name_for_run(run, settings=settings) == "quantum-gpu"


def test_queue_name_for_run_keeps_cpu_default_queue():
    settings = MagicMock(queue_name="quantum", gpu_queue_name="quantum-gpu")
    run = MagicMock(config_json={"backend_options": {"device": "CPU"}})

    assert queue_name_for_run(run, settings=settings) == "quantum"


def test_enqueue_run_uses_configured_queue_name():
    mock_queue = MagicMock()
    mock_queue.enqueue.return_value = MagicMock(id="job-1")
    mock_redis = MagicMock()

    with patch("app.services.queue_service.get_settings") as mock_settings:
        mock_settings.return_value.quantum_job_timeout_seconds = 42
        mock_settings.return_value.queue_name = "custom-queue"
        with patch("rq.Queue", return_value=mock_queue) as queue_factory:
            enqueue_run(UUID("aaaaaaaa-0000-0000-0000-000000000001"), mock_redis)

    queue_factory.assert_called_once_with("custom-queue", connection=mock_redis)


def test_cancel_queued_job_cancels_waiting_job():
    mock_client = MagicMock()
    mock_job = MagicMock()
    mock_job.get_status.return_value = "queued"

    with patch("rq.job.Job.fetch", return_value=mock_job):
        cancel_queued_job("job-1", mock_client)

    mock_job.cancel.assert_called_once()


def test_cancel_queued_job_sends_stop_for_started_job():
    mock_client = MagicMock()
    mock_job = MagicMock()
    mock_job.get_status.return_value = "started"

    with (
        patch("rq.job.Job.fetch", return_value=mock_job),
        patch("rq.command.send_stop_job_command") as mock_stop,
    ):
        cancel_queued_job("job-1", mock_client)

    mock_stop.assert_called_once_with(mock_client, "job-1")
    mock_job.cancel.assert_not_called()


def test_cancel_queued_job_classifies_missing_job(caplog):
    with patch("rq.job.Job.fetch", side_effect=NoSuchJobError("missing")):
        cancel_queued_job("job-that-is-longer", MagicMock())

    record = caplog.records[-2]
    assert record.queue_operation == "cancel_queued_job"
    assert record.queue_failure_reason == QueueFailureReason.MISSING_JOB
    assert record.queue_job_id == "...is-longer"


def test_cancel_queued_job_classifies_redis_connection_failure(caplog):
    with patch("rq.job.Job.fetch", side_effect=RedisConnectionError("offline")):
        cancel_queued_job("job-1", MagicMock())

    record = caplog.records[-2]
    assert record.queue_operation == "cancel_queued_job"
    assert record.queue_failure_reason == QueueFailureReason.CONNECTION


def test_cancel_queued_job_classifies_invalid_job_state(caplog):
    with patch("rq.job.Job.fetch", side_effect=InvalidJobOperation("done")):
        cancel_queued_job("job-1", MagicMock())

    record = caplog.records[-2]
    assert record.queue_operation == "cancel_queued_job"
    assert record.queue_failure_reason == QueueFailureReason.INVALID_JOB_STATE


def test_count_workers_classifies_unexpected_errors(caplog):
    with patch("rq.Worker.all", side_effect=RuntimeError("unexpected")):
        assert count_workers(MagicMock()) == 0

    record = caplog.records[-2]
    assert record.queue_operation == "count_workers"
    assert record.queue_failure_reason == QueueFailureReason.UNKNOWN
