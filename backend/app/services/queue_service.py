"""
Redis/RQ queue service for job management.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
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


@dataclass(frozen=True, slots=True)
class QueueRoutingDecision:
    """Internal queue and resource decision for one persisted run."""

    queue_name: str
    resource_class: str
    fallback_reason: str | None = None
    requested_auto_stages: tuple[str, ...] = ()
    provider: str | None = None
    provider_requirements: tuple[str, ...] = ()
    routing_error: str | None = None


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


def _normalize_setting(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return value.strip().upper()


def _configured_provider_queue(settings: Any, provider: str) -> str | None:
    """Return an explicitly configured queue for one chemistry provider."""
    setting_name = {
        "gpu4pyscf": "gpu4pyscf_queue_name",
        "sbd": "sbd_gpu_queue_name",
    }.get(provider)
    value = getattr(settings, setting_name, None) if setting_name else None
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def _provider_routing_decision(
    *,
    settings: Any,
    providers: tuple[str, ...],
    requested_auto_stages: tuple[str, ...],
) -> QueueRoutingDecision | None:
    """Resolve provider-specific GPU routing without guessing image contents."""
    if not providers:
        return None
    if len(providers) > 1:
        return QueueRoutingDecision(
            queue_name=str(settings.queue_name),
            resource_class="gpu",
            requested_auto_stages=requested_auto_stages,
            provider_requirements=providers,
            routing_error=(
                "multiple_gpu_providers_require_one_validated_combined_image_or_stage_split"
            ),
        )

    provider = providers[0]
    if provider == "aer":
        queue_name = str(settings.gpu_queue_name)
    else:
        queue_name = _configured_provider_queue(settings, provider)
        if queue_name is None:
            return QueueRoutingDecision(
                queue_name=str(settings.queue_name),
                resource_class="gpu",
                requested_auto_stages=requested_auto_stages,
                provider=provider,
                provider_requirements=providers,
                routing_error=f"{provider}_gpu_queue_not_configured",
            )
    return QueueRoutingDecision(
        queue_name=queue_name,
        resource_class="gpu",
        requested_auto_stages=requested_auto_stages,
        provider=provider,
        provider_requirements=providers,
    )


def queue_routing_for_run(
    run: object,
    *,
    settings: Any | None = None,
) -> QueueRoutingDecision:
    """Resolve the worker queue without guessing provider availability.

    Explicit GPU stages require the GPU queue. Chemistry ``AUTO`` requests are
    resolved by the worker and therefore remain on the CPU queue until a
    provider is selected explicitly. This avoids reserving a GPU worker for a
    request that may fall back to CPU.
    """
    resolved_settings = settings or get_settings()
    config_snapshot = getattr(run, "config_json", None)
    if not isinstance(config_snapshot, dict):
        return QueueRoutingDecision(
            queue_name=str(resolved_settings.queue_name),
            resource_class="cpu",
        )

    backend_options = config_snapshot.get("backend_options")
    chemistry_options = config_snapshot.get("chemistry_options")
    chemistry_options = chemistry_options if isinstance(chemistry_options, dict) else {}
    chemistry_stages = {
        "reference_scf": chemistry_options.get("reference_device"),
        "selected_ci": chemistry_options.get("selected_ci_device"),
    }

    auto_stages = tuple(
        stage
        for stage, value in chemistry_stages.items()
        if _normalize_setting(value) == "AUTO"
    )
    providers: list[str] = []
    if isinstance(backend_options, dict) and _normalize_setting(
        backend_options.get("device")
    ) == "GPU":
        providers.append("aer")
    if _normalize_setting(chemistry_stages["reference_scf"]) == "GPU":
        providers.append("gpu4pyscf")
    if _normalize_setting(chemistry_stages["selected_ci"]) == "GPU":
        providers.append("sbd")

    provider_decision = _provider_routing_decision(
        settings=resolved_settings,
        providers=tuple(dict.fromkeys(providers)),
        requested_auto_stages=auto_stages,
    )
    if provider_decision is not None:
        return provider_decision
    return QueueRoutingDecision(
        queue_name=str(resolved_settings.queue_name),
        resource_class="cpu",
        fallback_reason=(
            "auto_gpu_provider_selection_deferred_to_worker"
            if auto_stages
            else None
        ),
        requested_auto_stages=auto_stages,
    )


def queue_name_for_run(run: object, *, settings: Any | None = None) -> str:
    """Return the queue selected by :func:`queue_routing_for_run`."""
    return queue_routing_for_run(run, settings=settings).queue_name


def record_queue_routing_metadata(
    run: object,
    decision: QueueRoutingDecision,
) -> None:
    """Record deferred AUTO intent in the existing run metadata field."""
    if (
        decision.fallback_reason is None
        and decision.provider is None
        and decision.routing_error is None
    ):
        return

    metadata = getattr(run, "run_metadata", None)
    if not isinstance(metadata, dict):
        return

    routing_metadata = metadata.get("queue_routing")
    if not isinstance(routing_metadata, dict):
        routing_metadata = {}
    routing_metadata = {
        **routing_metadata,
        "queue": decision.queue_name,
        "resource_class": decision.resource_class,
        "requested_auto_stages": list(decision.requested_auto_stages),
        "fallback_reason": decision.fallback_reason,
    }
    if decision.provider is not None:
        routing_metadata["provider"] = decision.provider
    if decision.provider_requirements:
        routing_metadata["provider_requirements"] = list(decision.provider_requirements)
    if decision.routing_error is not None:
        routing_metadata["routing_error"] = decision.routing_error
    run.run_metadata = {**metadata, "queue_routing": routing_metadata}


def enqueue_run(
    run_id: UUID,
    redis_client,
    *,
    execution_generation: int = 1,
    queue_name: str | None = None,
) -> str:
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
    selected_queue_name = queue_name or settings.queue_name
    queue = Queue(selected_queue_name, connection=redis_client)
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
        selected_queue_name,
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
