"""Shared local encryption helpers for IBM credential profiles."""

from __future__ import annotations

import os
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from .local_secret_files import LocalSecretFileError, read_or_create_secret_file

_KEYS_ENV = "LOCAL_CREDENTIALS_KEYS"
_KEY_FILE_ENV = "LOCAL_CREDENTIALS_KEY_FILE"
_DEFAULT_KEY_FILE = ".local/credential-fernet.key"


@dataclass(frozen=True)
class CredentialCipherStatus:
    """Non-secret status shown in settings diagnostics."""

    key_source: str
    generated_key_file: bool = False
    warning: str | None = None


class CredentialCipherError(RuntimeError):
    """Raised when credential encryption/decryption cannot proceed."""


class CredentialCipher:
    """Fernet/MultiFernet wrapper used by API and worker processes."""

    def __init__(self, fernet: MultiFernet, status: CredentialCipherStatus) -> None:
        self._fernet = fernet
        self.status = status

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt(self, value: str) -> str:
        try:
            return self._fernet.decrypt(value.encode("ascii")).decode("utf-8")
        except (InvalidToken, UnicodeError) as exc:
            raise CredentialCipherError("Unable to decrypt IBM credential profile") from exc

    def rotate(self, value: str) -> str:
        try:
            return self._fernet.rotate(value.encode("ascii")).decode("ascii")
        except (InvalidToken, UnicodeError) as exc:
            raise CredentialCipherError("Unable to rotate IBM credential profile") from exc


def get_credential_cipher() -> CredentialCipher:
    """Return a configured cipher, generating an ignored local key if needed."""

    keys_raw = os.getenv(_KEYS_ENV, "").strip()
    if keys_raw:
        keys = [key.strip() for key in keys_raw.split(",") if key.strip()]
        if not keys:
            raise CredentialCipherError(f"{_KEYS_ENV} did not contain any Fernet keys")
        try:
            return CredentialCipher(
                MultiFernet([Fernet(key.encode("ascii")) for key in keys]),
                CredentialCipherStatus(key_source=_KEYS_ENV),
            )
        except (TypeError, ValueError) as exc:
            raise CredentialCipherError(f"{_KEYS_ENV} contained an invalid Fernet key") from exc

    path = os.getenv(_KEY_FILE_ENV, _DEFAULT_KEY_FILE)
    try:
        key, generated = read_or_create_secret_file(
            path,
            create_bytes=Fernet.generate_key,
            description="Local IBM credential encryption key",
        )
    except LocalSecretFileError as exc:
        raise CredentialCipherError(
            "Unable to initialize the local IBM credential key file"
        ) from exc

    warning = None
    if generated:
        warning = (
            "A local credential encryption key was generated. Keep this ignored file; "
            "saved IBM profiles cannot be decrypted if it is deleted."
        )

    return CredentialCipher(
        MultiFernet([Fernet(key)]),
        CredentialCipherStatus(
            key_source=str(path),
            generated_key_file=generated,
            warning=warning,
        ),
    )


def mask_secret(value: str, *, prefix: int = 4, suffix: int = 4) -> str:
    """Return a short non-secret hint for display."""

    cleaned = value.strip()
    if not cleaned:
        return ""
    if len(cleaned) <= prefix + suffix:
        return "*" * len(cleaned)
    return f"{cleaned[:prefix]}...{cleaned[-suffix:]}"
