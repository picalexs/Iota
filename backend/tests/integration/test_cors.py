"""
Integration tests for CORS middleware configuration.

Verifies that the CORSMiddleware is correctly configured: allowed origins
receive Access-Control-Allow-Origin response headers, and disallowed origins
do not.

The test conftest sets CORS_ORIGINS=http://localhost:3000, so that is the
only explicitly allowed origin in these tests.
"""

from __future__ import annotations

import logging

from tests.conftest import ASGISyncTestClient


class TestCORSResponseHeaders:
    """Tests that CORS response headers are present on cross-origin requests."""

    def test_allowed_origin_receives_acao_header(self, client: ASGISyncTestClient):
        """Allowed origin gets Access-Control-Allow-Origin header."""
        response = client.get("/api/health", headers={"Origin": "http://localhost:3000"})

        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        assert response.headers["access-control-allow-origin"] == "http://localhost:3000"

    def test_disallowed_origin_has_no_acao_header(self, client: ASGISyncTestClient):
        """Disallowed origin does not receive Access-Control-Allow-Origin header."""
        response = client.get("/api/health", headers={"Origin": "http://evil.example.com"})

        assert response.status_code == 200
        assert "access-control-allow-origin" not in response.headers

    def test_no_origin_header_has_no_acao_header(self, client: ASGISyncTestClient):
        """Same-origin (no Origin header) request has no CORS headers."""
        response = client.get("/api/health")

        assert response.status_code == 200
        assert "access-control-allow-origin" not in response.headers


class TestCORSPreflightRequest:
    """Tests for OPTIONS preflight handling."""

    def test_preflight_allowed_origin_returns_200(self, client: ASGISyncTestClient):
        """OPTIONS preflight for allowed origin succeeds with CORS headers."""
        response = client.request(
            "OPTIONS",
            "/api/molecules",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )

        # CORSMiddleware returns 200 for preflight
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        assert response.headers["access-control-allow-origin"] == "http://localhost:3000"

    def test_preflight_disallowed_origin_has_no_acao_header(self, client: ASGISyncTestClient):
        """OPTIONS preflight from disallowed origin does not get CORS headers."""
        response = client.request(
            "OPTIONS",
            "/api/molecules",
            headers={
                "Origin": "http://attacker.example.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )

        assert "access-control-allow-origin" not in response.headers


class TestRequestLoggingIntegration:
    """Integration test verifying RequestLoggingMiddleware fires through the full stack."""

    def test_http_request_produces_access_log(self, client: ASGISyncTestClient, caplog):
        """A real HTTP request through the app produces an access log record."""
        with caplog.at_level(logging.INFO, logger="app.access"):
            response = client.get("/api/health")

        assert response.status_code == 200
        access_records = [r for r in caplog.records if r.name == "app.access"]
        assert len(access_records) == 1
        msg = access_records[0].message
        assert "GET" in msg
        assert "/api/health" in msg
        assert "200" in msg
        assert "ms" in msg
