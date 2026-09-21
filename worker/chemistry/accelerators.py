"""Optional GPU chemistry provider resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_CHEMISTRY_DEVICES = frozenset({"CPU", "GPU", "AUTO"})


@dataclass(frozen=True)
class AcceleratorResolution:
    """Requested and actual device information for one chemistry stage."""

    requested_device: str
    actual_device: str
    provider: str
    fallback_reason: str | None = None


def normalize_chemistry_device(value: Any) -> str:
    """Normalize a chemistry device request while preserving CPU compatibility."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return "CPU"
    if not isinstance(value, str) or value.strip().upper() not in _CHEMISTRY_DEVICES:
        allowed = ", ".join(sorted(_CHEMISTRY_DEVICES))
        raise ValueError(f"Chemistry device must be one of: {allowed}")
    return value.strip().upper()


def resolve_gpu4pyscf(device: Any) -> tuple[AcceleratorResolution, Any | None]:
    """Resolve the optional GPU4PySCF RHF provider without importing it on CPU runs."""
    requested = normalize_chemistry_device(device)
    if requested == "CPU":
        return AcceleratorResolution(requested, "CPU", "pyscf"), None

    try:
        from gpu4pyscf.scf import RHF as gpu_rhf
    except ImportError as exc:
        reason = "gpu4pyscf is not installed on this worker"
        if requested == "GPU":
            raise RuntimeError(
                "GPU chemistry was requested, but GPU4PySCF is not installed. "
                "Install the GPU chemistry worker dependencies or select CPU."
            ) from exc
        return AcceleratorResolution(requested, "CPU", "pyscf", reason), None

    return AcceleratorResolution(requested, "GPU", "gpu4pyscf"), gpu_rhf


def resolve_selected_ci_device(device: Any) -> str:
    """Normalize a selected-CI device request for the optional SBD adapter."""
    return normalize_chemistry_device(device)


__all__ = [
    "AcceleratorResolution",
    "normalize_chemistry_device",
    "resolve_gpu4pyscf",
    "resolve_selected_ci_device",
]
