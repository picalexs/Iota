"""Unit tests for pure SKQD configuration normalization."""

from __future__ import annotations

from worker.chemistry.algorithms.skqd import workflow as skqd_solver
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


def test_skqd_solver_keeps_legacy_configuration_aliases() -> None:
    assert skqd_solver._SKQDConfig is SKQDConfig
    assert skqd_solver._resolve_skqd_config is resolve_skqd_config
