"""Worker-side IBM credential profile resolver."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from shared.credential_crypto import get_credential_cipher
from worker.persistence.credential_profile_repository import (
    SqlIbmCredentialProfileRepository,
)


def inject_profile_credentials(
    session: Session,
    backend_options: dict[str, Any],
) -> dict[str, Any]:
    """Return backend options with decrypted IBM credentials added for runtime only."""
    profile_id = backend_options.get("credential_profile_id")
    if not profile_id:
        return backend_options

    profile = SqlIbmCredentialProfileRepository(session).get(str(profile_id))
    if profile is None:
        return backend_options

    cipher = get_credential_cipher()
    next_options = dict(backend_options)
    next_options["token"] = cipher.decrypt(profile.encrypted_token)
    next_options["instance"] = cipher.decrypt(profile.encrypted_crn)
    next_options["channel"] = profile.channel or "ibm_quantum_platform"
    return next_options
