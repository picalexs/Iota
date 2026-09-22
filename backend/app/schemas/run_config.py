"""Pydantic schemas for run configuration and algorithm options."""

from __future__ import annotations

import math
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import EasyGoal, RunAlgorithm
from shared.contracts.catalog import PUBLIC_LIMITS


class BackendSelectionPolicy(StrEnum):
    """Backend selection modes for concrete runtime backends."""

    MANUAL = "manual"
    LEAST_BUSY = "least_busy"
    LEAST_ERROR = "least_error"


class BackendOptions(BaseModel):
    """Runtime backend options shared by Aer and IBM Runtime targets."""

    model_config = ConfigDict(extra="forbid")

    selection_policy: BackendSelectionPolicy = BackendSelectionPolicy.MANUAL
    backend_name: str | None = Field(None, min_length=1, max_length=255)
    shots: int = Field(4096, ge=1, le=1_000_000)
    estimator_precision: float | None = Field(
        None,
        ge=0.0,
        allow_inf_nan=False,
        description=(
            "Estimator standard-error budget. Omit or set null to derive 1/sqrt(shots) "
            "for noisy Aer. Zero requests exact estimator values."
        ),
    )
    optimization_level: int = Field(1, ge=0, le=3)
    seed_simulator: int | None = Field(None, ge=0, le=2**32 - 1)
    seed_transpiler: int | None = Field(None, ge=0, le=2**32 - 1)
    credential_profile_id: UUID | None = Field(
        None,
        description="Non-secret IBM credential profile reference for Runtime requests.",
    )
    aer_method: Literal[
        "automatic",
        "statevector",
        "density_matrix",
        "matrix_product_state",
        "stabilizer",
        "extended_stabilizer",
        "unitary",
        "superop",
    ] = "automatic"
    device: Literal["CPU", "GPU"] | None = Field(
        None,
        exclude_if=lambda value: value is None,
        description="Aer execution device. GPU requires a GPU-enabled worker.",
    )
    batched_shots_gpu: bool | None = Field(
        None,
        exclude_if=lambda value: value is None,
        description="Enable Aer GPU shot batching when supported by the method.",
    )
    runtime_parameter_bind_enable: bool | None = Field(
        None,
        exclude_if=lambda value: value is None,
        description="Enable Aer runtime parameter binding.",
    )
    shot_branching_enable: bool | None = Field(
        None,
        exclude_if=lambda value: value is None,
        description="Enable Aer shot branching when supported by the workload.",
    )
    blocking_enable: bool | None = Field(
        None,
        exclude_if=lambda value: value is None,
        description="Enable Aer blocking simulation mode.",
    )
    cuStateVec_enable: bool | None = Field(
        None,
        exclude_if=lambda value: value is None,
        description="Enable Aer cuStateVec integration when available.",
    )
    max_parallel_threads: int | None = Field(
        None,
        ge=1,
        le=1024,
        exclude_if=lambda value: value is None,
        description="Bound Aer numerical threads per worker.",
    )
    max_parallel_experiments: int | None = Field(
        None,
        ge=1,
        le=1024,
        exclude_if=lambda value: value is None,
        description="Bound Aer parallel experiments per worker.",
    )
    max_parallel_shots: int | None = Field(
        None,
        ge=1,
        le=1024,
        exclude_if=lambda value: value is None,
        description="Bound Aer parallel shots per worker.",
    )
    aer_pub_chunk_size: int | None = Field(
        None,
        ge=1,
        le=32,
        exclude_if=lambda value: value is None,
        description="Optional PUB batch size for projected Aer matrix workloads.",
    )


class NoiseModelSource(StrEnum):
    """Source type for optional noise profile."""

    BACKEND_DERIVED = "backend_derived"
    CUSTOM_PRESET = "custom_preset"


class CustomNoisePreset(StrEnum):
    """Allowed custom noise presets."""

    DEPOLARIZING_CX = "depolarizing_cx"
    THERMAL_RELAXATION = "thermal_relaxation"
    READOUT_BIAS = "readout_bias"


class BackendDerivedNoiseProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal[NoiseModelSource.BACKEND_DERIVED]
    reference_backend: str = Field(..., min_length=1)
    temperature_mk: float | None = Field(None, ge=0.0, allow_inf_nan=False)

    @field_validator("reference_backend")
    @classmethod
    def validate_reference_backend(cls, value: str) -> str:
        normalized = value.strip()
        if normalized.lower() in {
            "aer_simulator",
            "aer_simulator_statevector",
            "statevector",
        }:
            raise ValueError("backend-derived noise requires an IBM backend reference")
        return normalized


class CustomPresetNoiseProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal[NoiseModelSource.CUSTOM_PRESET]
    preset: CustomNoisePreset
    strength: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        allow_inf_nan=False,
        description="Gate strength for depolarizing CX noise.",
    )
    p01: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        allow_inf_nan=False,
        description="Probability of reading 1 when the true value is 0.",
    )
    p10: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        allow_inf_nan=False,
        description="Probability of reading 0 when the true value is 1.",
    )
    t1_us: float | None = Field(
        None,
        gt=0.0,
        allow_inf_nan=False,
        description="T1 relaxation time in microseconds.",
    )
    t2_us: float | None = Field(
        None,
        gt=0.0,
        allow_inf_nan=False,
        description="T2 relaxation time in microseconds.",
    )
    gate_time_us: float | None = Field(
        None,
        gt=0.0,
        allow_inf_nan=False,
        description="Gate time in microseconds for thermal relaxation.",
    )

    @model_validator(mode="after")
    def validate_preset_parameters(self) -> "CustomPresetNoiseProfile":
        populated = {
            key
            for key in ("strength", "p01", "p10", "t1_us", "t2_us", "gate_time_us")
            if getattr(self, key) is not None
        }
        if self.preset == CustomNoisePreset.DEPOLARIZING_CX:
            required = {"strength"}
        elif self.preset == CustomNoisePreset.READOUT_BIAS:
            required = {"p01", "p10"}
        else:
            required = {"t1_us", "t2_us", "gate_time_us"}
        if populated != required:
            expected = ", ".join(sorted(required))
            raise ValueError(f"preset '{self.preset.value}' requires exactly: {expected}")
        if self.preset == CustomNoisePreset.THERMAL_RELAXATION:
            assert self.t1_us is not None
            assert self.t2_us is not None
            if self.t2_us > 2 * self.t1_us:
                raise ValueError("t2_us must not exceed 2 * t1_us")
        return self


NoiseProfile = Annotated[
    BackendDerivedNoiseProfile | CustomPresetNoiseProfile,
    Field(discriminator="source"),
]


class EasyOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: EasyGoal


class VQEAdvancedConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    algorithm: Literal[RunAlgorithm.VQE]
    ansatz_name: str
    optimizer_name: str
    max_iterations: int = Field(..., ge=1, le=5000)
    max_function_evaluations: int | None = Field(None, ge=1, le=250_000)
    reps: int = Field(2, ge=1, le=6)
    optimizer_options: dict[str, Any] | None = None
    initial_parameters: list[float] | None = None
    initial_point_strategy: Literal["seeded_random", "zero", "zero_plus_seeded_random"] | None = (
        None
    )
    initial_point_candidates: int | None = Field(None, ge=1)
    seed: int | None = None
    convergence_threshold: float | None = Field(None, gt=0.0)
    parameter_bounds: list[list[float]] | None = None


class SQDSamplingParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    samples_per_batch: int = Field(..., ge=1)
    num_batches: int = Field(..., ge=1)
    max_iterations: int = Field(..., ge=1)
    num_elec_a: int | None = Field(None, ge=0)
    num_elec_b: int | None = Field(None, ge=0)
    energy_tol: float | None = Field(None, gt=0.0)
    occupancies_tol: float | None = Field(None, gt=0.0)
    min_selected_configurations: int | None = Field(None, ge=1)
    seed: int | None = Field(None, ge=0, le=2**32 - 1)
    symmetrize_spin: bool | None = None
    carryover_threshold: float | None = Field(None, ge=0.0, le=1.0)
    max_dim: int | tuple[int, int] | Literal["full"] | None = None
    spin_sq_target: float | None = Field(None, ge=0.0)
    sci_solver_options: dict[str, Any] | None = None


class SKQDSamplingParams(BaseModel):
    """Sampling and selected-CI controls used by the SKQD sample union."""

    model_config = ConfigDict(extra="forbid")

    num_elec_a: int | None = Field(None, ge=0)
    num_elec_b: int | None = Field(None, ge=0)
    min_selected_configurations: int | None = Field(None, ge=1)
    seed: int | None = Field(None, ge=0, le=2**32 - 1)
    symmetrize_spin: bool | None = None
    max_dim: int | tuple[int, int] | Literal["full"] | None = None
    spin_sq_target: float | None = Field(None, ge=0.0)
    sci_solver_options: dict[str, Any] | None = None


class SQDAdvancedConfig(SQDSamplingParams):
    model_config = ConfigDict(extra="forbid")

    algorithm: Literal[RunAlgorithm.SQD]
    sampling_state_source: Literal["hf", "vqe"] = "hf"
    sampling_vqe_ansatz_name: str | None = None
    sampling_vqe_optimizer_name: str | None = None
    sampling_vqe_max_iterations: int | None = Field(None, ge=1, le=5000)
    sampling_vqe_reps: int | None = Field(None, ge=1, le=6)
    sampling_vqe_seed: int | None = Field(None, ge=0, le=2**32 - 1)


class KQDAdvancedConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    algorithm: Literal[RunAlgorithm.KQD]
    krylov_dim: int = Field(..., ge=2)
    time_step: float = Field(..., gt=0.0)
    evolution_method: Literal["exact", "trotter"] = "trotter"
    trotter_steps: int = Field(1, ge=1, le=32)
    residual_tolerance: float | None = Field(None, gt=0.0)


class QFDAdvancedConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    algorithm: Literal[RunAlgorithm.QFD]
    num_time_points: int = Field(..., ge=2)
    max_time: float = Field(..., gt=0.0)
    time_grid_type: Literal["linear", "geometric"] = "linear"
    qfd_variant: Literal[
        "qfd_chemistry_forward",
        "qfd_original_symmetric",
    ] = "qfd_chemistry_forward"
    kappa: float = Field(1.0, gt=0.0)
    trotter_steps: int = Field(1, ge=1, le=32)
    residual_tolerance: float | None = Field(None, gt=0.0)


class QSEComplexAmplitude(BaseModel):
    """JSON-safe complex scalar used by QSE provided-reference payloads."""

    model_config = ConfigDict(extra="forbid")

    real: float
    imag: float = 0.0

    @field_validator("real", "imag")
    @classmethod
    def finite_components(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("complex amplitude components must be finite")
        return value


QSEReferenceScalar = float | QSEComplexAmplitude


class QSESectorAmplitude(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bitstring: str
    amplitude: QSEReferenceScalar


class QSEAdvancedConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    algorithm: Literal[RunAlgorithm.QSE]
    reference_method: Literal["hf", "vqe", "provided_state", "provided_sector"]
    provided_state_vector: list[QSEReferenceScalar] | None = None
    provided_sector_amplitudes: list[QSESectorAmplitude] | None = None
    excitation_level: Literal["singles", "singles_doubles"]
    max_subspace_dim: int | None = Field(None, ge=1, le=96)
    vqe_reference_ansatz_name: str | None = None
    vqe_reference_optimizer_name: str | None = None
    vqe_reference_max_iterations: int | None = Field(None, ge=1)
    vqe_reference_reps: int | None = Field(None, ge=1, le=6)
    regularization: float | None = Field(None, ge=0.0)
    overlap_threshold: float | None = Field(None, gt=0.0)
    residual_tolerance: float | None = Field(None, gt=0.0)


class SKQDAdvancedConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    algorithm: Literal[RunAlgorithm.SKQD]
    samples_per_state: int = Field(
        ...,
        ge=PUBLIC_LIMITS["advanced_config.samples_per_state"]["minimum"],
        le=PUBLIC_LIMITS["advanced_config.samples_per_state"]["maximum"],
    )
    base_sampling_options: SKQDSamplingParams
    krylov_extension_dim: int = Field(..., ge=1, le=32)
    sampling_mode: Literal["sample_union_exact", "legacy_statevector_extension"] = (
        "sample_union_exact"
    )
    time_step: float = Field(0.1, gt=0.0)
    trotter_steps: int = Field(1, ge=1, le=32)
    residual_tolerance: float | None = Field(None, gt=0.0)


AdvancedConfig = Annotated[
    VQEAdvancedConfig
    | SQDAdvancedConfig
    | KQDAdvancedConfig
    | QFDAdvancedConfig
    | QSEAdvancedConfig
    | SKQDAdvancedConfig,
    Field(discriminator="algorithm"),
]
