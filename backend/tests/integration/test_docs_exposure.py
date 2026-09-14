"""Integration tests for the interactive API documentation gate."""

from __future__ import annotations

import asyncio
import os
from unittest.mock import patch

from app.config import Settings, get_settings
from app.main import create_app
from httpx import ASGITransport, AsyncClient, Response

HARDENED_ENVIRONMENT = {
    "DATABASE_URL": "sqlite:///:memory:",
    "DB_PASSWORD": "real-password",
    "REDIS_URL": "redis://localhost:6379/0",
    "ALLOW_INSECURE_DEFAULTS": "false",
    "SKIP_PUBCHEM_SYNC": "true",
}

LOCAL_ENVIRONMENT = {
    "DATABASE_URL": "sqlite:///:memory:",
    "REDIS_URL": "redis://localhost:6379/0",
    "SKIP_PUBCHEM_SYNC": "true",
}


class LifespanFreeClient:
    """Minimal synchronous client for route-only checks."""

    def __init__(self, app) -> None:
        self.app = app

    def get(self, url: str) -> Response:
        async def request() -> Response:
            async with AsyncClient(
                transport=ASGITransport(app=self.app),
                base_url="http://testserver",
            ) as client:
                return await client.get(url)

        return asyncio.run(request())

    def __enter__(self) -> "LifespanFreeClient":
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def _client_with_environment(environment: dict[str, str]) -> LifespanFreeClient:
    """Build an app whose settings come from the supplied environment."""
    with patch.dict(os.environ, environment, clear=False):
        get_settings.cache_clear()
        settings = Settings(_env_file=None)
        with patch("app.main.get_settings", return_value=settings):
            app = create_app()
    get_settings.cache_clear()
    return LifespanFreeClient(app)


def test_docs_are_served_for_local_defaults() -> None:
    """The local workflow keeps /docs and the schema available."""
    with _client_with_environment(LOCAL_ENVIRONMENT) as client:
        assert client.get("/docs").status_code == 200
        assert client.get("/openapi.json").status_code == 200


def test_docs_are_absent_when_insecure_defaults_disabled() -> None:
    """Hardened deployments do not expose the interactive docs surface."""
    with _client_with_environment(HARDENED_ENVIRONMENT) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404
        assert client.get("/openapi.json").status_code == 404


def test_root_endpoint_reports_docs_availability() -> None:
    """The root payload must not advertise a docs path that 404s."""
    with _client_with_environment(LOCAL_ENVIRONMENT) as local:
        assert local.get("/").json()["docs"] == "/docs"
    with _client_with_environment(HARDENED_ENVIRONMENT) as hardened:
        assert hardened.get("/").json()["docs"] is None
