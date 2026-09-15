"""Pure KQD configuration normalization for the algorithm package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from worker.chemistry.solver_utils import bounded_int, positive_float


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
    time_step = positive_float(resolved.get("time_step"), default=0.1, name="KQD time_step")
    evolution_method = str(resolved.get("evolution_method", "exact")).lower()
    if evolution_method not in {"exact", "trotter"}:
        raise ValueError("KQD evolution_method must be 'exact' or 'trotter'")
    residual_tolerance = positive_float(
        resolved.get("residual_tolerance"),
        default=1e-8,
        name="KQD residual_tolerance",
    )
    return KQDConfig(
        krylov_dim=bounded_int(resolved.get("krylov_dim"), default=12, low=2, high=64),
        time_step=time_step,
        evolution_method=evolution_method,
        trotter_steps=bounded_int(resolved.get("trotter_steps"), default=4, low=1, high=32),
        residual_tolerance=residual_tolerance,
    )


__all__ = ["KQDConfig", "resolve_kqd_config"]
