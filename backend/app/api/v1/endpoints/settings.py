"""Local settings and IBM credential profile endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.dependencies import get_db, require_local_operator_access
from app.schemas.settings import (
    IbmCredentialProfileCreate,
    IbmCredentialProfileListResponse,
    IbmCredentialProfileResponse,
    IbmCredentialProfileTestResponse,
    IbmCredentialProfileUpdate,
)
from app.services.credential_profiles import IbmCredentialProfileService

router = APIRouter(dependencies=[Depends(require_local_operator_access)])


def _list_ibm_profiles_for_request(
    db: Session,
) -> IbmCredentialProfileListResponse:
    return IbmCredentialProfileService(db).list_profiles()


def _create_ibm_profile_for_request(
    db: Session,
    payload: IbmCredentialProfileCreate,
) -> IbmCredentialProfileResponse:
    profile = IbmCredentialProfileService(db).create(payload)
    return IbmCredentialProfileResponse.model_validate(profile)


def _update_ibm_profile_for_request(
    db: Session,
    profile_id: UUID,
    payload: IbmCredentialProfileUpdate,
) -> IbmCredentialProfileResponse:
    profile = IbmCredentialProfileService(db).update(profile_id, payload)
    return IbmCredentialProfileResponse.model_validate(profile)


def _activate_ibm_profile_for_request(
    db: Session,
    profile_id: UUID,
) -> IbmCredentialProfileResponse:
    profile = IbmCredentialProfileService(db).activate(profile_id)
    return IbmCredentialProfileResponse.model_validate(profile)


def _test_ibm_profile_for_request(
    db: Session,
    profile_id: UUID,
) -> IbmCredentialProfileTestResponse:
    return IbmCredentialProfileService(db).test_profile(profile_id)


def _delete_ibm_profile_for_request(
    db: Session,
    profile_id: UUID,
    confirm_name: str,
) -> None:
    IbmCredentialProfileService(db).delete(profile_id, confirm_name=confirm_name)


@router.get("/ibm-profiles")
async def list_ibm_profiles(
    db: Annotated[Session, Depends(get_db)],
) -> IbmCredentialProfileListResponse:
    """List encrypted local IBM Runtime profiles without exposing secrets."""
    return await run_in_threadpool(_list_ibm_profiles_for_request, db)


@router.post(
    "/ibm-profiles",
    status_code=status.HTTP_201_CREATED,
)
async def create_ibm_profile(
    payload: IbmCredentialProfileCreate,
    db: Annotated[Session, Depends(get_db)],
) -> IbmCredentialProfileResponse:
    """Create an encrypted IBM Runtime credential profile."""
    return await run_in_threadpool(_create_ibm_profile_for_request, db, payload)


@router.patch("/ibm-profiles/{profile_id}")
async def update_ibm_profile(
    profile_id: UUID,
    payload: IbmCredentialProfileUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> IbmCredentialProfileResponse:
    """Update profile name, active state, channel, or saved credentials."""
    return await run_in_threadpool(_update_ibm_profile_for_request, db, profile_id, payload)


@router.post("/ibm-profiles/{profile_id}/activate")
async def activate_ibm_profile(
    profile_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> IbmCredentialProfileResponse:
    """Make one IBM profile the active profile for new Runtime runs."""
    return await run_in_threadpool(_activate_ibm_profile_for_request, db, profile_id)


@router.post("/ibm-profiles/{profile_id}/test")
async def test_ibm_profile(
    profile_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> IbmCredentialProfileTestResponse:
    """Test a saved IBM Runtime profile by decrypting it locally."""
    return await run_in_threadpool(_test_ibm_profile_for_request, db, profile_id)


@router.delete("/ibm-profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ibm_profile(
    profile_id: UUID,
    confirm_name: Annotated[str, Query(min_length=1)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Delete an IBM profile after the caller confirms its exact display name."""
    await run_in_threadpool(_delete_ibm_profile_for_request, db, profile_id, confirm_name)
