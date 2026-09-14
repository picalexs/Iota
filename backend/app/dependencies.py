"""FastAPI dependencies."""

import logging
import secrets
from collections.abc import AsyncGenerator, Generator
from typing import Annotated

from redis import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.config import get_settings
from app.exceptions import APIException, InternalError
from app.models.enums import BackendTarget
from app.schemas.run_config import NoiseModelSource
from app.schemas.run_requests import RunCreate
from shared.local_operator_auth import (
    LocalOperatorAuthError,
    get_local_operator_auth,
    get_local_operator_header_name,
)

logger = logging.getLogger(__name__)


def get_db(request: Annotated[Request, None]) -> Generator[Session, None, None]:
    """Yield a synchronous database session."""
    try:
        session_factory = request.app.state.session_factory
    except AttributeError as err:
        raise RuntimeError(
            "Session factory not initialized. Ensure app.lifespan has been called."
        ) from err

    db = session_factory()
    try:
        yield db
    finally:
        db.close()


async def get_async_db(request: Annotated[Request, None]) -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session for streaming endpoints."""
    try:
        factory = request.app.state.async_session_factory
    except AttributeError as err:
        raise RuntimeError(
            "Async session factory not initialized. Ensure app.lifespan has been called."
        ) from err

    async with factory() as session:
        yield session


async def get_redis() -> AsyncGenerator[Redis | None, None]:
    """
    Yield None when Redis is unavailable so callers can degrade gracefully.
    """
    settings = get_settings()
    client: Redis | None = None
    try:
        client = Redis.from_url(settings.redis_url)
    except Exception:
        logger.warning("Redis client initialization failed", exc_info=True)
    try:
        yield client
    finally:
        if client is not None:
            client.close()


def ensure_local_operator_access(request: Request) -> None:
    """Require the configured local operator token for sensitive local actions."""

    try:
        expected = get_local_operator_auth().token
    except LocalOperatorAuthError as exc:
        raise InternalError("Local operator access is misconfigured") from exc

    header_name = get_local_operator_header_name()
    provided = request.headers.get(header_name, "")
    if not provided or not secrets.compare_digest(provided, expected):
        raise APIException(
            "FORBIDDEN",
            "Local operator access is required for IBM credential management and IBM submissions.",
            status_code=403,
        )


def run_requires_local_operator_access(run_in: RunCreate) -> bool:
    """Return whether a run contract may use saved IBM account material."""

    if run_in.backend_target == BackendTarget.IBM_RUNTIME:
        return True

    return (
        run_in.backend_target == BackendTarget.AER_SIMULATOR
        and run_in.noise_profile is not None
        and run_in.noise_profile.source == NoiseModelSource.BACKEND_DERIVED
    )


def require_local_operator_access(request: Request) -> None:
    """Dependency wrapper for local operator-only routes."""

    ensure_local_operator_access(request)
