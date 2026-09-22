"""Unit tests for the pure worker execution-plan contract."""

from __future__ import annotations

import pytest

from worker.jobs.execution_plan import (
    DeviceRequest,
    ExecutionPlan,
    ExecutionPlanError,
    GpuUnavailableError,
    ResourceClass,
    StagePlan,
    StageRequest,
)


def test_resource_classes_and_device_requests_are_stable() -> None:
    assert [resource.value for resource in ResourceClass] == [
        "cpu",
        "aer_gpu",
        "chemistry_gpu",
        "sbd_gpu",
    ]
    assert [device.value for device in DeviceRequest] == ["CPU", "GPU", "AUTO"]


def test_cpu_request_resolves_to_cpu_without_fallback() -> None:
    plan = StagePlan.resolve(
        StageRequest(
            name="projected_solve",
            resource_class=ResourceClass.CPU,
            requested_device="CPU",
            gpu_available=True,
        )
    )

    assert plan.actual_device is DeviceRequest.CPU
    assert plan.fallback_reason is None
    assert plan.gpu_available is True


def test_gpu_request_resolves_when_the_required_capability_is_available() -> None:
    plan = StagePlan.resolve(
        StageRequest(
            name="state_generation",
            resource_class="aer_gpu",
            requested_device="GPU",
            gpu_available=True,
            provider="qiskit-aer",
        )
    )

    assert plan.resource_class is ResourceClass.AER_GPU
    assert plan.actual_device is DeviceRequest.GPU
    assert plan.provider == "qiskit-aer"
    assert plan.fallback_reason is None


@pytest.mark.parametrize(
    "resource_class",
    [
        ResourceClass.CPU,
        ResourceClass.AER_GPU,
        ResourceClass.CHEMISTRY_GPU,
        ResourceClass.SBD_GPU,
    ],
)
def test_explicit_gpu_fails_closed_when_the_stage_cannot_use_gpu(
    resource_class: ResourceClass,
) -> None:
    with pytest.raises(GpuUnavailableError, match="explicitly requires GPU"):
        StagePlan.resolve(
            StageRequest(
                name="stage",
                resource_class=resource_class,
                requested_device=DeviceRequest.GPU,
                gpu_available=False,
            )
        )


def test_auto_uses_gpu_when_available() -> None:
    plan = StagePlan.resolve(
        StageRequest(
            name="sampling",
            resource_class=ResourceClass.AER_GPU,
            requested_device=DeviceRequest.AUTO,
            gpu_available=True,
        )
    )

    assert plan.actual_device is DeviceRequest.GPU
    assert plan.fallback_reason is None


def test_auto_falls_back_to_cpu_with_a_reason() -> None:
    plan = StagePlan.resolve(
        StageRequest(
            name="selected_ci",
            resource_class=ResourceClass.SBD_GPU,
            requested_device=DeviceRequest.AUTO,
            gpu_available=False,
        )
    )

    assert plan.actual_device is DeviceRequest.CPU
    assert plan.fallback_reason == "sbd_gpu is unavailable"


def test_auto_records_cpu_only_reason() -> None:
    plan = StagePlan.resolve(
        StageRequest(
            name="finalize",
            resource_class=ResourceClass.CPU,
            requested_device=DeviceRequest.AUTO,
        )
    )

    assert plan.actual_device is DeviceRequest.CPU
    assert plan.fallback_reason == "stage resource class is CPU-only"


def test_execution_plan_preserves_order_and_rejects_duplicate_names() -> None:
    plan = ExecutionPlan.resolve(
        [
            StageRequest("reference_scf", ResourceClass.CHEMISTRY_GPU, "AUTO"),
            StageRequest("finalize", ResourceClass.CPU, "CPU"),
        ]
    )

    assert tuple(stage.name for stage in plan.stages) == ("reference_scf", "finalize")

    with pytest.raises(ExecutionPlanError, match="stage names must be unique"):
        ExecutionPlan.resolve(
            [
                StageRequest("duplicate", ResourceClass.CPU),
                StageRequest("duplicate", ResourceClass.CPU),
            ]
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [("name", "  "), ("resource_class", "not-a-resource"), ("requested_device", "MAYBE")],
)
def test_invalid_stage_request_fails_closed(field: str, value: str) -> None:
    request = StageRequest(
        name=value if field == "name" else "stage",
        resource_class=value if field == "resource_class" else ResourceClass.CPU,
        requested_device=value if field == "requested_device" else DeviceRequest.CPU,
    )

    with pytest.raises(ExecutionPlanError):
        StagePlan.resolve(request)
