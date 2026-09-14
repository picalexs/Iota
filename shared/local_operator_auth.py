"""Helpers for protecting local operator-only actions."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass

from .local_secret_files import LocalSecretFileError, read_or_create_secret_file

_TOKEN_ENV = "LOCAL_OPERATOR_TOKEN"
_TOKEN_FILE_ENV = "LOCAL_OPERATOR_TOKEN_FILE"
_DEFAULT_TOKEN_FILE = ".local/operator-access.token"
_HEADER_NAME = "X-Local-Operator-Token"


@dataclass(frozen=True)
class LocalOperatorAuthStatus:
    """Non-secret diagnostics about the local operator token source."""

    token_source: str
    generated_token_file: bool = False
    warning: str | None = None


class LocalOperatorAuthError(RuntimeError):
    """Raised when local operator authentication cannot be configured safely."""


@dataclass(frozen=True)
class LocalOperatorAuth:
    """Resolved local operator token and non-secret diagnostics."""

    token: str
    status: LocalOperatorAuthStatus


def get_local_operator_auth() -> LocalOperatorAuth:
    """Resolve the local operator token from env or an owner-only local file."""

    token = os.getenv(_TOKEN_ENV, "").strip()
    if token:
        return LocalOperatorAuth(
            token=token,
            status=LocalOperatorAuthStatus(token_source=_TOKEN_ENV),
        )

    path = os.getenv(_TOKEN_FILE_ENV, _DEFAULT_TOKEN_FILE)
    try:
        token_bytes, generated = read_or_create_secret_file(
            path,
            create_bytes=lambda: secrets.token_urlsafe(32).encode("utf-8"),
            description="Local operator token file",
        )
    except LocalSecretFileError as exc:
        raise LocalOperatorAuthError("Unable to initialize the local operator token") from exc

    warning = None
    if generated:
        warning = (
            "A local operator access token was generated. Keep this ignored file; "
            "IBM profile management and IBM submissions require it."
        )
    return LocalOperatorAuth(
        token=token_bytes.decode("utf-8"),
        status=LocalOperatorAuthStatus(
            token_source=str(path),
            generated_token_file=generated,
            warning=warning,
        ),
    )


def get_local_operator_header_name() -> str:
    """Return the HTTP header name used for operator-only access."""

    return _HEADER_NAME
