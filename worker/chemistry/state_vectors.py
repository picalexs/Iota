"""Pure state-vector normalization helpers for worker chemistry solvers."""

from __future__ import annotations

import numpy as np


def normalize_state_vector(
    state: np.ndarray,
    *,
    error_message: str,
    expected_size: int | None = None,
) -> np.ndarray:
    """Flatten and normalize a non-zero state vector at a solver boundary."""
    vector = np.asarray(state, dtype=complex).reshape(-1)
    if expected_size is not None and vector.size != expected_size:
        raise ValueError("state vector dimension does not match the expected size")
    norm = float(np.linalg.norm(vector))
    if not np.isfinite(norm) or norm == 0.0:
        raise ValueError(error_message)
    return vector / norm


__all__ = ["normalize_state_vector"]
