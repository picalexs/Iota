"""
Integration tests for GET /api/health and GET /api/status endpoints.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from tests.conftest import ASGISyncTestClient


class TestHealthEndpoint:
    """Tests for GET /api/health (simple liveness probe)."""

    def test_health_returns_200(self, client: ASGISyncTestClient):
        """GET /api/health always returns 200."""
        response = client.get("/api/health")
        assert response.status_code == 200

    def test_health_returns_ok_body(self, client: ASGISyncTestClient):
        """GET /api/health body is {"status": "ok"}."""
        response = client.get("/api/health")
        assert response.json() == {"status": "ok"}

    def test_health_does_not_check_dependencies(self, client: ASGISyncTestClient):
        """GET /api/health returns 200 even when Redis is unavailable."""
        with patch(
            "app.api.v1.endpoints.health.get_redis_client",
            side_effect=Exception("Redis dead"),
        ):
            response = client.get("/api/health")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestSystemStatusEndpoint:
    """Tests for GET /api/status (readiness probe with actual connectivity checks)."""

    def test_status_all_connected_returns_200(self, client: ASGISyncTestClient):
        """GET /api/status returns 200 when all components are reachable."""
        with patch("app.api.v1.endpoints.health.get_redis_client") as mock_get_redis:
            mock_redis = MagicMock()
            mock_redis.ping.return_value = True
            mock_get_redis.return_value = mock_redis

            response = client.get("/api/status")

        assert response.status_code == 200
        body = response.json()
        assert body["api"] == "ready"
        assert body["db"] == "connected"
        assert body["redis"] == "connected"

    def test_status_db_disconnected_returns_503(self, client: ASGISyncTestClient):
        """GET /api/status returns 503 when the database is not reachable."""
        with patch("app.api.v1.endpoints.health.check_postgres", return_value="disconnected"):
            with patch("app.api.v1.endpoints.health.get_redis_client") as mock_get_redis:
                mock_redis = MagicMock()
                mock_redis.ping.return_value = True
                mock_get_redis.return_value = mock_redis

                response = client.get("/api/status")

        assert response.status_code == 503
        body = response.json()
        assert body["api"] == "ready"
        assert body["db"] == "disconnected"

    def test_status_redis_disconnected_returns_503(self, client: ASGISyncTestClient):
        """GET /api/status returns 503 when Redis is not reachable."""
        with patch("app.api.v1.endpoints.health.get_redis_client") as mock_get_redis:
            mock_redis = MagicMock()
            mock_redis.ping.side_effect = Exception("Connection refused")
            mock_get_redis.return_value = mock_redis

            response = client.get("/api/status")

        assert response.status_code == 503
        body = response.json()
        assert body["api"] == "ready"
        assert body["redis"] == "disconnected"

    def test_status_redis_unknown_returns_200(self, client: ASGISyncTestClient):
        """GET /api/status returns 200 when Redis is unconfigured (unknown, not an error)."""
        with patch("app.api.v1.endpoints.health.get_redis_client", return_value=None):
            response = client.get("/api/status")

        assert response.status_code == 200
        body = response.json()
        assert body["api"] == "ready"
        assert body["redis"] == "unknown"

    def test_status_response_schema(self, client: ASGISyncTestClient):
        """GET /api/status response body matches StatusResponse schema."""
        with patch("app.api.v1.endpoints.health.get_redis_client") as mock_get_redis:
            mock_redis = MagicMock()
            mock_redis.ping.return_value = True
            mock_get_redis.return_value = mock_redis

            response = client.get("/api/status")

        body = response.json()
        assert "api" in body
        assert "db" in body
        assert "redis" in body
        assert body["api"] == "ready"
        assert body["db"] in ("connected", "disconnected", "unknown")
        assert body["redis"] in ("connected", "disconnected", "unknown")
        # No timestamp or worker fields (those belong to /api/health legacy response)
        assert "timestamp" not in body
        assert "worker" not in body
