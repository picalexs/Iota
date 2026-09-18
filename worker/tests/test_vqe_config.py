"""Unit tests for pure VQE configuration normalization."""

from __future__ import annotations

import pytest

from worker.chemistry.algorithms.vqe.config import (
    VQEConfig,
    bounded_optional_positive_int,
    positive_float_or_default,
    resolve_parameter_bounds,
    resolve_vqe_config,
    select_vqe_optimizer_name,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, None), (True, None), (0, None), (-2, None), (3.9, 3), (999, 10)],
)
def test_bounded_optional_positive_int(value: object, expected: int | None) -> None:
    assert bounded_optional_positive_int(value, high=10) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, 0.5), (True, 0.5), (0, 0.5), (-1.0, 0.5), (2, 2.0)],
)
def test_positive_float_or_default(value: object, expected: float) -> None:
    assert positive_float_or_default(value, default=0.5) == pytest.approx(expected)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_vqe_float_helpers_reject_non_finite_values(value: float) -> None:
    assert bounded_optional_positive_int(value, high=10) is None
    assert positive_float_or_default(value, default=0.5) == pytest.approx(0.5)


def test_resolve_parameter_bounds_normalizes_numeric_pairs() -> None:
    assert resolve_parameter_bounds(
        {"parameter_bounds": [[0, 1], (-2.5, 3)]},
        num_parameters=2,
    ) == [(0.0, 1.0), (-2.5, 3.0)]


@pytest.mark.parametrize(
    ("config", "num_parameters", "message"),
    [
        ({"parameter_bounds": "invalid"}, 1, "must be a list"),
        ({"parameter_bounds": [[0, 1]]}, 2, "exactly 2"),
        ({"parameter_bounds": [[0]]}, 1, "numeric"),
        ({"parameter_bounds": [[2, 1]]}, 1, "cannot exceed"),
        ({"parameter_bounds": [[float("nan"), 1]]}, 1, "must be finite"),
        ({"parameter_bounds": [[float("inf"), 1]]}, 1, "must be finite"),
    ],
)
def test_resolve_parameter_bounds_rejects_invalid_values(
    config: dict[str, object],
    num_parameters: int,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        resolve_parameter_bounds(config, num_parameters=num_parameters)


def test_resolve_vqe_config_applies_defaults_and_caps() -> None:
    result = resolve_vqe_config(
        {
            "max_iterations": 9999,
            "optimizer": "SPSA",
            "ansatz": "TwoLocal",
            "optimizer_options": {"maxfun": 12},
            "convergence_threshold": 0.25,
            "reps": 99,
        }
    )

    assert result == VQEConfig(
        max_iterations=5000,
        optimizer_name="SPSA",
        ansatz_name="TwoLocal",
        optimizer_options={"maxfun": 12},
        seed=42,
        convergence_threshold=0.25,
        max_function_evaluations=12,
        reps=6,
        optimizer_policy="explicit",
    )


def test_resolve_vqe_config_defaults_non_finite_integer_options() -> None:
    result = resolve_vqe_config({"max_iterations": float("nan"), "reps": float("inf")})

    assert result.max_iterations == 500
    assert result.reps == 2


def test_resolve_vqe_config_prefers_explicit_function_limit() -> None:
    result = resolve_vqe_config(
        {"max_function_evaluations": 4, "optimizer_options": {"maxfun": 12}}
    )

    assert result.max_function_evaluations == 4


def test_select_vqe_optimizer_uses_spsa_only_for_requested_noisy_policy() -> None:
    assert select_vqe_optimizer_name(
        {"optimizer_policy": "noise_aware_auto"},
        optimizer_policy="noise_aware_auto",
        backend_target="aer_simulator",
        noise_profile={"source": "custom_preset"},
    ) == ("SPSA", "noise_aware_auto")


def test_select_vqe_optimizer_preserves_explicit_choice() -> None:
    assert select_vqe_optimizer_name(
        {"optimizer_name": "COBYLA", "optimizer_policy": "noise_aware_auto"},
        optimizer_policy="noise_aware_auto",
        backend_target="ibm_runtime",
        noise_profile=None,
    ) == ("COBYLA", "explicit")
