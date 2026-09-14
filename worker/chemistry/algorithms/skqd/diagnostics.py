"""Pure prefix diagnostics for SKQD sampled Krylov states."""

from __future__ import annotations

from typing import Any

import numpy as np

from worker.chemistry.algorithms.skqd.sampling import SKQDSampleUnion


def build_skqd_prefix_summaries(
    sample_union: SKQDSampleUnion,
    *,
    num_elec_a: int,
    num_elec_b: int,
) -> list[dict[str, Any]]:
    """Summarize every sampled Krylov prefix without changing selected-CI inputs.

    ``selected_space_size`` is the count of unique raw determinants in the
    requested electron sector. It precedes configuration recovery and any
    selected-CI cap, so it remains a stable sampling diagnostic.
    """
    prefix_samples: list[np.ndarray] = []
    summaries: list[dict[str, Any]] = []
    width: int | None = None

    for dimension, sample in enumerate(sample_union.samples_by_state, start=1):
        matrix = np.asarray(sample.bitstring_matrix, dtype=bool)
        if matrix.ndim != 2 or matrix.shape[0] == 0:
            raise ValueError("SKQD prefix diagnostics require non-empty bitstring matrices")
        if matrix.shape[1] < 2 or matrix.shape[1] % 2 != 0:
            raise ValueError("SKQD prefix diagnostics require an even positive bitstring width")
        if width is None:
            width = int(matrix.shape[1])
        elif matrix.shape[1] != width:
            raise ValueError("SKQD prefix diagnostics require a consistent bitstring width")

        prefix_samples.append(matrix)
        prefix = np.concatenate(prefix_samples, axis=0)
        norb = prefix.shape[1] // 2
        valid_mask = np.logical_and(
            np.sum(prefix[:, norb:], axis=1) == num_elec_a,
            np.sum(prefix[:, :norb], axis=1) == num_elec_b,
        )
        valid_samples = prefix[valid_mask]
        summaries.append(
            {
                "krylov_dimension": dimension,
                "krylov_index": int(sample.krylov_index),
                "sample_count": int(prefix.shape[0]),
                "union_determinant_count": int(np.unique(prefix, axis=0).shape[0]),
                "valid_sector_mass": float(np.mean(valid_mask)),
                "selected_space_size": int(np.unique(valid_samples, axis=0).shape[0]),
                "selected_space_size_source": (
                    "unique_raw_valid_sector_determinants_before_recovery_and_ci_cap"
                ),
            }
        )
    return summaries


__all__ = ["build_skqd_prefix_summaries"]
