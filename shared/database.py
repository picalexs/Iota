"""Shared helpers for building local PostgreSQL connection URLs."""

from __future__ import annotations

from urllib.parse import quote


def build_postgres_url(
    *,
    host: str,
    port: int,
    database: str,
    user: str,
    password: str,
) -> str:
    """Build an encoded PostgreSQL URL from the local DB_* fallback fields.

    ``DATABASE_URL`` remains the preferred runtime setting. This helper exists
    only for the local Compose fallback shared by the API and worker.
    """
    if not all([host, database, user, password]):
        return ""

    encoded_user = quote(user, safe="")
    encoded_password = quote(password, safe="")
    return f"postgresql://{encoded_user}:{encoded_password}@{host}:{port}/{database}"
