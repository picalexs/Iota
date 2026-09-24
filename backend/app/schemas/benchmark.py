"""Pydantic schemas for persisted benchmark batches."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.models.enums import RunAlgorithm

BenchmarkBackendMode = Literal[
    "statevector",
    "aer_simulator",
    "aer_simulator_backend_noise",
    "ibm_runtime",
]
BenchmarkRunHistoryStatus = Literal[
    "draft",
    "running",
    "paused",
    "finished",
    "partial",
    "failed",
    "cancelled",
    "planned",
    "excluded",
]


class BenchmarkRunBase(BaseModel):
    """Shared persisted benchmark batch payload."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    name: str = Field(..., min_length=1, max_length=255)
    campaign_id: str | None = Field(
        None,
        min_length=1,
        max_length=255,
        validation_alias=AliasChoices("campaignId", "campaign_id"),
        serialization_alias="campaignId",
    )
    registration_digest: str | None = Field(
        None,
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
        validation_alias=AliasChoices("registrationDigest", "registration_digest"),
        serialization_alias="registrationDigest",
    )
    campaign_metadata: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("campaignMetadata", "campaign_metadata"),
        serialization_alias="campaignMetadata",
    )
    selected_molecule_keys: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("selectedMoleculeKeys", "selected_molecule_keys"),
        serialization_alias="selectedMoleculeKeys",
    )
    selected_algorithms: list[RunAlgorithm] = Field(
        default_factory=list,
        validation_alias=AliasChoices("selectedAlgorithms", "selected_algorithms"),
        serialization_alias="selectedAlgorithms",
    )
    selected_basis: str = Field(
        "sto-3g",
        min_length=1,
        max_length=255,
        validation_alias=AliasChoices("selectedBasis", "selected_basis"),
        serialization_alias="selectedBasis",
    )
    selected_backend_mode: BenchmarkBackendMode = Field(
        "statevector",
        validation_alias=AliasChoices("selectedBackendMode", "selected_backend_mode"),
        serialization_alias="selectedBackendMode",
    )
    selected_backend_name: str | None = Field(
        None,
        max_length=255,
        validation_alias=AliasChoices("selectedBackendName", "selected_backend_name"),
        serialization_alias="selectedBackendName",
    )
    shots: int = Field(4096, ge=1, le=1_000_000)
    optimization_level: int = Field(
        1,
        ge=0,
        le=3,
        validation_alias=AliasChoices("optimizationLevel", "optimization_level"),
        serialization_alias="optimizationLevel",
    )
    seed_transpiler: int | None = Field(
        None,
        ge=0,
        le=2**32 - 1,
        validation_alias=AliasChoices("seedTranspiler", "seed_transpiler"),
        serialization_alias="seedTranspiler",
    )
    dynamical_decoupling: bool = Field(
        False,
        validation_alias=AliasChoices("dynamicalDecoupling", "dynamical_decoupling"),
        serialization_alias="dynamicalDecoupling",
    )
    twirling: bool = Field(
        False,
        validation_alias=AliasChoices("twirling"),
        serialization_alias="twirling",
    )
    chemical_accuracy_ha: float = Field(
        1.6e-3,
        gt=0.0,
        validation_alias=AliasChoices("chemicalAccuracyHa", "chemical_accuracy_ha"),
        serialization_alias="chemicalAccuracyHa",
    )
    custom_molecules: list[dict[str, Any]] = Field(
        default_factory=list,
        validation_alias=AliasChoices("customMolecules", "custom_molecules"),
        serialization_alias="customMolecules",
    )
    entries: list[dict[str, Any]] = Field(default_factory=list)


class BenchmarkRunCreate(BenchmarkRunBase):
    """Create a benchmark batch snapshot."""


class BenchmarkRegistrationCreate(BenchmarkRunCreate):
    """Register one validated campaign as a persisted benchmark."""

    campaign_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        validation_alias=AliasChoices("campaignId", "campaign_id"),
        serialization_alias="campaignId",
    )
    registration_digest: str = Field(
        ...,
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
        validation_alias=AliasChoices("registrationDigest", "registration_digest"),
        serialization_alias="registrationDigest",
    )


class BenchmarkRunUpdate(BaseModel):
    """Patch a benchmark batch snapshot."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=255)
    campaign_metadata: dict[str, Any] | None = Field(
        None,
        validation_alias=AliasChoices("campaignMetadata", "campaign_metadata"),
        serialization_alias="campaignMetadata",
    )
    selected_molecule_keys: list[str] | None = Field(
        None,
        validation_alias=AliasChoices("selectedMoleculeKeys", "selected_molecule_keys"),
        serialization_alias="selectedMoleculeKeys",
    )
    selected_algorithms: list[RunAlgorithm] | None = Field(
        None,
        validation_alias=AliasChoices("selectedAlgorithms", "selected_algorithms"),
        serialization_alias="selectedAlgorithms",
    )
    selected_basis: str | None = Field(
        None,
        min_length=1,
        max_length=255,
        validation_alias=AliasChoices("selectedBasis", "selected_basis"),
        serialization_alias="selectedBasis",
    )
    selected_backend_mode: BenchmarkBackendMode | None = Field(
        None,
        validation_alias=AliasChoices("selectedBackendMode", "selected_backend_mode"),
        serialization_alias="selectedBackendMode",
    )
    selected_backend_name: str | None = Field(
        None,
        max_length=255,
        validation_alias=AliasChoices("selectedBackendName", "selected_backend_name"),
        serialization_alias="selectedBackendName",
    )
    shots: int | None = Field(None, ge=1, le=1_000_000)
    optimization_level: int | None = Field(
        None,
        ge=0,
        le=3,
        validation_alias=AliasChoices("optimizationLevel", "optimization_level"),
        serialization_alias="optimizationLevel",
    )
    seed_transpiler: int | None = Field(
        None,
        ge=0,
        le=2**32 - 1,
        validation_alias=AliasChoices("seedTranspiler", "seed_transpiler"),
        serialization_alias="seedTranspiler",
    )
    dynamical_decoupling: bool | None = Field(
        None,
        validation_alias=AliasChoices("dynamicalDecoupling", "dynamical_decoupling"),
        serialization_alias="dynamicalDecoupling",
    )
    twirling: bool | None = Field(
        None,
        validation_alias=AliasChoices("twirling"),
        serialization_alias="twirling",
    )
    chemical_accuracy_ha: float | None = Field(
        None,
        gt=0.0,
        validation_alias=AliasChoices("chemicalAccuracyHa", "chemical_accuracy_ha"),
        serialization_alias="chemicalAccuracyHa",
    )
    custom_molecules: list[dict[str, Any]] | None = Field(
        None,
        validation_alias=AliasChoices("customMolecules", "custom_molecules"),
        serialization_alias="customMolecules",
    )
    entries: list[dict[str, Any]] | None = None


class BenchmarkRunResponse(BenchmarkRunBase):
    """Full persisted benchmark batch response."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class BenchmarkRunListResponse(BaseModel):
    """Paginated benchmark batch response."""

    items: list[BenchmarkRunResponse]
    total: int
    limit: int
    offset: int


class BenchmarkRunSummaryResponse(BaseModel):
    """Compact benchmark batch response for history lists."""

    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    name: str
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")
    selected_molecule_keys: list[str] = Field(
        validation_alias=AliasChoices("selectedMoleculeKeys", "selected_molecule_keys"),
        serialization_alias="selectedMoleculeKeys",
    )
    selected_basis: str = Field(
        validation_alias=AliasChoices("selectedBasis", "selected_basis"),
        serialization_alias="selectedBasis",
    )
    selected_backend_mode: BenchmarkBackendMode = Field(
        validation_alias=AliasChoices("selectedBackendMode", "selected_backend_mode"),
        serialization_alias="selectedBackendMode",
    )
    selected_backend_name: str | None = Field(
        None,
        validation_alias=AliasChoices("selectedBackendName", "selected_backend_name"),
        serialization_alias="selectedBackendName",
    )
    status: BenchmarkRunHistoryStatus
    row_count: int = Field(validation_alias=AliasChoices("rowCount", "row_count"), serialization_alias="rowCount")
    completed_count: int = Field(
        validation_alias=AliasChoices("completedCount", "completed_count"),
        serialization_alias="completedCount",
    )
    active_count: int = Field(
        validation_alias=AliasChoices("activeCount", "active_count"),
        serialization_alias="activeCount",
    )
    paused_count: int = Field(
        validation_alias=AliasChoices("pausedCount", "paused_count"),
        serialization_alias="pausedCount",
    )
    failed_count: int = Field(
        validation_alias=AliasChoices("failedCount", "failed_count"),
        serialization_alias="failedCount",
    )
    cancelled_count: int = Field(
        validation_alias=AliasChoices("cancelledCount", "cancelled_count"),
        serialization_alias="cancelledCount",
    )
    planned_count: int = Field(
        validation_alias=AliasChoices("plannedCount", "planned_count"),
        serialization_alias="plannedCount",
    )
    excluded_count: int = Field(
        validation_alias=AliasChoices("excludedCount", "excluded_count"),
        serialization_alias="excludedCount",
    )
    associated_run_count: int = Field(
        validation_alias=AliasChoices("associatedRunCount", "associated_run_count"),
        serialization_alias="associatedRunCount",
    )


class BenchmarkRunSummaryListResponse(BaseModel):
    """Paginated compact benchmark batch response."""

    items: list[BenchmarkRunSummaryResponse]
    total: int
    limit: int
    offset: int
