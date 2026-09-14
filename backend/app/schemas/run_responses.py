"""Pydantic response schemas for run resources."""

from __future__ import annotations

import math
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError, field_validator

from app.models.enums import BackendTarget, RunAlgorithm, RunMode, RunStatus
from app.schemas.common import BaseORMModel
from app.schemas.molecule import MoleculeResponse
from app.schemas.run_events import RunEventResponse
from app.schemas.run_results import RunResultResponse

DEFAULT_CHEMICAL_ACCURACY_HA = 1.6e-3


def resolve_chemical_accuracy_target_ha(config_json: Any) -> float:
    if isinstance(config_json, dict):
        threshold = config_json.get("chemical_accuracy_target_ha")
        if isinstance(threshold, (int, float)) and math.isfinite(float(threshold)):
            resolved = float(threshold)
            if resolved > 0:
                return resolved
    return DEFAULT_CHEMICAL_ACCURACY_HA


def resolve_run_chemical_accurate(run: Any) -> bool | None:
    result = getattr(run, "result", None)
    if result is None:
        return None

    signed_error = getattr(result, "signed_error", None)
    reference_energy = getattr(result, "reference_energy", None)
    if not isinstance(signed_error, (int, float)) or not math.isfinite(float(signed_error)):
        return None
    if not isinstance(reference_energy, (int, float)) or not math.isfinite(float(reference_energy)):
        return None

    threshold = resolve_chemical_accuracy_target_ha(getattr(run, "config_json", {}) or {})
    return abs(float(signed_error)) <= abs(threshold)


class RunEstimate(BaseModel):
    """Typed runtime estimate snapshot used by API responses and telemetry events."""

    source: str
    algorithm: str
    estimated_total_iterations: int | None = Field(None, ge=0)
    estimated_remaining_iterations: int | None = Field(None, ge=0)
    estimated_total_seconds: float | None = Field(None, ge=0.0)
    estimated_remaining_seconds: float | None = Field(None, ge=0.0)
    estimated_primary_iterations: int | None = Field(None, ge=0)
    estimated_reference_iterations: int | None = Field(None, ge=0)
    estimated_total_work_units: int | None = Field(None, ge=0)
    work_unit_policy: str | None = None
    reference_workload: str | None = None
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    updated_at: datetime


def _coerce_persisted_run_estimate(value: Any) -> RunEstimate | None:
    """Ignore incomplete legacy snapshots at the API response boundary."""
    if value is None or isinstance(value, RunEstimate):
        return value
    if not isinstance(value, dict):
        return None

    try:
        return RunEstimate.model_validate(value)
    except ValidationError:
        return None


class RunResponse(BaseORMModel):
    """Schema for run responses."""

    id: UUID
    molecule_id: UUID
    status: RunStatus
    algorithm: RunAlgorithm | None = None
    mode: RunMode | None = None
    backend_target: BackendTarget | None = None
    config_json: dict[str, Any] = Field(
        ..., alias="config_json", description="Configuration snapshot"
    )
    ibm_job_id: str | None = None
    client_request_id: UUID | None = None
    execution_generation: int = 1
    restarted_from_run_id: UUID | None = None
    credential_profile_id: UUID | None = None
    credential_profile_name: str | None = None
    basis_set: str | None = None
    versions: dict[str, Any] | None = None
    # run_metadata is the ORM attribute name; serialised as "metadata" in API responses
    metadata: dict[str, Any] | None = Field(None, validation_alias="run_metadata")
    initial_estimate: RunEstimate | None = None
    latest_estimate: RunEstimate | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("initial_estimate", "latest_estimate", mode="before")
    @classmethod
    def discard_incomplete_estimate(cls, value: Any) -> RunEstimate | None:
        return _coerce_persisted_run_estimate(value)


class RunSummaryResponse(BaseModel):
    """Lightweight run list item used by high-volume runs tables."""

    id: UUID
    molecule_id: UUID
    molecule_name: str | None = None
    status: RunStatus
    algorithm: RunAlgorithm | None = None
    backend_target: BackendTarget | None = None
    backend_name: str | None = None
    converged: bool | None = None
    chemical_accurate: bool | None = None
    execution_generation: int = 1
    restarted_from_run_id: UUID | None = None
    credential_profile_id: UUID | None = None
    credential_profile_name: str | None = None
    basis_set: str | None = None
    metadata: dict[str, Any] | None = Field(None, validation_alias="run_metadata")
    latest_estimate: RunEstimate | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("latest_estimate", mode="before")
    @classmethod
    def discard_incomplete_estimate(cls, value: Any) -> RunEstimate | None:
        return _coerce_persisted_run_estimate(value)

    @classmethod
    def from_run(cls, run: Any) -> "RunSummaryResponse":
        config_json = getattr(run, "config_json", {}) or {}
        backend_options = config_json.get("backend_options")
        backend_name = None
        if isinstance(backend_options, dict):
            raw_backend_name = backend_options.get("backend_name")
            if isinstance(raw_backend_name, str) and raw_backend_name.strip():
                backend_name = raw_backend_name.strip()
        result = getattr(run, "result", None)

        return cls.model_validate(
            {
                "id": getattr(run, "id"),
                "molecule_id": getattr(run, "molecule_id"),
                "molecule_name": getattr(getattr(run, "molecule", None), "name", None),
                "status": getattr(run, "status"),
                "algorithm": getattr(run, "algorithm", None),
                "backend_target": getattr(run, "backend_target", None),
                "backend_name": backend_name,
                "converged": getattr(result, "converged", None),
                "chemical_accurate": resolve_run_chemical_accurate(run),
                "execution_generation": getattr(run, "execution_generation", 1),
                "restarted_from_run_id": getattr(run, "restarted_from_run_id", None),
                "credential_profile_id": getattr(run, "credential_profile_id", None),
                "credential_profile_name": getattr(run, "credential_profile_name", None),
                "basis_set": getattr(run, "basis_set", None),
                "run_metadata": getattr(run, "run_metadata", None),
                "latest_estimate": getattr(run, "latest_estimate", None),
                "created_at": getattr(run, "created_at"),
                "updated_at": getattr(run, "updated_at"),
            }
        )


class RunExecutionSegmentResponse(BaseORMModel):
    """One measured worker execution segment."""

    id: UUID
    run_id: UUID
    execution_generation: int
    attempt_number: int
    rq_job_id: str | None = None
    status: str
    worker_started_at: datetime
    worker_finished_at: datetime | None = None
    duration_seconds: float | None = Field(None, ge=0.0)
    last_heartbeat_at: datetime | None = None
    last_heartbeat_duration_seconds: float | None = Field(None, ge=0.0)
    termination_reason: str | None = None


class RunListResponse(BaseModel):
    """Schema for paginated run list."""

    items: list[RunResponse]
    total: int
    limit: int
    offset: int


class RunSummaryListResponse(BaseModel):
    """Schema for paginated lightweight run list."""

    items: list[RunSummaryResponse]
    total: int
    limit: int
    offset: int


class RunCancelResponse(BaseModel):
    """Schema for run cancellation response."""

    id: UUID
    status: RunStatus


class RunActionResponse(BaseModel):
    """Schema for run control action responses."""

    id: UUID
    status: RunStatus
    execution_generation: int = 1
    message: str | None = None
    child_run_id: UUID | None = None
    checkpoint_id: UUID | None = None


class RunCheckpointResponse(BaseORMModel):
    """Persisted run checkpoint response."""

    id: UUID
    run_id: UUID
    execution_generation: int
    algorithm: str
    checkpoint_version: str
    payload: dict[str, Any]
    event_sequence: int | None = None
    created_at: datetime


class RunCheckpointListResponse(BaseModel):
    """List of checkpoints for a run."""

    items: list[RunCheckpointResponse]
    total: int


class ValidationErrorCode(StrEnum):
    """Machine-readable validation error reasons."""

    MISSING_REQUIRED = "missing_required"
    INVALID_RANGE = "invalid_range"
    INCOMPATIBLE_BACKEND = "incompatible_backend"
    UNSUPPORTED_OPTION = "unsupported_option"


class RunValidationErrorDetail(BaseModel):
    """Single validation error."""

    field: str
    code: ValidationErrorCode | None = None
    message: str
    suggestion: str | None = None


class RunValidationResponse(BaseModel):
    """Schema for config validation response."""

    valid: bool
    errors: list[RunValidationErrorDetail] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    estimate: RunEstimate | None = None


class ExportBundle(BaseModel):
    """Reproducibility export bundle for a completed or partial run."""

    export_version: str = "1.0"
    exported_at: datetime
    molecule: MoleculeResponse
    run: RunResponse
    versions: dict[str, Any] | None
    events: list[RunEventResponse]
    result: RunResultResponse | None
    execution_segments: list[RunExecutionSegmentResponse] = Field(default_factory=list)
