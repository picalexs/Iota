"""Contract tests for the Redis/RQ enqueue boundary."""

from __future__ import annotations

import os
import time
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest
from redis import Redis
from rq import Queue, SimpleWorker
from rq.exceptions import NoSuchJobError
from rq.job import Job


def _redis_url() -> str:
    value = os.environ.get("TEST_REDIS_URL", "").strip()
    if not value:
        pytest.skip("TEST_REDIS_URL is not configured")
    return value


def _callback_path(callback: object) -> str:
    """Normalize RQ callback representations across supported RQ versions."""
    if isinstance(callback, str):
        return callback
    return f"{callback.__module__}.{callback.__name__}"


def _redis_noop(value: str) -> dict[str, str]:
    """Return a deterministic result for real RQ dequeue tests."""
    return {"value": value}


def _wait_for_job_key_to_expire(redis_client: Redis, job_id: str) -> None:
    """Wait briefly for Redis to remove an RQ job whose result TTL elapsed."""
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        if not redis_client.exists(f"rq:job:{job_id}"):
            return
        time.sleep(0.05)
    pytest.fail(f"RQ job {job_id} did not expire within the test timeout")


@pytest.mark.redis
def test_enqueue_run_persists_runtime_queue_and_callback_contract() -> None:
    from app.services.queue_service import enqueue_run

    redis_client = Redis.from_url(_redis_url())
    queue_name = f"maintainability-contract-{uuid4().hex}"
    run_id = uuid4()
    settings = SimpleNamespace(queue_name=queue_name, quantum_job_timeout_seconds=30)
    job_id: str | None = None
    try:
        assert redis_client.ping() is True
        with patch("app.services.queue_service.get_settings", return_value=settings):
            job_id = enqueue_run(run_id, redis_client, execution_generation=4)

        job = Job.fetch(job_id, connection=redis_client)
        assert Queue(queue_name, connection=redis_client).count == 1
        assert job.timeout == 30
        assert job.func_name == "worker.tasks.enqueueable_execute_run"
        assert job.args == ({"run_id": str(run_id), "execution_generation": 4},)
        assert _callback_path(job.success_callback) == "worker.jobs.callbacks.on_job_success"
        assert _callback_path(job.failure_callback) == "worker.jobs.callbacks.on_job_failure"
    finally:
        if job_id is not None:
            Job.fetch(job_id, connection=redis_client).delete()
        redis_client.close()


@pytest.mark.redis
def test_cancel_queued_job_handles_waiting_and_missing_jobs() -> None:
    from app.services.queue_service import cancel_queued_job, enqueue_run

    redis_client = Redis.from_url(_redis_url())
    queue_name = f"maintainability-cancel-{uuid4().hex}"
    settings = SimpleNamespace(queue_name=queue_name, quantum_job_timeout_seconds=30)
    job_id: str | None = None
    try:
        assert redis_client.ping() is True
        with patch("app.services.queue_service.get_settings", return_value=settings):
            job_id = enqueue_run(uuid4(), redis_client, execution_generation=1)

        cancel_queued_job(job_id, redis_client)
        assert Job.fetch(job_id, connection=redis_client).get_status() == "canceled"

        cancel_queued_job(f"missing-{uuid4().hex}", redis_client)
    finally:
        if job_id is not None:
            try:
                Job.fetch(job_id, connection=redis_client).delete()
            except NoSuchJobError:
                pass
        redis_client.close()


@pytest.mark.redis
def test_simple_worker_dequeues_and_finishes_deterministic_job() -> None:
    """Prove the configured Redis queue can be consumed without solver state."""
    redis_client = Redis.from_url(_redis_url())
    queue_name = f"maintainability-dequeue-{uuid4().hex}"
    job_id: str | None = None
    try:
        assert redis_client.ping() is True
        job = Queue(queue_name, connection=redis_client).enqueue(_redis_noop, "ok")
        job_id = job.id

        assert SimpleWorker([queue_name], connection=redis_client).work(burst=True)

        job.refresh()
        assert job.get_status() == "finished"
        assert job.return_value() == {"value": "ok"}
    finally:
        if job_id is not None:
            try:
                Job.fetch(job_id, connection=redis_client).delete()
            except NoSuchJobError:
                pass
        redis_client.close()


@pytest.mark.redis
def test_expired_job_is_treated_as_missing_by_cancellation(caplog) -> None:
    """Prove a completed job removed by Redis TTL follows the safe missing path."""
    from app.services.queue_service import cancel_queued_job

    redis_client = Redis.from_url(_redis_url())
    queue_name = f"maintainability-expiry-{uuid4().hex}"
    job_id: str | None = None
    try:
        assert redis_client.ping() is True
        job = Queue(queue_name, connection=redis_client).enqueue(
            _redis_noop,
            "expires",
            result_ttl=1,
        )
        job_id = job.id
        assert SimpleWorker([queue_name], connection=redis_client).work(burst=True)
        _wait_for_job_key_to_expire(redis_client, job_id)

        cancel_queued_job(job_id, redis_client)

        assert "already started or expired" in caplog.text
    finally:
        if job_id is not None:
            redis_client.delete(f"rq:job:{job_id}")
        redis_client.close()


@pytest.mark.redis
def test_terminal_job_cancellation_keeps_database_authority(caplog) -> None:
    """Prove an RQ terminal-state failure does not override DB cancellation."""
    from app.services.queue_service import cancel_queued_job

    redis_client = Redis.from_url(_redis_url())
    queue_name = f"maintainability-terminal-{uuid4().hex}"
    job_id: str | None = None
    try:
        assert redis_client.ping() is True
        job = Queue(queue_name, connection=redis_client).enqueue(_redis_noop, "terminal")
        job_id = job.id
        assert SimpleWorker([queue_name], connection=redis_client).work(burst=True)

        cancel_queued_job(job_id, redis_client)
        cancel_queued_job(job_id, redis_client)

        assert "DB cancellation remains authoritative" in caplog.text
    finally:
        if job_id is not None:
            try:
                Job.fetch(job_id, connection=redis_client).delete()
            except NoSuchJobError:
                pass
        redis_client.close()
