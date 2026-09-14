"""Helpers for securely storing local secret files."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path


class LocalSecretFileError(RuntimeError):
    """Raised when a local secret file cannot be used safely."""


def read_or_create_secret_file(
    raw_path: str | Path,
    *,
    create_bytes: Callable[[], bytes],
    description: str,
) -> tuple[bytes, bool]:
    """Read a local secret file, creating it atomically with owner-only perms if needed."""

    path = Path(raw_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)

    generated = False
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        generated = True
        with os.fdopen(fd, "wb") as handle:
            handle.write(create_bytes())

    if path.is_symlink():
        raise LocalSecretFileError(f"{description} path must not be a symlink: {path}")
    if not path.is_file():
        raise LocalSecretFileError(f"{description} path is not a regular file: {path}")

    try:
        mode = path.stat().st_mode & 0o777
    except OSError as exc:
        raise LocalSecretFileError(f"Unable to inspect {description} permissions: {path}") from exc
    if mode & 0o077:
        try:
            path.chmod(0o600)
            mode = path.stat().st_mode & 0o777
        except OSError as exc:
            raise LocalSecretFileError(
                f"{description} must be readable only by its owner: {path}"
            ) from exc
        if mode & 0o077:
            raise LocalSecretFileError(f"{description} must use 0600 permissions: {path}")

    try:
        value = path.read_bytes().strip()
    except OSError as exc:
        raise LocalSecretFileError(f"Unable to read {description}: {path}") from exc
    if not value:
        raise LocalSecretFileError(f"{description} file is empty: {path}")
    return value, generated
