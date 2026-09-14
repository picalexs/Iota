"""Unit coverage for local secret-file helpers used by IBM credential protection."""

from __future__ import annotations

from pathlib import Path

from shared.local_operator_auth import get_local_operator_auth
from shared.local_secret_files import read_or_create_secret_file


def test_read_or_create_secret_file_creates_owner_only_file(tmp_path: Path) -> None:
    path = tmp_path / "secret.txt"

    value, generated = read_or_create_secret_file(
        path,
        create_bytes=lambda: b"secret-value\n",
        description="test secret",
    )

    assert generated is True
    assert value == b"secret-value"
    assert path.exists()
    assert path.stat().st_mode & 0o777 == 0o600


def test_read_or_create_secret_file_tightens_existing_permissions(tmp_path: Path) -> None:
    path = tmp_path / "secret.txt"
    path.write_text("existing-value\n", encoding="utf-8")
    path.chmod(0o644)

    value, generated = read_or_create_secret_file(
        path,
        create_bytes=lambda: b"new-value\n",
        description="test secret",
    )

    assert generated is False
    assert value == b"existing-value"
    assert path.stat().st_mode & 0o777 == 0o600


def test_local_operator_auth_prefers_env_token(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LOCAL_OPERATOR_TOKEN", "env-token")
    monkeypatch.setenv("LOCAL_OPERATOR_TOKEN_FILE", str(tmp_path / "operator.token"))

    auth = get_local_operator_auth()

    assert auth.token == "env-token"
    assert auth.status.token_source == "LOCAL_OPERATOR_TOKEN"
