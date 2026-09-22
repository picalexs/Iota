"""Aer runtime capability discovery and device validation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from worker.exceptions import BackendError

if TYPE_CHECKING:
    from worker.adapters.base import BackendExecutionContext

GPU_AER_METHODS = frozenset({"statevector", "density_matrix", "unitary"})


@dataclass(frozen=True)
class AerRuntimeInfo:
    """Runtime facts reported by the installed Qiskit Aer package."""

    aer_version: str | None
    available_devices: tuple[str, ...]

    @property
    def gpu_available(self) -> bool:
        return "GPU" in self.available_devices

    def metadata(self, *, requested_device: str | None) -> dict[str, Any]:
        normalized_requested = _normalize_device(requested_device)
        # Device discovery proves that a requested GPU is available. It does
        # not prove that a later simulator job used that GPU. Keep that fact
        # separate until Aer returns experiment metadata.
        preflight_actual = "CPU" if normalized_requested == "CPU" else None
        return {
            "requested_device": normalized_requested,
            "device_source": "explicit" if requested_device is not None else "default",
            "actual_device": preflight_actual,
            "device_verified": preflight_actual is not None,
            "available_devices": list(self.available_devices),
            "gpu_available": self.gpu_available,
            "aer_version": self.aer_version,
            "aer_preflight": "passed",
        }


def _normalize_device(value: str | None) -> str:
    if isinstance(value, str) and value.strip().upper() == "GPU":
        return "GPU"
    return "CPU"


def _load_aer_runtime() -> tuple[Any, Any]:
    try:
        import qiskit_aer
        from qiskit_aer import AerSimulator
    except Exception as exc:  # pragma: no cover - depends on the worker image
        raise BackendError(f"Qiskit Aer is not available in this worker: {exc}") from exc
    return qiskit_aer, AerSimulator


def probe_aer_runtime() -> AerRuntimeInfo:
    """Inspect the installed Aer package without creating a simulator job."""
    aer_module, simulator_class = _load_aer_runtime()
    try:
        raw_devices = simulator_class().available_devices()
    except Exception as exc:
        raise BackendError(f"Aer device discovery failed: {exc}") from exc

    devices = tuple(sorted({str(device).strip().upper() for device in raw_devices if device}))
    version = getattr(aer_module, "__version__", None)
    return AerRuntimeInfo(
        aer_version=str(version) if version else None,
        available_devices=devices,
    )


def validate_aer_runtime(
    context: BackendExecutionContext,
    *,
    runtime_info: AerRuntimeInfo | None = None,
) -> AerRuntimeInfo:
    """Require the requested Aer device before a primitive can be created."""
    info = runtime_info or probe_aer_runtime()
    requested_device = context.backend_options.get("device")
    if _normalize_device(requested_device) == "GPU" and not info.gpu_available:
        available = ", ".join(info.available_devices) or "none"
        raise BackendError(
            "GPU execution was requested, but this Aer worker has no GPU device "
            f"(available devices: {available}). Use CPU or start a GPU-enabled worker."
        )
    return info


def validate_aer_method_for_device(*, device: str | None, method: str) -> None:
    """Reject GPU requests that use a method Aer cannot execute on GPU."""
    if _normalize_device(device) != "GPU":
        return
    if method not in GPU_AER_METHODS:
        supported = ", ".join(sorted(GPU_AER_METHODS))
        raise BackendError(
            f"GPU execution requires an explicit Aer method supported by GPU: {supported}."
        )


def extract_aer_result_metadata(result: Any, *, experiment_index: int = 0) -> dict[str, Any]:
    """Extract result and experiment metadata without inferring device use.

    Aer exposes aggregate timing/runtime facts on ``Result.metadata`` and
    simulator details, including the actual device, on the selected result
    entry. Missing metadata is valid for test doubles and older result shapes.
    """
    captured: dict[str, Any] = {}
    result_metadata = _metadata_mapping(getattr(result, "metadata", None))
    if result_metadata:
        captured["aer_result_metadata"] = result_metadata

    experiment_metadata: dict[str, Any] = {}
    results = getattr(result, "results", None)
    if isinstance(results, (list, tuple)) and 0 <= experiment_index < len(results):
        experiment_metadata = _metadata_mapping(
            getattr(results[experiment_index], "metadata", None)
        )
    if experiment_metadata:
        captured["aer_experiment_metadata"] = experiment_metadata
        actual_device = _observed_device(experiment_metadata.get("device"))
        if actual_device is not None:
            captured["actual_device"] = actual_device
            captured["device_verified"] = True
    return captured


def _metadata_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return dict(value)


def _observed_device(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().upper()
    return normalized if normalized in {"CPU", "GPU"} else None


def aer_runtime_metadata(context: BackendExecutionContext) -> dict[str, Any]:
    """Return capability and requested/actual device metadata for a run."""
    info = validate_aer_runtime(context)
    return info.metadata(requested_device=context.backend_options.get("device"))


__all__ = [
    "GPU_AER_METHODS",
    "AerRuntimeInfo",
    "aer_runtime_metadata",
    "extract_aer_result_metadata",
    "probe_aer_runtime",
    "validate_aer_method_for_device",
    "validate_aer_runtime",
]
