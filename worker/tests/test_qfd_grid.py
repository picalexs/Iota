"""Tests for named QFD time-grid variants."""

import numpy as np
import pytest

from worker.chemistry.algorithms.qfd.grid import build_qfd_time_grid, qfd_grid_metadata


def test_original_qfd_grid_contains_symmetric_negative_and_positive_indices() -> None:
    grid = build_qfd_time_grid(
        qfd_variant="qfd_original_symmetric",
        num_time_points=5,
        max_time=1.0,
        time_grid_type="linear",
        kappa=2.0,
    )

    assert grid == pytest.approx(np.asarray([-2, -1, 0, 1, 2]) * np.pi)
    metadata = qfd_grid_metadata(grid, qfd_variant="qfd_original_symmetric", kappa=2.0)
    assert metadata["qfd_variant"] == "qfd_original_symmetric"
    assert metadata["grid_convention"] == "symmetric_kappa"
    assert len(metadata["time_grid_hash"]) == 64


def test_chemistry_forward_grid_keeps_existing_nonnegative_convention() -> None:
    grid = build_qfd_time_grid(
        qfd_variant="qfd_chemistry_forward",
        num_time_points=4,
        max_time=0.6,
        time_grid_type="linear",
        kappa=2.0,
    )

    assert grid == pytest.approx(np.linspace(0.0, 0.6, 4))


def test_qfd_grid_rejects_undefined_custom_variant() -> None:
    with pytest.raises(ValueError, match="unsupported QFD variant"):
        build_qfd_time_grid(
            qfd_variant="qfd_custom_grid",
            num_time_points=4,
            max_time=0.6,
            time_grid_type="linear",
            kappa=2.0,
        )
