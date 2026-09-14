"""Schemas for run event resources."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RunEventType
from app.schemas.common import BaseORMModel


class RunEventCreate(BaseModel):
    """Schema for creating a run event (internal — emitted by worker)."""

    model_config = ConfigDict(extra="forbid")

    run_id: UUID = Field(..., description="ID of the associated run")
    event_type: RunEventType = Field(..., description="Category of the event")
    sequence: int = Field(
        ..., ge=0, description="Monotonically increasing sequence number within the run"
    )
    payload: dict[str, Any] = Field(default_factory=dict, description="Arbitrary event data")


class RunEventResponse(BaseORMModel):
    """Schema for run event."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "run_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "sequence": 0,
                "type": "status_changed",
                "payload": {"old_status": "QUEUED", "new_status": "RUNNING"},
                "created_at": "2026-02-24T12:00:00Z",
            }
        },
    )

    id: int
    run_id: UUID
    sequence: int
    type: RunEventType
    payload: dict[str, Any]
    created_at: datetime


class RunEventListResponse(BaseModel):
    """Schema for run event list."""

    events: list[RunEventResponse]
    last_sequence: int
