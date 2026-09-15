"""
Pytest configuration and fixtures for backend tests.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast
from unittest.mock import MagicMock, patch

import anyio.to_thread
import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

# Set environment variables BEFORE importing any app modules
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("DEBUG", "false")
os.environ.setdefault("LOG_LEVEL", "INFO")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
os.environ.setdefault("TRUSTED_HOSTS", "testserver,localhost,127.0.0.1")
os.environ.setdefault("LOCAL_OPERATOR_TOKEN", "test-local-operator-token")

from app.database.base import Base
from app.dependencies import get_async_db, get_db, get_redis
from app.main import app
from app.models.molecule import Molecule
from app.models.run import Run, RunStatus


class ASGISyncTestClient:
    """Sync wrapper around AsyncClient + ASGITransport for integration tests."""

    def __init__(self, app_obj) -> None:
        self._app = app_obj

    async def _request_async(self, method: str, url: str, **kwargs) -> Response:
        headers = kwargs.setdefault("headers", {})
        if "X-Local-Operator-Token" not in headers:
            headers["X-Local-Operator-Token"] = os.environ["LOCAL_OPERATOR_TOKEN"]

        async def run_sync_inline(func, *args, **run_sync_kwargs):
            """Avoid the unavailable AnyIO worker pool in the ASGI test harness."""

            del run_sync_kwargs
            return func(*args)

        async with AsyncClient(
            transport=ASGITransport(app=self._app),
            base_url="http://testserver",
        ) as client:
            with patch.object(anyio.to_thread, "run_sync", run_sync_inline):
                response = await client.request(method, url, **kwargs)

                # Keep existing tests using /api/* paths working with router redirect behavior.
                if response.status_code in (301, 302, 307, 308):
                    location = response.headers.get("location")
                    if location:
                        response = await client.request(method, location, **kwargs)

            return response

    def request(self, method: str, url: str, **kwargs) -> Response:
        return asyncio.run(self._request_async(method, url, **kwargs))

    def get(self, url: str, **kwargs) -> Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> Response:
        return self.request("POST", url, **kwargs)

    def patch(self, url: str, **kwargs) -> Response:
        return self.request("PATCH", url, **kwargs)

    def delete(self, url: str, **kwargs) -> Response:
        return self.request("DELETE", url, **kwargs)


@pytest.fixture(scope="function")
def test_db() -> Generator[Session, None, None]:
    """
    Create a file-backed SQLite test database.

    Each test gets a fresh isolated database.
    """
    with TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test.db"
        engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
        )

        Base.metadata.create_all(bind=engine)
        testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = testing_session_local()

        yield session

        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(test_db: Session) -> Generator[ASGISyncTestClient, None, None]:
    """
    Create a test client with dependency overrides.

    Overrides get_db, get_async_db, and get_redis to use isolated test resources.
    Redis is replaced with None so all tests exercise graceful degradation by default.
    """

    engine_bind = cast("Engine", test_db.get_bind())

    async def override_get_db() -> AsyncGenerator[Session, None]:
        db = Session(bind=engine_bind)
        try:
            yield db
        finally:
            db.close()

    # Build an async engine over the same SQLite file as the sync test_db engine
    async_db_url = str(engine_bind.url).replace("sqlite://", "sqlite+aiosqlite://")
    async_test_engine = create_async_engine(
        async_db_url,
        connect_args={"check_same_thread": False},
    )
    async_test_session_factory = async_sessionmaker(async_test_engine, expire_on_commit=False)

    async def override_get_async_db() -> AsyncGenerator:
        async with async_test_session_factory() as session:
            yield session

    async def override_get_redis() -> AsyncGenerator:
        # No Redis in tests; callers receive None and follow graceful-degradation paths.
        yield None

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_async_db] = override_get_async_db
    app.dependency_overrides[get_redis] = override_get_redis

    test_client = ASGISyncTestClient(app)
    try:
        yield test_client
    finally:
        app.dependency_overrides.clear()
        asyncio.run(async_test_engine.dispose())


@pytest.fixture
def mock_redis():
    """
    Create a mock Redis client for testing.

    Prevents tests from requiring Redis to be running.
    """
    redis = MagicMock()
    redis.ping.return_value = True
    redis.get.return_value = None
    redis.set.return_value = True
    redis.delete.return_value = True
    redis.exists.return_value = False
    redis.lpush.return_value = 1
    redis.lrange.return_value = []
    redis.expire.return_value = True
    return redis


@pytest.fixture
def sample_molecule(test_db: Session) -> Molecule:
    """
    Create a sample molecule for testing.

    Returns:
        Sample H2 molecule
    """
    molecule = Molecule(
        name="H2_sample",
        atoms=[
            {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.0},
            {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.735},
        ],
        charge=0,
        multiplicity=1,
        active_space={"n_electrons": 2, "n_orbitals": 2},
    )
    test_db.add(molecule)
    test_db.commit()
    test_db.refresh(molecule)
    return molecule


@pytest.fixture
def sample_run(test_db: Session, sample_molecule: Molecule) -> Run:
    """
    Create a sample run for testing.

    Returns:
        Sample run in CREATED state
    """
    run = Run(
        molecule_id=sample_molecule.id,
        status=RunStatus.CREATED,
        config_json={
            "basis_set": "sto-3g",
            "ansatz": "UCC",
            "optimizer": "COBYLA",
            "max_iterations": 100,
            "backend": "aer_simulator",
        },
    )
    test_db.add(run)
    test_db.commit()
    test_db.refresh(run)
    return run


@pytest.fixture
def client_with_redis(test_db: Session, mock_redis) -> Generator[ASGISyncTestClient, None, None]:
    """
    Test client with a mock Redis client injected.

    get_redis yields mock_redis (not None), so RunService.create() exercises
    the QUEUED path. queue_service.enqueue_run is patched to return a
    deterministic fake job ID without making any real RQ calls.
    """
    from unittest.mock import patch

    engine_bind = cast("Engine", test_db.get_bind())

    async def override_get_db() -> AsyncGenerator[Session, None]:
        db = Session(bind=engine_bind)
        try:
            yield db
        finally:
            db.close()

    async_db_url = str(engine_bind.url).replace("sqlite://", "sqlite+aiosqlite://")
    async_test_engine = create_async_engine(
        async_db_url,
        connect_args={"check_same_thread": False},
    )
    async_test_session_factory = async_sessionmaker(async_test_engine, expire_on_commit=False)

    async def override_get_async_db() -> AsyncGenerator:
        async with async_test_session_factory() as session:
            yield session

    async def override_get_redis() -> AsyncGenerator:
        yield mock_redis

    with patch(
        "app.services.queue_service.enqueue_run",
        return_value="test-rq-job-id",
    ):
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_async_db] = override_get_async_db
        app.dependency_overrides[get_redis] = override_get_redis

        test_client = ASGISyncTestClient(app)
        try:
            yield test_client
        finally:
            app.dependency_overrides.clear()
            asyncio.run(async_test_engine.dispose())
