"""Settings and local credential profile schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import BaseORMModel


class IbmCredentialProfileCreate(BaseModel):
    """Create an encrypted IBM Runtime credential profile."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=255)
    token: str = Field(..., min_length=1)
    crn: str = Field(..., min_length=1)
    channel: str = Field("ibm_quantum_platform", min_length=1, max_length=64)
    activate: bool = True


class IbmCredentialProfileUpdate(BaseModel):
    """Update profile metadata and optionally replace encrypted credentials."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=255)
    token: str | None = Field(None, min_length=1)
    crn: str | None = Field(None, min_length=1)
    channel: str | None = Field(None, min_length=1, max_length=64)
    activate: bool | None = None


class IbmCredentialProfileResponse(BaseORMModel):
    """Safe profile response with non-secret metadata only."""

    id: UUID
    name: str
    channel: str
    active: bool
    created_at: datetime
    updated_at: datetime


class IbmCredentialProfileListResponse(BaseModel):
    """Profile list plus local encryption diagnostics."""

    profiles: list[IbmCredentialProfileResponse]
    active_profile_id: UUID | None = None
    encryption_key_source: str
    encryption_warning: str | None = None


class IbmCredentialProfileTestResponse(BaseModel):
    """Connectivity test response for a profile."""

    id: UUID
    ok: bool
    message: str
    active_instance: str | None = None


class IbmRuntimeCredentials(BaseModel):
    """Decrypted runtime credentials used internally by API/worker code."""

    profile_id: UUID
    profile_name: str | None = None
    token: str
    instance: str
    channel: str
