"""Service layer for encrypted IBM credential profiles."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from queue import Empty, Queue
from threading import Thread
from typing import Any, Callable, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.models import IbmCredentialProfile
from app.schemas.settings import (
    IbmCredentialProfileCreate,
    IbmCredentialProfileListResponse,
    IbmCredentialProfileResponse,
    IbmCredentialProfileTestResponse,
    IbmCredentialProfileUpdate,
    IbmRuntimeCredentials,
)
from shared.credential_crypto import CredentialCipherError, get_credential_cipher

logger = logging.getLogger(__name__)
_IBM_PROFILE_VALIDATION_TIMEOUT_SECONDS = 5.0
_IBM_PROFILE_VALIDATION_TIMEOUT_MESSAGE = "IBM Runtime validation timed out. Check IBM Quantum access or network connectivity and try again."


@dataclass(frozen=True)
class ProfileCredentialPayload:
    """Plain credential payload scoped to an internal runtime operation."""

    profile_id: UUID
    token: str
    instance: str
    channel: str


class IbmCredentialProfileService:
    """CRUD and decryption operations for IBM credential profiles."""

    def __init__(self, db: Session):
        self.db = db

    def list_profiles(self) -> IbmCredentialProfileListResponse:
        cipher_status = get_credential_cipher().status
        profiles = list(
            self.db.scalars(select(IbmCredentialProfile).order_by(IbmCredentialProfile.name)).all()
        )
        self._rewrap_profiles_if_needed(profiles)
        active = next((profile.id for profile in profiles if profile.active), None)
        return IbmCredentialProfileListResponse(
            profiles=[IbmCredentialProfileResponse.model_validate(profile) for profile in profiles],
            active_profile_id=active,
            encryption_key_source=cipher_status.key_source,
            encryption_warning=cipher_status.warning,
        )

    def create(self, payload: IbmCredentialProfileCreate) -> IbmCredentialProfile:
        name = payload.name.strip()
        existing = self.db.scalars(
            select(IbmCredentialProfile).where(
                func.lower(IbmCredentialProfile.name) == name.lower()
            )
        ).first()
        if existing:
            raise ConflictError(f"IBM credential profile '{name}' already exists")

        cipher = get_credential_cipher()
        profile = IbmCredentialProfile(
            name=name,
            encrypted_token=cipher.encrypt(payload.token.strip()),
            encrypted_crn=cipher.encrypt(payload.crn.strip()),
            channel=payload.channel.strip(),
            active=False,
            token_hint=None,
            crn_hint=None,
        )
        self.db.add(profile)
        self.db.flush()
        if payload.activate or not self._active_profile_exists():
            self._activate_profile(profile)
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def update(
        self,
        profile_id: UUID,
        payload: IbmCredentialProfileUpdate,
    ) -> IbmCredentialProfile:
        profile = self.get(profile_id)
        if payload.name is not None:
            next_name = payload.name.strip()
            conflict = self.db.scalars(
                select(IbmCredentialProfile).where(
                    func.lower(IbmCredentialProfile.name) == next_name.lower(),
                    IbmCredentialProfile.id != profile_id,
                )
            ).first()
            if conflict:
                raise ConflictError(f"IBM credential profile '{next_name}' already exists")
            profile.name = next_name

        cipher = get_credential_cipher()
        if payload.token is not None:
            token = payload.token.strip()
            profile.encrypted_token = cipher.encrypt(token)
            profile.token_hint = None
        if payload.crn is not None:
            crn = payload.crn.strip()
            profile.encrypted_crn = cipher.encrypt(crn)
            profile.crn_hint = None
        if payload.channel is not None:
            profile.channel = payload.channel.strip()
        if payload.activate is True:
            self._activate_profile(profile)
        elif payload.activate is False and profile.active:
            profile.active = False

        self.db.commit()
        self.db.refresh(profile)
        return profile

    def delete(self, profile_id: UUID, *, confirm_name: str) -> None:
        profile = self.get(profile_id)
        if profile.name != confirm_name:
            raise ValidationError(
                "Profile deletion confirmation did not match", field="confirm_name"
            )
        was_active = profile.active
        self.db.delete(profile)
        self.db.flush()
        if was_active:
            replacement = self.db.scalars(
                select(IbmCredentialProfile).order_by(IbmCredentialProfile.created_at.desc())
            ).first()
            if replacement is not None:
                self._activate_profile(replacement)
        self.db.commit()

    def activate(self, profile_id: UUID) -> IbmCredentialProfile:
        profile = self.get(profile_id)
        self._activate_profile(profile)
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def get(self, profile_id: UUID) -> IbmCredentialProfile:
        profile = self.db.get(IbmCredentialProfile, profile_id)
        if profile is None:
            raise NotFoundError(f"IBM credential profile {profile_id} not found")
        return profile

    def resolve_credentials(self, profile_id: UUID | None = None) -> IbmRuntimeCredentials | None:
        profile = self._resolve_profile(profile_id)
        if profile is None:
            return None
        cipher = get_credential_cipher()
        try:
            token = cipher.decrypt(profile.encrypted_token)
            instance = cipher.decrypt(profile.encrypted_crn)
        except CredentialCipherError as exc:
            raise ValidationError(
                "Saved IBM credentials could not be decrypted. Check the local credentials key.",
                field="credential_profile_id",
            ) from exc
        return IbmRuntimeCredentials(
            profile_id=profile.id,
            profile_name=profile.name,
            token=token,
            instance=instance,
            channel=profile.channel,
        )

    def test_profile(
        self,
        profile_id: UUID,
        *,
        runtime_service_factory: Callable[[IbmRuntimeCredentials], Any] | None = None,
        validation_timeout_seconds: float | None = None,
    ) -> IbmCredentialProfileTestResponse:
        credentials = self.resolve_credentials(profile_id)
        if credentials is None:
            raise NotFoundError(f"IBM credential profile {profile_id} not found")
        if not credentials.token.strip() or not credentials.instance.strip():
            return IbmCredentialProfileTestResponse(
                id=profile_id,
                ok=False,
                message="IBM Runtime credential profile is missing required credential material.",
            )
        try:
            backend = _validate_runtime_credentials(
                credentials,
                runtime_service_factory=runtime_service_factory,
                timeout_seconds=(
                    _IBM_PROFILE_VALIDATION_TIMEOUT_SECONDS
                    if validation_timeout_seconds is None
                    else validation_timeout_seconds
                ),
            )
        except ModuleNotFoundError:
            return IbmCredentialProfileTestResponse(
                id=profile_id,
                ok=False,
                message="qiskit-ibm-runtime is not installed; IBM Runtime validation is unavailable.",
            )
        except TimeoutError:
            logger.info("IBM Runtime profile validation timed out for profile %s", profile_id)
            return IbmCredentialProfileTestResponse(
                id=profile_id,
                ok=False,
                message=_IBM_PROFILE_VALIDATION_TIMEOUT_MESSAGE,
            )
        except Exception:
            return IbmCredentialProfileTestResponse(
                id=profile_id,
                ok=False,
                message=(
                    "IBM Runtime validation failed. Check the saved token, instance, "
                    "channel, and network access."
                ),
            )
        backend_name = _backend_name(backend)
        return IbmCredentialProfileTestResponse(
            id=profile_id,
            ok=True,
            message=f"IBM Runtime credentials validated successfully using backend {backend_name}.",
            active_instance=None,
        )

    def _resolve_profile(self, profile_id: UUID | None) -> IbmCredentialProfile | None:
        if profile_id is not None:
            return self.get(profile_id)
        return self.db.scalars(
            select(IbmCredentialProfile).where(IbmCredentialProfile.active.is_(True))
        ).first()

    def _active_profile_exists(self) -> bool:
        return (
            self.db.scalars(
                select(IbmCredentialProfile.id).where(IbmCredentialProfile.active.is_(True))
            ).first()
            is not None
        )

    def _activate_profile(self, profile: IbmCredentialProfile) -> None:
        self.db.query(IbmCredentialProfile).update({IbmCredentialProfile.active: False})
        profile.active = True

    def _rewrap_profiles_if_needed(self, profiles: list[IbmCredentialProfile]) -> None:
        cipher = get_credential_cipher()
        changed = False
        for profile in profiles:
            rotated_token = cipher.rotate(profile.encrypted_token)
            rotated_instance = cipher.rotate(profile.encrypted_crn)
            if rotated_token != profile.encrypted_token:
                profile.encrypted_token = rotated_token
                changed = True
            if rotated_instance != profile.encrypted_crn:
                profile.encrypted_crn = rotated_instance
                changed = True
            if profile.token_hint is not None:
                profile.token_hint = None
                changed = True
            if profile.crn_hint is not None:
                profile.crn_hint = None
                changed = True
        if changed:
            self.db.commit()


def _build_runtime_service(credentials: IbmRuntimeCredentials) -> Any:
    from qiskit_ibm_runtime import QiskitRuntimeService

    return QiskitRuntimeService(
        channel=cast(Any, credentials.channel),
        token=credentials.token,
        instance=credentials.instance,
    )


def _validate_runtime_credentials(
    credentials: IbmRuntimeCredentials,
    *,
    runtime_service_factory: Callable[[IbmRuntimeCredentials], Any] | None,
    timeout_seconds: float,
) -> Any:
    results: Queue[tuple[str, Any]] = Queue(maxsize=1)

    def validate() -> None:
        try:
            service = (
                runtime_service_factory(credentials)
                if runtime_service_factory
                else _build_runtime_service(credentials)
            )
            results.put(("ok", service.least_busy(operational=True, simulator=False)))
        except Exception as exc:  # pragma: no cover - surfaced by caller/tests
            results.put(("error", exc))

    Thread(target=validate, name="ibm-profile-validation", daemon=True).start()
    try:
        kind, value = results.get(timeout=max(0.001, timeout_seconds))
    except Empty as exc:
        raise TimeoutError from exc

    if kind == "error":
        raise value
    return value


def _backend_name(backend: Any) -> str:
    name = getattr(backend, "name", None)
    if callable(name):
        resolved = name()
        return str(resolved) if resolved else "least_busy"
    if name is not None:
        return str(name)
    return str(backend or "least_busy")
