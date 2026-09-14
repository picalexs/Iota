"""Worker-owned lookup boundary for encrypted IBM credential profiles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True, slots=True)
class EncryptedIbmCredentialProfile:
    """Encrypted profile values returned to the worker credential resolver."""

    encrypted_token: str
    encrypted_crn: str
    channel: str | None


@runtime_checkable
class IbmCredentialProfileRepository(Protocol):
    """Persistence operation required to resolve one saved IBM profile."""

    def get(self, profile_id: str) -> EncryptedIbmCredentialProfile | None:
        """Return one encrypted profile without decrypting or exposing its values."""


class SqlIbmCredentialProfileRepository:
    """SQLAlchemy Core implementation for encrypted IBM profile lookup."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, profile_id: str) -> EncryptedIbmCredentialProfile | None:
        row = self._session.execute(
            text(
                "SELECT encrypted_token, encrypted_crn, channel "
                "FROM ibm_credential_profiles WHERE id = :profile_id"
            ),
            {"profile_id": profile_id},
        ).fetchone()
        if row is None:
            return None
        return EncryptedIbmCredentialProfile(
            encrypted_token=str(row[0]),
            encrypted_crn=str(row[1]),
            channel=str(row[2]) if row[2] is not None else None,
        )


__all__ = [
    "EncryptedIbmCredentialProfile",
    "IbmCredentialProfileRepository",
    "SqlIbmCredentialProfileRepository",
]
