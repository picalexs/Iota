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
