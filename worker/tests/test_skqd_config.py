"""Unit tests for pure SKQD configuration normalization."""

from __future__ import annotations

import pytest

from worker.chemistry.algorithms.skqd.config import SKQDConfig, resolve_skqd_config


def test_resolve_skqd_config_applies_defaults_and_nested_sqd_algorithm() -> None:
    result = resolve_skqd_config(
        {
            "krylov_extension_dim": 99,
            "residual_tolerance": 0.25,
            "krylov_time_step": 0.4,
            "base_sampling_options": {"max_iterations": 12},
        }
    )

    assert result == SKQDConfig(
        krylov_extension_dim=32,
        residual_tolerance=0.25,
        sampling_time_step=0.4,
        time_step_policy="explicit_user_time_step",
        sampling_mode="sample_union_exact",
        samples_per_state=512,
        seed=42,
        trotter_steps=1,
        trotter_order=2,
        sqd_config={
            "algorithm": "sqd",
            "samples_per_batch": 1,
            "num_batches": 1,
            "max_iterations": 12,
            "energy_tol": 1e-5,
            "occupancies_tol": 1e-5,
            "carryover_threshold": 0.0,
        },
    )


def test_resolve_skqd_config_accepts_explicit_legacy_extension_mode() -> None:
    result = resolve_skqd_config(
        {
            "sampling_mode": "legacy_statevector_extension",
            "samples_per_state": 24,
            "seed": 7,
        }
    )

    assert result.sampling_mode == "legacy_statevector_extension"
    assert result.samples_per_state == 24
    assert result.seed == 7


def test_resolve_skqd_config_normalizes_explicit_sample_union_mode() -> None:
    result = resolve_skqd_config({"sampling_mode": " SAMPLE_UNION_EXACT "})

    assert result.sampling_mode == "sample_union_exact"


@pytest.mark.parametrize("samples_per_state", [2048, 4096])
def test_resolve_skqd_config_preserves_public_samples_per_state_limit(
    samples_per_state: int,
) -> None:
    result = resolve_skqd_config({"samples_per_state": samples_per_state})

    assert result.samples_per_state == samples_per_state


@pytest.mark.parametrize("field", ["time_step", "residual_tolerance"])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_resolve_skqd_config_rejects_non_finite_float_options(
    field: str,
    value: float,
) -> None:
    with pytest.raises(ValueError, match="finite"):
        resolve_skqd_config({field: value})


def test_resolve_skqd_config_rejects_explicit_zero_time_step() -> None:
    with pytest.raises(ValueError, match="positive"):
        resolve_skqd_config({"time_step": 0.0})
