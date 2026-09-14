"""Runtime backend discovery endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.dependencies import get_db, require_local_operator_access
from app.schemas.backend import (
    BackendListResponse,
    BackendResolveRequest,
    BackendResolveResponse,
    TranspilePreviewRequest,
    TranspilePreviewResponse,
)
from app.services.backend_runtime import list_backends, resolve_backend, transpile_preview
from app.services.credential_profiles import IbmCredentialProfileService

router = APIRouter(dependencies=[Depends(require_local_operator_access)])


def _list_backends_for_request(
    db: Session,
    credential_profile_id: UUID | None,
) -> BackendListResponse:
    credentials = IbmCredentialProfileService(db).resolve_credentials(credential_profile_id)
    return list_backends(ibm_credentials=credentials, allow_background_refresh=True)


def _resolve_runtime_backend_for_request(
    db: Session,
    request: BackendResolveRequest,
) -> BackendResolveResponse:
    credentials = IbmCredentialProfileService(db).resolve_credentials(
        request.backend_options.credential_profile_id
    )
    return resolve_backend(request, ibm_credentials=credentials)


def _preview_transpile_for_request(
    db: Session,
    request: TranspilePreviewRequest,
) -> TranspilePreviewResponse:
    credentials = IbmCredentialProfileService(db).resolve_credentials(
        request.backend_options.credential_profile_id
    )
    return transpile_preview(request, ibm_credentials=credentials)


@router.get("")
async def get_backends(
    db: Annotated[Session, Depends(get_db)],
    credential_profile_id: Annotated[
        UUID | None,
        Query(
            description="IBM profile to use for hardware discovery; active profile is used when omitted."
        ),
    ] = None,
) -> BackendListResponse:
    """List local and configured runtime backends."""
    return await run_in_threadpool(_list_backends_for_request, db, credential_profile_id)


@router.post("/resolve")
async def resolve_runtime_backend(
    request: BackendResolveRequest,
    db: Annotated[Session, Depends(get_db)],
) -> BackendResolveResponse:
    """Resolve a backend target and selection policy to a concrete backend."""
    return await run_in_threadpool(_resolve_runtime_backend_for_request, db, request)


@router.post("/transpile-preview")
async def preview_transpile(
    request: TranspilePreviewRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TranspilePreviewResponse:
    """Return best-effort transpile metadata for the requested backend."""
    return await run_in_threadpool(_preview_transpile_for_request, db, request)
