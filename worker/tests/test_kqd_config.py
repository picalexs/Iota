"""Unit tests for pure KQD configuration normalization."""

from __future__ import annotations

import pytest

from worker.chemistry import kqd_solver
from worker.chemistry.algorithms.kqd.config import KQDConfig, resolve_kqd_config


def test_resolve_kqd_config_applies_defaults_and_bounds() -> None:
    result = resolve_kqd_config(
        {
            "krylov_dim": 99,
            "time_step": 0.25,
            "evolution_method": "TROTTER",
            "trotter_steps": 99,
            "residual_tolerance": 0.001,
        }
    )

    assert result == KQDConfig(
        krylov_dim=64,
        time_step=0.25,
        evolution_method="trotter",
        trotter_steps=32,
        residual_tolerance=0.001,
    )


def test_kqd_solver_keeps_legacy_configuration_aliases() -> None:
    assert kqd_solver._KQDConfig is KQDConfig
    assert kqd_solver._resolve_kqd_config is resolve_kqd_config


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("evolution_method", "unknown", "evolution_method"),
        ("time_step", 0.0, "time_step"),
        ("residual_tolerance", 0.0, "residual_tolerance"),
    ],
)
def test_kqd_rejects_invalid_runtime_semantics(field: str, value: object, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        resolve_kqd_config({field: value})
