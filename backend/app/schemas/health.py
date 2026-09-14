"""
Pydantic schemas for health check responses.
"""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

HealthStatus = Literal["healthy", "degraded", "unhealthy"]
ComponentStatus = Literal["connected", "disconnected", "unknown"]
WorkerStatus = Literal["active", "inactive", "unknown"]
ApiStatus = Literal["ready"]


class StatusResponse(BaseModel):
    """
    System status response for the readiness probe.

    Reports actual connectivity to each backing service.
    HTTP 200 when all components are reachable; HTTP 503 otherwise.
    """

    api: ApiStatus = "ready"
    db: ComponentStatus
    redis: ComponentStatus


class HealthResponse(BaseModel):
    """
    Health check response.

    Provides status for the API and its dependencies.
    """

    status: HealthStatus
    postgres: ComponentStatus
    redis: ComponentStatus
    worker: WorkerStatus
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
