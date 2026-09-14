"""
Request/response logging middleware.

Logs every HTTP request with method, path, sanitized query params,
response status code, and latency. Sensitive query parameters are
redacted before logging to prevent credential exposure.
"""

import logging
import time
import urllib.parse
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger("app.access")

# Query parameter keys whose values must never appear in logs.
SENSITIVE_PARAMS: frozenset[str] = frozenset(
    {
        "password",
        "token",
        "api_key",
        "secret",
        "authorization",
        "ibm_quantum_token",
        "access_token",
        "refresh_token",
    }
)

# Paths excluded from access logging (e.g. load-balancer health checks).
_SKIP_LOG_PATHS: frozenset[str] = frozenset()


def sanitize_query_string(query_string: str) -> str:
    """
    Replace the values of sensitive query parameters with '***'.

    Args:
        query_string: Raw URL query string (without leading '?').

    Returns:
        Sanitized query string with sensitive values redacted.
    """
    if not query_string:
        return ""

    parts: list[str] = []
    for part in query_string.split("&"):
        if "=" in part:
            key, _, _ = part.partition("=")
            decoded_key = urllib.parse.unquote_plus(key).lower()
            # Match on the base name so array-style keys like "token[0]" are
            # treated as sensitive when "token" is listed in SENSITIVE_PARAMS.
            base_key = decoded_key.split("[", 1)[0]
            if base_key in SENSITIVE_PARAMS:
                parts.append(f"{key}=***")
            else:
                parts.append(part)
        else:
            parts.append(part)

    return "&".join(parts)


class RequestLoggingMiddleware:
    """
    Raw ASGI middleware that logs each HTTP request.

    Uses raw ASGI (not BaseHTTPMiddleware) so it does not buffer response
    bodies, preserving compatibility with SSE streaming endpoints.

    Logged format:
        METHOD /path?query STATUS - latencyms
    """

    def __init__(self, app: Callable[..., Awaitable[Any]]) -> None:
        self.app = app

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[..., Awaitable[Any]],
        send: Callable[..., Awaitable[Any]],
    ) -> None:
        """Process an ASGI request, logging HTTP requests."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method: str = scope.get("method", "")
        path: str = scope.get("path", "")
        raw_query: str = scope.get("query_string", b"").decode("utf-8", errors="replace")
        query = sanitize_query_string(raw_query)
        path_with_query = f"{path}?{query}" if query else path

        if path in _SKIP_LOG_PATHS:
            await self.app(scope, receive, send)
            return

        status_code: int = 500
        start = time.perf_counter()

        async def send_wrapper(message: dict[str, Any]) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "%s %s %d - %.0fms",
                method,
                path_with_query,
                status_code,
                elapsed_ms,
            )
