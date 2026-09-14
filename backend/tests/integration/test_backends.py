"""Integration tests for backend discovery endpoints."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import anyio.to_thread
import pytest
from app.database.base import Base
from app.dependencies import (
    ensure_local_operator_access,
    get_async_db,
    get_db,
    get_redis,
    require_local_operator_access,
)
from app.exceptions import APIException
from app.main import app
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from starlette.requests import Request


@pytest.fixture(scope="function")
def backend_app() -> Generator:
    with TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test.db"
        engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=engine)

        async_db_url = str(engine.url).replace("sqlite://", "sqlite+aiosqlite://")
        async_engine = create_async_engine(
            async_db_url,
            connect_args={"check_same_thread": False},
        )
        async_session_factory = async_sessionmaker(async_engine, expire_on_commit=False)

        async def override_get_db() -> AsyncGenerator[Session, None]:
            db = Session(bind=engine)
            try:
                yield db
            finally:
                db.close()

        async def override_get_async_db() -> AsyncGenerator:
            async with async_session_factory() as session:
                yield session

        async def override_get_redis() -> AsyncGenerator:
            yield None

        def allow_local_operator_access() -> None:
            return None

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_async_db] = override_get_async_db
        app.dependency_overrides[get_redis] = override_get_redis
        app.dependency_overrides[require_local_operator_access] = allow_local_operator_access

        try:
            yield app
        finally:
            app.dependency_overrides.clear()
            asyncio.run(async_engine.dispose())
            Base.metadata.drop_all(bind=engine)
            engine.dispose()


async def _request(backend_app, method: str, url: str, **kwargs):
    headers = kwargs.setdefault("headers", {})
    headers.setdefault("X-Local-Operator-Token", "test-local-operator-token")

    async def run_sync_inline(func, *args, **run_sync_kwargs):
        """Avoid the unavailable AnyIO worker pool in the ASGI test harness."""

        del run_sync_kwargs
        return func(*args)

    async with AsyncClient(
        transport=ASGITransport(app=backend_app),
        base_url="http://testserver",
    ) as client:
        with patch.object(anyio.to_thread, "run_sync", run_sync_inline):
            return await client.request(method, url, **kwargs)


@pytest.mark.asyncio
async def test_list_backends_endpoint_exposes_aer(backend_app) -> None:
    response = await _request(backend_app, "GET", "/api/backends")

    assert response.status_code == 200
    data = response.json()
    aer = next(item for item in data["backends"] if item["target"] == "aer_simulator")
    assert aer["available"] is True
    assert aer["supports_noise_profile"] is True


def test_backends_endpoint_rejects_invalid_local_operator_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOCAL_OPERATOR_TOKEN", "test-local-operator-token")
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/backends",
            "headers": [(b"x-local-operator-token", b"wrong-token")],
        }
    )

    with pytest.raises(APIException) as exc_info:
        ensure_local_operator_access(request)

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "FORBIDDEN"


@pytest.mark.asyncio
async def test_resolve_aer_endpoint_returns_local_backend(backend_app) -> None:
    response = await _request(
        backend_app,
        "POST",
        "/api/backends/resolve",
        json={
            "target": "aer_simulator",
            "backend_options": {"shots": 1024, "aer_method": "automatic"},
            "required_qubits": 4,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["resolved"] is True
    assert data["backend_name"] == "aer_simulator"


@pytest.mark.asyncio
async def test_transpile_preview_endpoint_reports_metadata(backend_app) -> None:
    response = await _request(
        backend_app,
        "POST",
        "/api/backends/transpile-preview",
        json={
            "target": "aer_simulator",
            "backend_options": {"optimization_level": 2, "shots": 2048},
            "num_qubits": 4,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["feasible"] is True
    assert data["metadata"]["optimization_level"] == 2
    assert data["metadata"]["shots"] == 2048
