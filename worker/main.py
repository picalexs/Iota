"""Worker startup module."""

import json
import logging
import sys
import threading
import time
from contextlib import suppress
from datetime import UTC, datetime

import redis as redis_lib
from redis.exceptions import RedisError
from redis.exceptions import TimeoutError as RedisTimeoutError
from rq import Queue, Worker

from worker.config import get_settings
from worker.db import dispose_worker_db_engine
from worker.jobs.recovery import recover_interrupted_runs


class _JsonFormatter(logging.Formatter):
    """Emit one JSON object per log record, matching backend logging."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in ("run_id", "job_id", "algorithm", "event"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


logger = logging.getLogger(__name__)

_QUEUE_DEPTH_INTERVAL = 60  # seconds
_MAX_REDIS_RECONNECT_WAIT_SECONDS = 60.0

_timer: threading.Timer | None = None


def _cancel_timer() -> None:
    global _timer
    if _timer is not None:
        _timer.cancel()
        _timer = None


def _worker_socket_timeout_seconds(worker_ttl_seconds: int, timeout_buffer_seconds: float) -> float:
    """Return a socket timeout comfortably above RQ's blocking dequeue timeout."""
    dequeue_timeout = max(1, worker_ttl_seconds - 15)
    return float(dequeue_timeout + timeout_buffer_seconds)


def _build_redis_client(*, blocking_worker: bool):
    """Create a Redis client with keepalive and health checks enabled."""
    settings = get_settings()
    socket_timeout = settings.redis_socket_connect_timeout_seconds
    if blocking_worker:
        socket_timeout = _worker_socket_timeout_seconds(
            settings.worker_ttl_seconds,
            settings.redis_socket_timeout_buffer_seconds,
        )

    return redis_lib.from_url(
        settings.redis_url,
        health_check_interval=settings.redis_health_check_interval_seconds,
        socket_connect_timeout=settings.redis_socket_connect_timeout_seconds,
        socket_keepalive=True,
        socket_timeout=socket_timeout,
    )


class ResilientWorker(Worker):
    """RQ worker that retries idle Redis socket timeouts instead of exiting."""

    def dequeue_job_and_maintain_ttl(self, timeout, max_idle_time=None):
        connection_wait_time = 1.0

        while True:
            try:
                return super().dequeue_job_and_maintain_ttl(timeout, max_idle_time)
            except RedisTimeoutError as exc:
                self.log.warning(
                    "Worker %s: Redis socket timeout while idle (%s); "
                    "reconnecting in %.1f seconds...",
                    self.name,
                    exc,
                    connection_wait_time,
                )
                time.sleep(connection_wait_time)
                with suppress(Exception):
                    self.unsubscribe()
                with suppress(Exception):
                    self.connection.close()
                try:
                    self._set_connection(_build_redis_client(blocking_worker=True))
                    self.subscribe()
                except RedisError as reconnect_exc:
                    self.log.error(
                        "Worker %s: reconnect attempt failed: %s",
                        self.name,
                        reconnect_exc,
                    )
                connection_wait_time = min(
                    connection_wait_time * 2, _MAX_REDIS_RECONNECT_WAIT_SECONDS
                )


def _schedule_next_log(redis_url: str, queue_name: str) -> None:
    global _timer
    _timer = threading.Timer(_QUEUE_DEPTH_INTERVAL, _log_queue_depth, args=[redis_url, queue_name])
    _timer.daemon = True
    _timer.start()


def _log_queue_depth(redis_url: str, queue_name: str) -> None:
    """Log queue depth and reschedule after a successful Redis read."""
    _cancel_timer()

    try:
        client = _build_redis_client(blocking_worker=False)
        try:
            depth = len(Queue(queue_name, connection=client))
            logger.info("Queue '%s' depth: %d", queue_name, depth)
            _schedule_next_log(redis_url, queue_name)
        finally:
            client.close()
    except Exception as exc:
        logger.warning("Failed to read queue depth: %s", exc)


def main() -> None:
    """Initialize worker process logging and settings."""
    settings = get_settings()
    numeric_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    # Preserve existing handlers so caplog keeps working in tests.
    already_has_json = any(isinstance(h.formatter, _JsonFormatter) for h in root_logger.handlers)
    if not already_has_json:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(numeric_level)
        handler.setFormatter(_JsonFormatter())
        root_logger.addHandler(handler)
    logger.info("Worker initialized for queue '%s'", settings.queue_name)

    _log_queue_depth(settings.redis_url, settings.queue_name)


def run_worker() -> None:
    """Run the worker with repo-managed Redis connection settings."""
    settings = get_settings()
    main()
    connection = _build_redis_client(blocking_worker=True)
    try:
        recovered = recover_interrupted_runs(
            redis_client=connection,
            worker_ttl_seconds=settings.worker_ttl_seconds,
        )
        if recovered:
            logger.info("Recovered %d interrupted run(s)", recovered)
    except Exception:
        logger.exception("Failed to recover interrupted runs before worker startup")
    # Do not let RQ child processes inherit the recovery engine or its pool.
    dispose_worker_db_engine()
    worker = ResilientWorker(
        [settings.queue_name],
        connection=connection,
        worker_ttl=settings.worker_ttl_seconds,
    )
    try:
        worker.work(logging_level=settings.log_level)
    finally:
        _cancel_timer()
        with suppress(Exception):
            worker.connection.close()


if __name__ == "__main__":
    run_worker()
