"""Pure QFD configuration normalization for the algorithm package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from worker.chemistry.solver_utils import bounded_int, positive_float

_SUPPORTED_QFD_VARIANTS = {
    "qfd_chemistry_forward",
    "qfd_original_symmetric",
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


def resolve_qfd_config(
    resolved: Mapping[str, Any],
    *,
    default_num_time_points: int = 16,
) -> QFDConfig:
    """Resolve user QFD options into bounded internal values."""
    num_time_points = bounded_int(
        resolved.get("num_time_points"),
        default=default_num_time_points,
        low=2,
        high=128,
    )
    raw_variant = str(resolved.get("qfd_variant", "qfd_chemistry_forward")).strip().lower()
    aliases = {
        "chemistry_forward": "qfd_chemistry_forward",
        "original_symmetric": "qfd_original_symmetric",
    }
    qfd_variant = aliases.get(raw_variant, raw_variant)
    if qfd_variant not in _SUPPORTED_QFD_VARIANTS:
        supported = ", ".join(sorted(_SUPPORTED_QFD_VARIANTS))
        raise ValueError(f"qfd_variant must be one of: {supported}")
    raw_kappa = resolved.get("kappa")
    if raw_kappa is None:
        raw_kappa = resolved.get("spectral_scale")
    kappa = positive_float(raw_kappa, default=1.0, name="QFD kappa")
    if qfd_variant == "qfd_original_symmetric" and (
        num_time_points < 3 or num_time_points % 2 == 0
    ):
        raise ValueError("qfd_original_symmetric requires an odd num_time_points of at least 3")
    time_grid_type = str(resolved.get("time_grid_type", "linear")).strip().lower()
    if time_grid_type not in {"linear", "geometric"}:
        raise ValueError("time_grid_type must be one of: geometric, linear")
    return QFDConfig(
        num_time_points=num_time_points,
        max_time=positive_float(resolved.get("max_time"), default=2.0, name="QFD max_time"),
        time_grid_type=time_grid_type,
        qfd_variant=qfd_variant,
        kappa=kappa,
        trotter_steps=bounded_int(resolved.get("trotter_steps"), default=1, low=1, high=32),
        residual_tolerance=positive_float(
            resolved.get("residual_tolerance"),
            default=1e-6,
            name="QFD residual_tolerance",
        ),
    )


__all__ = ["QFDConfig", "resolve_qfd_config"]
