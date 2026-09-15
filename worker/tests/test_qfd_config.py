"""Unit tests for pure QFD configuration normalization."""

from __future__ import annotations

import pytest

from worker.chemistry import qfd_solver
from worker.chemistry.algorithms.qfd.config import QFDConfig, resolve_qfd_config


def test_resolve_qfd_config_applies_defaults_and_bounds() -> None:
    result = resolve_qfd_config(
        {
            "num_time_points": 999,
            "max_time": 3.5,
            "time_grid_type": "geometric",
            "trotter_steps": 99,
            "residual_tolerance": 0.001,
        }
    )

    assert result == QFDConfig(
        num_time_points=128,
        max_time=3.5,
        time_grid_type="geometric",
        qfd_variant="qfd_chemistry_forward",
        kappa=1.0,
        trotter_steps=32,
        residual_tolerance=0.001,
    )


def test_resolve_qfd_config_validates_original_symmetric_grid() -> None:
    result = resolve_qfd_config(
        {
            "num_time_points": 5,
            "max_time": 1.0,
            "qfd_variant": "qfd_original_symmetric",
            "kappa": 2.0,
        }
    )

    assert result.qfd_variant == "qfd_original_symmetric"
    assert result.kappa == 2.0


def test_resolve_qfd_config_rejects_even_original_grid() -> None:
    import pytest

    with pytest.raises(ValueError, match="odd num_time_points"):
        resolve_qfd_config(
            {
                "num_time_points": 4,
                "qfd_variant": "qfd_original_symmetric",
                "kappa": 2.0,
            }
        )


def test_qfd_solver_exposes_the_resolved_config_boundary() -> None:
    assert qfd_solver.QFDConfig is QFDConfig
    assert qfd_solver.resolve_qfd_config is resolve_qfd_config


@pytest.mark.parametrize("field", ["kappa", "max_time", "residual_tolerance"])
def test_resolve_qfd_config_rejects_explicit_non_positive_values(field: str) -> None:
    with pytest.raises(ValueError, match="finite and positive"):
        resolve_qfd_config({field: 0})
