"""Pure QSE configuration normalization for the algorithm package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from worker.chemistry.solver_utils import bounded_int, nonnegative_float, positive_float


@dataclass(frozen=True)
class QSEConfig:
    """Resolved QSE reference, excitation, and projected-solve options."""

    max_subspace_dim: int
    regularization: float
    overlap_threshold: float
    residual_tolerance: float
    excitation_level: str
    reference_method: str


def resolve_qse_config(resolved: Mapping[str, Any]) -> QSEConfig:
    """Resolve user QSE options into bounded internal values."""
    excitation_level = str(resolved.get("excitation_level", "singles")).lower()
    if excitation_level not in {"singles", "singles_doubles"}:
        raise ValueError(
            f"Unsupported QSE excitation_level '{excitation_level}'. "
            "Supported: singles, singles_doubles"
        )
    return QSEConfig(
        max_subspace_dim=bounded_int(
            resolved.get("max_subspace_dim"),
            default=8,
            low=1,
            high=96,
        ),
        regularization=positive_float(
            resolved.get("regularization"),
            default=1e-8,
            name="QSE regularization",
        ),
        overlap_threshold=nonnegative_float(
            resolved.get("overlap_threshold"),
            default=1e-8,
            name="QSE overlap_threshold",
        ),
        residual_tolerance=positive_float(
            resolved.get("residual_tolerance"),
            default=1e-8,
            name="QSE residual_tolerance",
        ),
        excitation_level=excitation_level,
        reference_method=str(resolved.get("reference_method", "vqe")).lower(),
    )


__all__ = ["QSEConfig", "resolve_qse_config"]
