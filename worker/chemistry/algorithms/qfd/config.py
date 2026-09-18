"""Pure QFD configuration normalization for the algorithm package."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

from worker.chemistry.solver_utils import bounded_int

_SUPPORTED_QFD_VARIANTS = {
    "qfd_chemistry_forward",
    "qfd_original_symmetric",
    "qfd_custom_grid",
}


@dataclass(frozen=True)
class QFDConfig:
    """Resolved QFD time-grid and projected-solve options."""

    num_time_points: int
    max_time: float
    time_grid_type: str
    qfd_variant: str
    kappa: float
    trotter_steps: int
    residual_tolerance: float


def resolve_qfd_config(resolved: Mapping[str, Any]) -> QFDConfig:
    """Resolve user QFD options into bounded internal values."""
    num_time_points = bounded_int(
            resolved.get("num_time_points"),
            default=16,
            low=2,
            high=128,
        )
    raw_variant = str(resolved.get("qfd_variant", "qfd_chemistry_forward")).strip().lower()
    aliases = {
        "chemistry_forward": "qfd_chemistry_forward",
        "original_symmetric": "qfd_original_symmetric",
        "custom_grid": "qfd_custom_grid",
    }
    qfd_variant = aliases.get(raw_variant, raw_variant)
    if qfd_variant not in _SUPPORTED_QFD_VARIANTS:
        supported = ", ".join(sorted(_SUPPORTED_QFD_VARIANTS))
        raise ValueError(f"qfd_variant must be one of: {supported}")
    kappa = float(resolved.get("kappa") or resolved.get("spectral_scale") or 1.0)
    if not math.isfinite(kappa) or kappa <= 0.0:
        raise ValueError("QFD kappa must be finite and positive")
    if qfd_variant == "qfd_original_symmetric" and (
        num_time_points < 3 or num_time_points % 2 == 0
    ):
        raise ValueError("qfd_original_symmetric requires an odd num_time_points of at least 3")
    return QFDConfig(
        num_time_points=num_time_points,
        max_time=float(resolved.get("max_time") or 2.0),
        time_grid_type=str(resolved.get("time_grid_type", "linear")),
        qfd_variant=qfd_variant,
        kappa=kappa,
        trotter_steps=bounded_int(resolved.get("trotter_steps"), default=1, low=1, high=32),
        residual_tolerance=float(resolved.get("residual_tolerance") or 1e-6),
    )


__all__ = ["QFDConfig", "resolve_qfd_config"]
