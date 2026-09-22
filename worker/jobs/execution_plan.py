"""Pure resource planning contracts for worker execution stages.

The contracts in this module describe a planned device resolution. They do not
inspect a worker, select a queue, or prove that a GPU stage executed on a GPU.
Runtime integrations can use the resolved values without changing public run
schemas.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable


class ResourceClass(StrEnum):
    """Resource family that can execute a stage."""

    CPU = "cpu"
    AER_GPU = "aer_gpu"
    CHEMISTRY_GPU = "chemistry_gpu"
    SBD_GPU = "sbd_gpu"


class DeviceRequest(StrEnum):
    """Device preference accepted by a stage plan."""

    CPU = "CPU"
    GPU = "GPU"
    AUTO = "AUTO"


class ExecutionPlanError(ValueError):
    """Base error for invalid execution plans."""


class GpuUnavailableError(ExecutionPlanError):
    """Raised when a stage explicitly requires an unavailable GPU resource."""


@dataclass(frozen=True, slots=True)
class StageRequest:
    """Pure input facts used to resolve one execution stage.

    ``gpu_available`` is supplied by a caller that owns runtime capability
    discovery. It is not inferred from a requested device or resource class.
    """

    name: str
    resource_class: ResourceClass | str
    requested_device: DeviceRequest | str | None = None
    gpu_available: bool = False
    provider: str | None = None


@dataclass(frozen=True, slots=True)
class StagePlan:
    """Resolved device plan for one stage.

    ``actual_device`` is the planned device target. It is not runtime proof;
    integrations must record execution evidence separately.
    """

    name: str
    resource_class: ResourceClass
    requested_device: DeviceRequest
    actual_device: DeviceRequest
    gpu_available: bool
    provider: str | None = None
    fallback_reason: str | None = None

    @classmethod
    def resolve(cls, request: StageRequest) -> "StagePlan":
        """Resolve one stage request without inspecting external state."""
        name = request.name.strip() if isinstance(request.name, str) else ""
        if not name:
            raise ExecutionPlanError("Stage name must be a non-empty string")

        resource_class = _coerce_resource_class(request.resource_class)
        requested_device = _coerce_device(request.requested_device)
        gpu_available = request.gpu_available is True

        if requested_device is DeviceRequest.CPU:
            actual_device = DeviceRequest.CPU
            fallback_reason = None
        elif resource_class is ResourceClass.CPU:
            if requested_device is DeviceRequest.GPU:
                raise GpuUnavailableError(
                    f"Stage '{name}' explicitly requires GPU, but its resource class is CPU"
                )
            actual_device = DeviceRequest.CPU
            fallback_reason = "stage resource class is CPU-only"
        elif gpu_available:
            actual_device = DeviceRequest.GPU
            fallback_reason = None
        elif requested_device is DeviceRequest.GPU:
            raise GpuUnavailableError(
                f"Stage '{name}' explicitly requires GPU, but {resource_class.value} is unavailable"
            )
        else:
            actual_device = DeviceRequest.CPU
            fallback_reason = f"{resource_class.value} is unavailable"

        return cls(
            name=name,
            resource_class=resource_class,
            requested_device=requested_device,
            actual_device=actual_device,
            gpu_available=gpu_available,
            provider=request.provider,
            fallback_reason=fallback_reason,
        )


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    """Ordered, immutable resource plan for a run's execution stages."""

    stages: tuple[StagePlan, ...]

    @classmethod
    def resolve(cls, requests: Iterable[StageRequest]) -> "ExecutionPlan":
        """Resolve stages in order and reject duplicate stage names."""
        stages = tuple(StagePlan.resolve(request) for request in requests)
        names = tuple(stage.name for stage in stages)
        if len(names) != len(set(names)):
            raise ExecutionPlanError("Execution plan stage names must be unique")
        return cls(stages=stages)


def _coerce_device(value: DeviceRequest | str | None) -> DeviceRequest:
    if value is None:
        return DeviceRequest.CPU
    if isinstance(value, DeviceRequest):
        return value
    if isinstance(value, str):
        try:
            return DeviceRequest(value.strip().upper())
        except ValueError as exc:
            allowed = ", ".join(device.value for device in DeviceRequest)
            raise ExecutionPlanError(f"Device must be one of: {allowed}") from exc
    raise ExecutionPlanError("Device must be a string or DeviceRequest")


def _coerce_resource_class(value: ResourceClass | str) -> ResourceClass:
    if isinstance(value, ResourceClass):
        return value
    if isinstance(value, str):
        try:
            return ResourceClass(value.strip().lower())
        except ValueError as exc:
            allowed = ", ".join(resource.value for resource in ResourceClass)
            raise ExecutionPlanError(f"Resource class must be one of: {allowed}") from exc
    raise ExecutionPlanError("Resource class must be a string or ResourceClass")


__all__ = [
    "DeviceRequest",
    "ExecutionPlan",
    "ExecutionPlanError",
    "GpuUnavailableError",
    "ResourceClass",
    "StagePlan",
    "StageRequest",
]
