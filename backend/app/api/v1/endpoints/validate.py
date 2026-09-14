"""
Config validation endpoint.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.dependencies import (
    ensure_local_operator_access,
    get_db,
    run_requires_local_operator_access,
)
from app.schemas.run_requests import RunValidationRequest
from app.schemas.run_responses import RunValidationResponse
from app.services.validation_service import validate_run_validation_request

router = APIRouter()


def _validate_config_for_request(
    db: Session,
    payload: RunValidationRequest,
) -> RunValidationResponse:
    return validate_run_validation_request(db, payload)


@router.post("/config")
async def validate_config(
    payload: RunValidationRequest,
    db: Annotated[Session, Depends(get_db)],
    http_request: Request,
) -> RunValidationResponse:
    """Validate an algorithm-aware run request before submission."""
    if run_requires_local_operator_access(payload.run):
        ensure_local_operator_access(http_request)
    return await run_in_threadpool(_validate_config_for_request, db, payload)
