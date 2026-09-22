"""Tests for Aer runtime capability and GPU method validation."""

from types import SimpleNamespace

import pytest

from worker.adapters.base import BackendExecutionContext
from worker.chemistry.aer_runtime import (
    AerRuntimeInfo,
    extract_aer_result_metadata,
    validate_aer_method_for_device,
    validate_aer_runtime,
)
from worker.exceptions import BackendError


def _gpu_info() -> AerRuntimeInfo:
    return AerRuntimeInfo(aer_version="0.17.2", available_devices=("CPU", "GPU"))


def test_gpu_runtime_requires_a_gpu_device() -> None:
    context = BackendExecutionContext(
        backend_target="aer_simulator",
        backend_options={"device": "GPU"},
        simulator_method="statevector",
    )

    with pytest.raises(BackendError, match="no GPU device"):
        validate_aer_runtime(
            context,
            runtime_info=AerRuntimeInfo(aer_version="0.17.2", available_devices=("CPU",)),
        )


def test_gpu_runtime_metadata_distinguishes_requested_and_actual_device() -> None:
    info = _gpu_info()

    assert info.metadata(requested_device="GPU") == {
        "requested_device": "GPU",
        "device_source": "explicit",
        "actual_device": None,
        "device_verified": False,
        "available_devices": ["CPU", "GPU"],
        "gpu_available": True,
        "aer_version": "0.17.2",
        "aer_preflight": "passed",
    }


@pytest.mark.parametrize("method", ["automatic", "matrix_product_state", "stabilizer"])
def test_gpu_runtime_requires_gpu_supported_explicit_method(method: str) -> None:
    with pytest.raises(BackendError, match="explicit Aer method"):
        validate_aer_method_for_device(device="GPU", method=method)


def test_cpu_runtime_keeps_default_device_metadata() -> None:
    info = AerRuntimeInfo(aer_version="0.17.2", available_devices=("CPU",))

    assert info.metadata(requested_device=None)["actual_device"] == "CPU"


def test_extract_aer_result_metadata_keeps_aggregate_and_experiment_facts() -> None:
    result = SimpleNamespace(
        metadata={"time_taken_execute": 0.25, "max_gpu_memory_mb": 12},
        results=[
            SimpleNamespace(
                metadata={"method": "statevector", "device": "GPU", "num_qubits": 4}
            )
        ],
    )

    assert extract_aer_result_metadata(result) == {
        "aer_result_metadata": {"time_taken_execute": 0.25, "max_gpu_memory_mb": 12},
        "aer_experiment_metadata": {
            "method": "statevector",
            "device": "GPU",
            "num_qubits": 4,
        },
        "actual_device": "GPU",
        "device_verified": True,
    }


def test_extract_aer_result_metadata_allows_missing_metadata() -> None:
    assert extract_aer_result_metadata(SimpleNamespace()) == {}
