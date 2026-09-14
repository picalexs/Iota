"""Tests for worker configuration ownership."""

from worker.config import WorkerSettings


def test_worker_queue_name_defaults_to_quantum():
    settings = WorkerSettings(
        _env_file=None,
        database_url="postgresql://localhost/test",
        redis_url="redis://localhost:6379/0",
    )

    assert settings.queue_name == "quantum"


def test_worker_queue_name_can_be_configured():
    settings = WorkerSettings(
        _env_file=None,
        database_url="postgresql://localhost/test",
        redis_url="redis://localhost:6379/0",
        queue_name="custom-queue",
    )

    assert settings.queue_name == "custom-queue"
