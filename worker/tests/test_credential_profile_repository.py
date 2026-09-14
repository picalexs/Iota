"""Tests for the worker IBM credential-profile persistence boundary."""

from __future__ import annotations

from unittest.mock import MagicMock

from worker.jobs._credential_profiles import inject_profile_credentials
from worker.persistence.credential_profile_repository import (
    EncryptedIbmCredentialProfile,
    SqlIbmCredentialProfileRepository,
)


def test_profile_repository_maps_encrypted_row_without_decrypting() -> None:
    session = MagicMock()
    session.execute.return_value.fetchone.return_value = (
        "encrypted-token",
        "encrypted-crn",
        "ibm_quantum_platform",
    )

    profile = SqlIbmCredentialProfileRepository(session).get("profile-123")

    assert profile == EncryptedIbmCredentialProfile(
        encrypted_token="encrypted-token",
        encrypted_crn="encrypted-crn",
        channel="ibm_quantum_platform",
    )
    sql, params = session.execute.call_args.args
    assert "SELECT encrypted_token, encrypted_crn, channel" in str(sql)
    assert "FROM ibm_credential_profiles" in str(sql)
    assert params == {"profile_id": "profile-123"}


def test_profile_repository_returns_none_for_missing_profile() -> None:
    session = MagicMock()
    session.execute.return_value.fetchone.return_value = None

    assert SqlIbmCredentialProfileRepository(session).get("missing") is None


def test_resolver_decrypts_only_values_returned_by_repository(monkeypatch) -> None:
    session = MagicMock()
    session.execute.return_value.fetchone.return_value = (
        "encrypted-token",
        "encrypted-crn",
        None,
    )
    cipher = MagicMock()
    cipher.decrypt.side_effect = ["token", "crn"]
    monkeypatch.setattr("worker.jobs._credential_profiles.get_credential_cipher", lambda: cipher)

    options = inject_profile_credentials(
        session,
        {"credential_profile_id": "profile-123", "backend_name": "ibm_brisbane"},
    )

    assert options == {
        "credential_profile_id": "profile-123",
        "backend_name": "ibm_brisbane",
        "token": "token",
        "instance": "crn",
        "channel": "ibm_quantum_platform",
    }
    assert cipher.decrypt.call_args_list[0].args == ("encrypted-token",)
    assert cipher.decrypt.call_args_list[1].args == ("encrypted-crn",)


def test_resolver_preserves_options_without_a_profile() -> None:
    session = MagicMock()
    options = {"backend_name": "aer_simulator"}

    assert inject_profile_credentials(session, options) is options
    session.execute.assert_not_called()
