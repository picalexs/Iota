"""Pydantic request schemas for run operations."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import BackendTarget, RunAlgorithm, RunMode, RunStatus
from app.schemas.run_config import AdvancedConfig, BackendOptions, EasyOptions, NoiseProfile


class RunCreate(BaseModel):
    """Schema for creating a new run."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "molecule_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "algorithm": "vqe",
                "mode": "easy",
                "backend_target": "statevector",
                "backend_options": {
                    "selection_policy": "manual",
                    "shots": 4096,
                    "optimization_level": 1,
                    "aer_method": "automatic",
                },
                "easy_options": {
                    "goal": "balanced",
                },
            }
        }
    )

    molecule_id: UUID = Field(..., description="ID of the molecule to simulate")
    client_request_id: UUID | None = Field(None, description="Optional idempotency key")

    algorithm: RunAlgorithm
    mode: RunMode
    backend_target: BackendTarget
    backend_options: BackendOptions = Field(
        default_factory=lambda: BackendOptions.model_validate({})
    )
    easy_options: EasyOptions | None = None
    advanced_config: AdvancedConfig | None = None
    basis_set_override: str | None = Field(None, min_length=1, max_length=255)
    chemical_accuracy_target_ha: float | None = Field(None, gt=0.0)
    noise_profile: NoiseProfile | None = None
    ibm_runtime_confirmed: bool = Field(
        False,
        description="Explicit user confirmation for IBM Runtime hardware submissions.",
    )

    def effective_basis_set(self, molecule_basis_set: str = "sto-3g") -> str:
        if self.basis_set_override:
            return self.basis_set_override
        return molecule_basis_set

    def snapshot_config(self) -> dict[str, Any]:
        backend_options = self.backend_options.model_dump(mode="json")
        # Preserve the distinction between automatic precision and an explicit
        # exact request in the worker-facing snapshot. Other nullable options
        # retain their existing compatibility shape.
        if backend_options.get("estimator_precision") is None:
            backend_options.pop("estimator_precision", None)
        return {
            "algorithm": self.algorithm.value,
            "mode": self.mode.value,
            "backend_target": self.backend_target.value,
            "backend_options": backend_options,
            "basis_set_override": self.basis_set_override,
            "easy_options": self.easy_options.model_dump() if self.easy_options else None,
            "advanced_config": self.advanced_config.model_dump() if self.advanced_config else None,
            "chemical_accuracy_target_ha": self.chemical_accuracy_target_ha,
            "noise_profile": self.noise_profile.model_dump() if self.noise_profile else None,
            "ibm_runtime_confirmed": self.ibm_runtime_confirmed,
        }


class RunUpdate(BaseModel):
    """Schema for internal run status updates (worker → API)."""

    model_config = ConfigDict(extra="forbid")

    status: RunStatus = Field(..., description="New run status")


class RunControlRequest(BaseModel):
    """Request body for pause/resume run control actions."""

    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(None, max_length=500)


class RunRestartRequest(BaseModel):
    """Request body for restarting a run from its stored configuration."""

    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(None, max_length=500)
    client_request_id: UUID | None = Field(None, description="Optional idempotency key for clone.")
    cancel_active: bool = Field(
        False,
        description="Cancel the source run first when it is still active.",
    )


class RunCheckpointCreate(BaseModel):
    """Checkpoint payload for a run execution generation."""

    model_config = ConfigDict(extra="forbid")

    checkpoint_version: str = Field("1.0", min_length=1, max_length=32)
    payload: dict[str, Any] = Field(default_factory=dict)
    event_sequence: int | None = Field(None, ge=0)


class RunValidationRequest(BaseModel):
    """Schema for run validation request."""

    molecule_id: UUID
    run: RunCreate
