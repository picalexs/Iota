"""
Redis/RQ queue service for job management.
"""

from __future__ import annotations

import logging
from enum import StrEnum
from uuid import UUID

from redis import Redis
from redis.exceptions import RedisError
from rq.exceptions import InvalidJobOperation, NoSuchJobError

from app.config import get_settings

logger = logging.getLogger(__name__)


class QueueFailureReason(StrEnum):
    """Safe diagnostic categories for queue operations."""

    CONFIGURATION = "configuration_error"
    CONNECTION = "connection_failure"
    MISSING_JOB = "missing_job"
    INVALID_JOB_STATE = "invalid_job_state"
    UNKNOWN = "unknown_failure"


def _classify_queue_error(error: BaseException) -> QueueFailureReason:
    """Map queue and Redis exceptions to stable, non-sensitive categories."""
    if isinstance(error, NoSuchJobError):
        return QueueFailureReason.MISSING_JOB
    if isinstance(error, InvalidJobOperation):
        return QueueFailureReason.INVALID_JOB_STATE
    if isinstance(error, RedisError):
        return QueueFailureReason.CONNECTION
    return QueueFailureReason.UNKNOWN


def _safe_job_id(job_id: str | None) -> str | None:
    """Keep job identifiers useful in logs without copying long values."""
    if not job_id:
        return None
    return job_id if len(job_id) <= 12 else f"...{job_id[-9:]}"


def _log_queue_failure(
    operation: str,
    reason: QueueFailureReason,
    *,
    job_id: str | None = None,
    error: BaseException | None = None,
    include_traceback: bool = False,
    level: int = logging.WARNING,
) -> None:
    """Write a structured, safe queue diagnostic entry."""
    extra = {
        "queue_operation": operation,
        "queue_failure_reason": reason.value,
    }
    safe_id = _safe_job_id(job_id)
    if safe_id is not None:
        extra["queue_job_id"] = safe_id

    logger.log(
        level,
        "Queue operation '%s' failed (%s)%s",
        operation,
        reason.value,
        f" for job {safe_id}" if safe_id is not None else "",
        extra=extra,
        exc_info=include_traceback and error is not None,
    )


def enqueue_run(run_id: UUID, redis_client, *, execution_generation: int = 1) -> str:
    """
    Enqueue a run for execution on the quantum worker queue.

    Registers on_success and on_failure callbacks so the worker can emit
    run_events, update run status, and persist results.

    Args:
        run_id: UUID of the run to execute.
        redis_client: Connected Redis client.

    Returns:
        The RQ job ID as a string.
    """
    from rq import Queue

    settings = get_settings()
    queue_name = settings.queue_name
    queue = Queue(queue_name, connection=redis_client)
    job_timeout = max(1, int(settings.quantum_job_timeout_seconds))
    job = queue.enqueue(
        "worker.tasks.enqueueable_execute_run",
        {"run_id": str(run_id), "execution_generation": int(execution_generation)},
        job_timeout=job_timeout,
        on_success="worker.jobs.on_job_success",
        on_failure="worker.jobs.on_job_failure",
    )
    logger.info(
        "Enqueued run %s as RQ job %s on queue '%s' with timeout=%ss",
        run_id,
        job.id,
        queue_name,
        job_timeout,
    )
    return job.id


def cancel_queued_job(job_id: str, redis_client) -> None:
    """
    Cancel a job in the RQ queue or ask a worker to stop it if already started.

    Logs a warning with full traceback if removal/stop fails. The DB status transition
    is authoritative — the worker will detect CANCELLED on its next status poll
    even if queue removal fails.

    Args:
        job_id: RQ job ID stored in run_metadata["rq_job_id"].
        redis_client: Connected Redis client.
    """
    from rq.command import send_stop_job_command
    from rq.job import Job

    try:
        job = Job.fetch(job_id, connection=redis_client)
        if job.get_status(refresh=True) == "started":
            send_stop_job_command(redis_client, job_id)
            logger.info("Sent stop command for started RQ job %s", job_id)
            return

        job.cancel()
        logger.info("Cancelled RQ job %s", job_id)
    except NoSuchJobError as error:
        _log_queue_failure(
            "cancel_queued_job",
            _classify_queue_error(error),
            job_id=job_id,
            error=error,
        )
        logger.warning(
            "RQ job %s not found in queue (may have already started or expired)",
            job_id,
        )
    except InvalidJobOperation as error:
        _log_queue_failure(
            "cancel_queued_job",
            _classify_queue_error(error),
            job_id=job_id,
            error=error,
            level=logging.INFO,
        )
        logger.info(
            "RQ job %s is already in a terminal state; DB cancellation remains authoritative",
            job_id,
        )
    except RedisError as error:
        _log_queue_failure(
            "cancel_queued_job",
            _classify_queue_error(error),
            job_id=job_id,
            error=error,
            include_traceback=True,
        )
        logger.warning(
            "Failed to reach Redis while cancelling RQ job %s — worker will detect CANCELLED via DB poll",
            job_id,
        )
    except Exception as error:
        _log_queue_failure(
            "cancel_queued_job",
            _classify_queue_error(error),
            job_id=job_id,
            error=error,
            include_traceback=True,
        )
        logger.warning(
            "Failed to cancel or stop RQ job %s — worker will detect CANCELLED via DB poll",
            job_id,
        )


def count_workers(redis_client) -> int:
    """
    Count active RQ workers registered in Redis.

    Args:
        redis_client: Connected Redis client.

    Returns:
        Number of registered workers, or 0 on error.
    """
    from rq import Worker

    try:
        workers = Worker.all(connection=redis_client)
        return len(workers)
    except RedisError as error:
        _log_queue_failure(
            "count_workers",
            _classify_queue_error(error),
            error=error,
            include_traceback=True,
        )
        return 0
    except Exception as error:
        _log_queue_failure(
            "count_workers",
            _classify_queue_error(error),
            error=error,
            include_traceback=True,
        )
        logger.warning("Failed to count RQ workers")
        return 0


def check_redis_health(client: Redis | None = None) -> bool:
    """
    Test Redis connectivity by sending a PING.

    If a client is provided it is tested in-place without closing it.
    If no client is provided a temporary one is created from the configured
    ``REDIS_URL``, tested, and closed immediately.

    Args:
        client: Optional connected Redis client to test. When ``None`` a
                temporary client is created from settings and closed after use.

    Returns:
        ``True`` if the ping succeeds, ``False`` if Redis is unavailable.
    """
    if client is not None:
        try:
            client.ping()
            return True
        except RedisError as error:
            _log_queue_failure(
                "redis_health",
                _classify_queue_error(error),
                error=error,
                include_traceback=True,
            )
            return False
        except Exception as error:
            _log_queue_failure(
                "redis_health",
                _classify_queue_error(error),
                error=error,
                include_traceback=True,
            )
            return False

    try:
        settings = get_settings()
        redis_url = settings.redis_url
    except Exception:
        _log_queue_failure("redis_health_settings", QueueFailureReason.CONFIGURATION)
        return False

    if not redis_url:
        return False

    temp_client: Redis | None = None
    try:
        temp_client = Redis.from_url(redis_url)
        temp_client.ping()
        return True
    except RedisError as error:
        _log_queue_failure(
            "redis_health",
            _classify_queue_error(error),
            error=error,
            include_traceback=True,
        )
        return False
    except Exception as error:
        _log_queue_failure(
            "redis_health",
            _classify_queue_error(error),
            error=error,
            include_traceback=True,
        )
        return False
    finally:
        if temp_client is not None:
            try:
                temp_client.close()
            except RedisError as error:
                _log_queue_failure(
                    "redis_health_close",
                    _classify_queue_error(error),
                    error=error,
                    include_traceback=True,
                )
            except Exception as error:
                _log_queue_failure(
                    "redis_health_close",
                    _classify_queue_error(error),
                    error=error,
                    include_traceback=True,
                )
