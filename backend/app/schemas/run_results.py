"""Pydantic schemas for run results and reproducibility exports."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.common import BaseORMModel


class CircuitArtifactPreview(BaseModel):
    """OpenQASM/SVG preview payload for a persisted circuit artifact."""

    model_config = ConfigDict(extra="allow")

    qubits: int | None = None
    classical_bits: int | None = None
    style: str | None = None
    qasm: str | None = None
    diagram_svg: str | None = None


class CircuitArtifact(BaseModel):
    """Typed quantum-circuit artifact stored under algorithm_metrics."""

    model_config = ConfigDict(extra="allow")

    schema_version: str
    artifact_type: Literal["quantum_circuit"]
    id: str | None = None
    artifact_id: str
    algorithm: str
    role: str
    phase: str | None = None
    representative: bool | None = None
    label: str
    source: str | None = None
    iteration: int | None = None
    qubits: int | None = None
    classical_bits: int | None = None
    depth: int | None = None
    size: int | None = None
    operation_counts: dict[str, int] = Field(default_factory=dict)
    parameters: dict[str, Any] | None = None
    logical: CircuitArtifactPreview | None = None
    preview: CircuitArtifactPreview | None = None
    transpiled: CircuitArtifactPreview | None = None
    downsampling: dict[str, Any] | None = None
    transpiled_preview: dict[str, Any] | None = None
    backend_target: str | None = None
    primitive_family: str | None = None
    job_ids: list[str] = Field(default_factory=list)
    pub_count: int | None = None
    shots: int | None = None
    transpilation_summary: dict[str, Any] | None = None


class RunResultResponse(BaseORMModel):
    """Schema for run result."""

    run_id: UUID
    energy: float = Field(..., description="Ground-state energy in Hartree")
    final_energy: float | None = None
    best_observed_energy: float | None = None
    reported_energy: float | None = None
    reported_energy_source: str | None = None
    reference_energy: float | None = None
    reference_basis: str | None = None
    signed_error: float | None = None
    iterations: int = Field(
        ...,
        description=(
            "Algorithm-reported iteration count; VQE uses objective evaluations while "
            "optimizer-native step counts remain in algorithm_metrics.optimizer_iterations"
        ),
    )
    optimal_parameters: list[float] = Field(
        ...,
        description="Variational parameters associated with the reported energy",
    )
    converged: bool = Field(
        ...,
        description="Whether solver-specific convergence criteria were met",
    )
    algorithm_metrics: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Algorithm-specific metrics stored in raw_result when available. "
            "Circuit previews are exposed as circuit_artifacts using the CircuitArtifact shape."
        ),
    )
    energy_policy: dict[str, Any] | None = Field(
        default=None,
        description="Policy explaining which algorithm energy is reported at the top level.",
    )
    created_at: datetime

    @model_validator(mode="after")
    def populate_energy_policy(self) -> "RunResultResponse":
        if self.energy_policy is None and isinstance(self.algorithm_metrics, dict):
            policy = self.algorithm_metrics.get("energy_policy")
            if isinstance(policy, dict):
                self.energy_policy = policy
        return self
