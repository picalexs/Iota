"""
Health check endpoint.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, Response
from fastapi import status as http_status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.dependencies import get_db
from app.schemas.health import ComponentStatus, StatusResponse, WorkerStatus
from app.services.queue_service import check_redis_health

if TYPE_CHECKING:
    from redis import Redis

router = APIRouter()
status_router = APIRouter()
logger = logging.getLogger(__name__)


def get_redis_client() -> Redis | None:
    """
    Get or initialize Redis client.

    Returns:
        Redis client or None if not configured/available.
    """
    settings = get_settings()
    if not settings.redis_url:
        return None

    try:
        import redis

        return redis.from_url(settings.redis_url, decode_responses=True)
    except Exception as exc:
        logger.debug("Redis client initialization failed: %s", exc)
        return None


def check_postgres(db: Session) -> ComponentStatus:
    """
    Check PostgreSQL connectivity.

    Returns:
        "connected" or "disconnected"
    """
    try:
        db.execute(text("SELECT 1"))
        return "connected"
    except Exception:
        logger.exception("PostgreSQL health check failed")
        return "disconnected"


def check_redis() -> ComponentStatus:
    """
    Check Redis connectivity.

    Returns:
        "connected", "disconnected", or "unknown"
    """
    client = get_redis_client()
    if client is None:
        return "unknown"

    try:
        if check_redis_health(client=client):
            return "connected"
        return "disconnected"
    finally:
        client.close()


def check_worker_queue() -> WorkerStatus:
    """
    Check whether at least one RQ worker is registered in Redis.

    Returns:
        "active" if workers are registered, "inactive" if none, "unknown" if Redis unavailable.
    """
    client: Redis | None = None
    try:
        client = get_redis_client()
        if client is None:
            return "unknown"

        from rq import Worker

        workers = Worker.all(connection=client)
        return "active" if workers else "inactive"
    except Exception:
        logger.exception("Worker queue check failed")
        return "unknown"
    finally:
        if client is not None:
            client.close()


@router.get(
    "",
    summary="Liveness probe",
    responses={200: {"description": "Service process is running"}},
)
def health_check() -> dict:
    """
    Simple liveness probe.

    Returns 200 as long as the process is running. Does **not** check
    database or Redis connectivity — use ``GET /api/status`` for that.
    """
    return {"status": "ok"}


@status_router.get(
    "",
    summary="System readiness probe",
    responses={
        200: {"description": "All components reachable"},
        503: {
            "description": "One or more components unreachable",
            "model": StatusResponse,
        },
    },
)
def system_status(
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> StatusResponse:
    """
    System readiness check.

    Checks actual connectivity to PostgreSQL and Redis.

    Returns:
        - **HTTP 200** when all components are reachable.
        - **HTTP 503** when PostgreSQL or Redis is unreachable.
    """
    db_status = check_postgres(db)
    redis_status = check_redis()

    if db_status == "disconnected" or redis_status == "disconnected":
        response.status_code = http_status.HTTP_503_SERVICE_UNAVAILABLE

    return StatusResponse(api="ready", db=db_status, redis=redis_status)
