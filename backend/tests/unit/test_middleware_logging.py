"""
Unit tests for RequestLoggingMiddleware and sanitize_query_string.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock

import pytest
from app.middleware.logging import RequestLoggingMiddleware, sanitize_query_string

# ---------------------------------------------------------------------------
# sanitize_query_string
# ---------------------------------------------------------------------------


class TestSanitizeQueryString:
    """Tests for query-string sanitization helper."""

    def test_empty_string_returns_empty(self):
        assert sanitize_query_string("") == ""

    def test_non_sensitive_param_not_redacted(self):
        assert sanitize_query_string("q=H2") == "q=H2"

    def test_token_param_is_redacted(self):
        result = sanitize_query_string("token=my-secret-token")
        assert result == "token=***"

    def test_password_param_is_redacted(self):
        sensitive_key = "password"
        raw_value = "dummy-secret-value"
        result = sanitize_query_string(f"{sensitive_key}={raw_value}")
        assert result == f"{sensitive_key}=***"

    def test_api_key_param_is_redacted(self):
        result = sanitize_query_string("api_key=supersecret")
        assert result == "api_key=***"

    def test_ibm_quantum_token_param_is_redacted(self):
        result = sanitize_query_string("ibm_quantum_token=abc123")
        assert result == "ibm_quantum_token=***"

    def test_access_token_param_is_redacted(self):
        result = sanitize_query_string("access_token=abc123")
        assert result == "access_token=***"

    def test_refresh_token_param_is_redacted(self):
        result = sanitize_query_string("refresh_token=abc123")
        assert result == "refresh_token=***"

    def test_mixed_params_partial_redaction(self):
        result = sanitize_query_string("q=H2&token=secret&limit=10")
        assert "q=H2" in result
        assert "token=***" in result
        assert "limit=10" in result
        assert "secret" not in result

    def test_param_without_value_preserved(self):
        result = sanitize_query_string("flag")
        assert result == "flag"

    def test_url_encoded_array_style_sensitive_key_is_redacted(self):
        # 'token%5B%5D' decodes to 'token[]'; base key 'token' is sensitive,
        # so the value must be redacted despite the bracket suffix.
        result = sanitize_query_string("token%5B%5D=value")
        assert "token%5B%5D=***" in result
        assert "value" not in result

    def test_case_insensitive_key_matching(self):
        # Keys are lowercased before matching
        result = sanitize_query_string("TOKEN=secret")
        assert result == "TOKEN=***"

    def test_secret_param_is_redacted(self):
        result = sanitize_query_string("secret=abc")
        assert result == "secret=***"

    def test_authorization_param_is_redacted(self):
        result = sanitize_query_string("authorization=Bearer+abc")
        assert result == "authorization=***"


# ---------------------------------------------------------------------------
# RequestLoggingMiddleware
# ---------------------------------------------------------------------------


def _make_scope(
    *,
    path: str = "/test",
    method: str = "GET",
    query_string: bytes = b"",
    scope_type: str = "http",
) -> dict[str, Any]:
    return {
        "type": scope_type,
        "method": method,
        "path": path,
        "query_string": query_string,
    }


def _make_app(status: int = 200) -> Callable[..., Awaitable[None]]:
    """Return a minimal ASGI app that sends a response with the given status."""

    async def inner_app(scope, receive, send):
        await send({"type": "http.response.start", "status": status, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    return inner_app


class TestRequestLoggingMiddleware:
    """Tests for RequestLoggingMiddleware ASGI middleware."""

    @pytest.mark.asyncio
    async def test_logs_method_path_and_status(self, caplog):
        """Middleware logs method, path, and status code."""
        middleware = RequestLoggingMiddleware(_make_app(status=200))
        scope = _make_scope(method="GET", path="/health")

        with caplog.at_level(logging.INFO, logger="app.access"):
            await middleware(scope, AsyncMock(), AsyncMock())

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert "GET" in record.message
        assert "/health" in record.message
        assert "200" in record.message

    @pytest.mark.asyncio
    async def test_logs_latency(self, caplog):
        """Middleware log record includes latency in milliseconds."""
        middleware = RequestLoggingMiddleware(_make_app(status=201))
        scope = _make_scope(method="POST", path="/api/molecules")

        with caplog.at_level(logging.INFO, logger="app.access"):
            await middleware(scope, AsyncMock(), AsyncMock())

        assert caplog.records[0].message.endswith("ms")

    @pytest.mark.asyncio
    async def test_sanitizes_token_in_query(self, caplog):
        """Sensitive query params are redacted in log output."""
        middleware = RequestLoggingMiddleware(_make_app())
        scope = _make_scope(path="/api/runs", query_string=b"token=secret123")

        with caplog.at_level(logging.INFO, logger="app.access"):
            await middleware(scope, AsyncMock(), AsyncMock())

        log_msg = caplog.records[0].message
        assert "token=***" in log_msg
        assert "secret123" not in log_msg

    @pytest.mark.asyncio
    async def test_sanitizes_password_in_query(self, caplog):
        """password query param value is redacted in log output."""
        middleware = RequestLoggingMiddleware(_make_app())
        sensitive_key = "password"
        raw_value = "dummy-secret-value"
        scope = _make_scope(
            path="/api/auth",
            query_string=f"{sensitive_key}={raw_value}".encode(),
        )

        with caplog.at_level(logging.INFO, logger="app.access"):
            await middleware(scope, AsyncMock(), AsyncMock())

        log_msg = caplog.records[0].message
        assert f"{sensitive_key}=***" in log_msg
        assert raw_value not in log_msg

    @pytest.mark.asyncio
    async def test_non_sensitive_params_not_redacted(self, caplog):
        """Non-sensitive query params are logged as-is."""
        middleware = RequestLoggingMiddleware(_make_app())
        scope = _make_scope(path="/api/molecules", query_string=b"q=H2&limit=10")

        with caplog.at_level(logging.INFO, logger="app.access"):
            await middleware(scope, AsyncMock(), AsyncMock())

        log_msg = caplog.records[0].message
        assert "q=H2" in log_msg
        assert "limit=10" in log_msg

    @pytest.mark.asyncio
    async def test_non_http_scope_passes_through_without_logging(self, caplog):
        """Lifespan and WebSocket scopes are forwarded without any log entry."""
        inner = AsyncMock()
        middleware = RequestLoggingMiddleware(inner)
        scope = _make_scope(scope_type="lifespan")

        with caplog.at_level(logging.DEBUG, logger="app.access"):
            await middleware(scope, AsyncMock(), AsyncMock())

        assert caplog.records == []
        inner.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_logs_on_exception_from_inner_app(self, caplog):
        """Log is still emitted (with 500) even if inner app raises."""

        async def failing_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 500, "headers": []})
            raise RuntimeError("boom")

        middleware = RequestLoggingMiddleware(failing_app)
        scope = _make_scope(path="/api/runs")

        with caplog.at_level(logging.INFO, logger="app.access"):
            with pytest.raises(RuntimeError):
                await middleware(scope, AsyncMock(), AsyncMock())

        assert len(caplog.records) == 1
        assert "500" in caplog.records[0].message

    @pytest.mark.asyncio
    async def test_logs_default_500_when_exception_before_response_start(self, caplog):
        """Status defaults to 500 when the inner app raises before sending any response."""

        async def no_response_app(scope, receive, send):
            raise RuntimeError("early crash")

        middleware = RequestLoggingMiddleware(no_response_app)
        scope = _make_scope(path="/api/runs")

        with caplog.at_level(logging.INFO, logger="app.access"):
            with pytest.raises(RuntimeError):
                await middleware(scope, AsyncMock(), AsyncMock())

        assert len(caplog.records) == 1
        assert "500" in caplog.records[0].message

    @pytest.mark.asyncio
    async def test_invalid_utf8_in_query_string_does_not_crash(self, caplog):
        """Middleware handles invalid UTF-8 bytes in query string without raising."""
        middleware = RequestLoggingMiddleware(_make_app())
        scope = _make_scope(path="/api/runs", query_string=b"q=\xff\xfe")

        with caplog.at_level(logging.INFO, logger="app.access"):
            await middleware(scope, AsyncMock(), AsyncMock())

        assert len(caplog.records) == 1
        assert "GET" in caplog.records[0].message
