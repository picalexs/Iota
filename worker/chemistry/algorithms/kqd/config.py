"""Pure KQD configuration normalization for the algorithm package."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

from worker.chemistry.solver_utils import bounded_int


@dataclass(frozen=True)
class KQDConfig:
    """Resolved KQD options used by projected time-evolution paths."""

    krylov_dim: int
    time_step: float
    evolution_method: str
    trotter_steps: int
    residual_tolerance: float


def resolve_kqd_config(resolved: Mapping[str, Any]) -> KQDConfig:
    """Resolve user KQD options into bounded internal values."""
    raw_time_step = resolved.get("time_step", 0.1)
    time_step = float(0.1 if raw_time_step is None else raw_time_step)
    if not math.isfinite(time_step) or time_step <= 0.0:
        raise ValueError("KQD time_step must be finite and positive")
    evolution_method = str(resolved.get("evolution_method", "exact")).lower()
    if evolution_method not in {"exact", "trotter"}:
        raise ValueError("KQD evolution_method must be 'exact' or 'trotter'")
    raw_residual_tolerance = resolved.get("residual_tolerance", 1e-8)
    residual_tolerance = float(
        1e-8 if raw_residual_tolerance is None else raw_residual_tolerance
    )
    if not math.isfinite(residual_tolerance) or residual_tolerance <= 0.0:
        raise ValueError("KQD residual_tolerance must be finite and positive")
    return KQDConfig(
        krylov_dim=bounded_int(resolved.get("krylov_dim"), default=12, low=2, high=64),
        time_step=time_step,
        evolution_method=evolution_method,
        trotter_steps=bounded_int(resolved.get("trotter_steps"), default=4, low=1, high=32),
        residual_tolerance=residual_tolerance,
    )


__all__ = ["KQDConfig", "resolve_kqd_config"]
