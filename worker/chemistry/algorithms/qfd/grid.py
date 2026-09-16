"""Named QFD time-grid construction and provenance helpers."""

from __future__ import annotations

import hashlib

import numpy as np

from worker.chemistry.time_evolution import build_time_grid


def build_qfd_time_grid(
    *,
    qfd_variant: str,
    num_time_points: int,
    max_time: float,
    time_grid_type: str,
    kappa: float,
) -> np.ndarray:
    """Build a QFD grid under an explicit published-variant convention."""
    if qfd_variant == "qfd_original_symmetric":
        if num_time_points < 3 or num_time_points % 2 == 0:
            raise ValueError("qfd_original_symmetric requires an odd point count of at least 3")
        if kappa <= 0.0 or not np.isfinite(kappa):
            raise ValueError("qfd_original_symmetric requires positive finite kappa")
        kmax = (num_time_points - 1) // 2
        indices = np.arange(-kmax, kmax + 1, dtype=float)
        return 2.0 * np.pi * indices / float(kappa)
    if qfd_variant != "qfd_chemistry_forward":
        raise ValueError(f"unsupported QFD variant: {qfd_variant}")
    return build_time_grid(
        num_time_points=num_time_points,
        max_time=max_time,
        grid_type=time_grid_type,
    )


def qfd_grid_metadata(time_grid: np.ndarray, *, qfd_variant: str, kappa: float) -> dict[str, object]:
    """Return serializable grid values and a stable provenance hash."""
    grid = np.asarray(time_grid, dtype=np.float64)
    digest = hashlib.sha256(grid.tobytes()).hexdigest()
    return {
        "qfd_variant": qfd_variant,
        "grid_convention": (
            "symmetric_kappa" if qfd_variant == "qfd_original_symmetric" else "forward"
        ),
        "kappa": float(kappa),
        "time_grid_values": [float(value) for value in grid],
        "time_grid_hash": digest,
    }


__all__ = ["build_qfd_time_grid", "qfd_grid_metadata"]
