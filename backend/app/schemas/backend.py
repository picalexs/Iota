"""Pydantic schemas for runtime backend discovery and selection."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import BackendTarget, RunAlgorithm
from app.schemas.run_config import BackendOptions, BackendSelectionPolicy

NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(ge=1)]
NonNegativeFloat = Annotated[float, Field(ge=0.0)]


class BackendProcessorType(BaseModel):
    """Safe processor-family metadata for a backend."""

    model_config = ConfigDict(extra="forbid")

    family: str | None = None
    revision: str | None = None
    segment: str | None = None


class BackendSummary(BaseModel):
    """Best-effort backend metadata safe to expose from the API."""

    model_config = ConfigDict(extra="forbid")

    target: BackendTarget
    name: str
    display_name: str
    available: bool
    credential_configured: bool | None = None
    credentials_usable: bool | None = None
    simulator: bool
    supports_noise_profile: bool
    supports_transpile_preview: bool
    num_qubits: NonNegativeInt | None = None
    pending_jobs: NonNegativeInt | None = None
    operational: bool | None = None
    basis_gates: list[str] | None = None
    coupling_map: list[list[int]] | None = None
    coupling_map_edges: NonNegativeInt | None = None
    max_shots: PositiveInt | None = None
    error_rate: NonNegativeFloat | None = None
    processor_type: BackendProcessorType | None = None
    qubit_errors: list[dict[str, Any]] | None = None
    gate_errors: list[dict[str, Any]] | None = None
    status_message: str | None = None
    warnings: list[str] = Field(default_factory=list)


class BackendListResponse(BaseModel):
    """Response for GET /api/backends."""

    backends: list[BackendSummary]
    warnings: list[str] = Field(default_factory=list)


class BackendResolveRequest(BaseModel):
    """Request for resolving a backend selection policy to a concrete backend."""

    model_config = ConfigDict(extra="forbid")

    target: BackendTarget
    backend_options: BackendOptions = Field(
        default_factory=lambda: BackendOptions.model_validate({})
    )
    required_qubits: PositiveInt | None = None
    algorithm: RunAlgorithm | None = None


class BackendResolveResponse(BaseModel):
    """Concrete backend resolution result."""

    target: BackendTarget
    selection_policy: BackendSelectionPolicy
    resolved: bool
    backend_name: str | None = None
    backend: BackendSummary | None = None
    warnings: list[str] = Field(default_factory=list)


class TranspilePreviewRequest(BaseModel):
    """Request for a deterministic transpile metadata preview."""

    model_config = ConfigDict(extra="forbid")

    target: BackendTarget
    backend_options: BackendOptions = Field(
        default_factory=lambda: BackendOptions.model_validate({})
    )
    num_qubits: int = Field(..., ge=1)
    circuit_depth: PositiveInt | None = None
    algorithm: RunAlgorithm | None = None


class TranspilePreviewResponse(BaseModel):
    """Best-effort transpile metadata preview without constructing a full circuit."""

    target: BackendTarget
    backend_name: str | None = None
    feasible: bool
    requested_qubits: int
    metadata: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
