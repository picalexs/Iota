"""Aer runtime capability discovery and device validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from worker.adapters.base import BackendExecutionContext
from worker.exceptions import BackendError

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
        return {
            "requested_device": normalized_requested,
            "device_source": "explicit" if requested_device is not None else "default",
            "actual_device": normalized_requested,
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


def aer_runtime_metadata(context: BackendExecutionContext) -> dict[str, Any]:
    """Return capability and requested/actual device metadata for a run."""
    info = validate_aer_runtime(context)
    return info.metadata(requested_device=context.backend_options.get("device"))


__all__ = [
    "GPU_AER_METHODS",
    "AerRuntimeInfo",
    "aer_runtime_metadata",
    "probe_aer_runtime",
    "validate_aer_method_for_device",
    "validate_aer_runtime",
]
