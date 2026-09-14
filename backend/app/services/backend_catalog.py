"""Local backend catalog summaries."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.config import Settings, get_settings
from app.models.enums import BackendTarget
from app.schemas.backend import BackendListResponse, BackendSummary
from app.schemas.settings import IbmRuntimeCredentials
from app.services.ibm_backend_discovery import discover_ibm_backends_cached


def list_backends(
    *,
    settings: Settings | None = None,
    ibm_credentials: IbmRuntimeCredentials | None = None,
    ibm_service_factory: Callable[[Settings], Any] | None = None,
    allow_background_refresh: bool = False,
) -> BackendListResponse:
    """Return local backend summaries plus credential-aware IBM Runtime metadata."""
    active_settings = settings or get_settings()
    warnings: list[str] = []
    backends = local_backend_summaries(active_settings)

    ibm_summaries, ibm_warnings = discover_ibm_backends_cached(
        active_settings,
        ibm_credentials=ibm_credentials,
        ibm_service_factory=ibm_service_factory,
        allow_background_refresh=allow_background_refresh,
    )
    backends.extend(ibm_summaries)
    warnings.extend(ibm_warnings)
    return BackendListResponse(backends=backends, warnings=warnings)


def local_backend_summaries(settings: Settings) -> list[BackendSummary]:
    """Build the deterministic local simulator entries for the backend catalog."""
    capabilities = settings.backend_capabilities
    return [
        BackendSummary(
            target=BackendTarget.STATEVECTOR,
            name="statevector",
            display_name="Statevector simulator",
            available=capabilities[BackendTarget.STATEVECTOR].enabled,
            credential_configured=None,
            credentials_usable=None,
            simulator=True,
            supports_noise_profile=False,
            supports_transpile_preview=False,
            status_message="Exact statevector simulation; noise profiles are not supported.",
        ),
        BackendSummary(
            target=BackendTarget.AER_SIMULATOR,
            name="aer_simulator",
            display_name="Aer simulator",
            available=capabilities[BackendTarget.AER_SIMULATOR].enabled,
            credential_configured=None,
            credentials_usable=None,
            simulator=True,
            supports_noise_profile=True,
            supports_transpile_preview=True,
            pending_jobs=0,
            error_rate=0.0,
            status_message=(
                "Local Aer simulator contract; defaults are ideal/noiseless "
                "unless noise_profile is provided."
            ),
        ),
    ]
