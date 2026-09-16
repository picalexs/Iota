"""Tests for backend option normalization."""

import math

import pytest

from worker.chemistry.backend_selector import build_backend_execution_context
from worker.exceptions import BackendError


def test_backend_context_preserves_requested_and_effective_measurement_settings() -> None:
    context = build_backend_execution_context(
        backend_target="aer_simulator",
        backend_options={"shots": 256, "estimator_precision": 0.125},
    )

    assert context.requested_shots == 256
    assert context.shots == 256
    assert context.requested_estimator_precision == 0.125
    assert context.estimator_precision == 0.125
    assert "estimator_precision" not in context.backend_options


def test_backend_context_replaces_invalid_legacy_precision_with_exact_default() -> None:
    context = build_backend_execution_context(
        backend_target="aer_simulator",
        backend_options={"estimator_precision": math.nan},
    )

    assert context.requested_estimator_precision is None
    assert context.estimator_precision == 0.0


def test_noisy_aer_derives_sampled_precision_from_shots() -> None:
    context = build_backend_execution_context(
        backend_target="aer_simulator",
        backend_options={"shots": 256},
        noise_profile={
            "source": "custom_preset",
            "preset": "depolarizing_cx",
            "strength": 0.01,
        },
    )

    assert context.requested_estimator_precision == 0.0625
    assert context.estimator_precision == 0.0625


def test_explicit_noisy_aer_precision_is_preserved() -> None:
    context = build_backend_execution_context(
        backend_target="aer_simulator",
        backend_options={"shots": 256, "estimator_precision": 0.125},
        noise_profile={
            "source": "custom_preset",
            "preset": "depolarizing_cx",
            "strength": 0.01,
        },
    )

    assert context.requested_estimator_precision == 0.125
    assert context.estimator_precision == 0.125


def test_backend_context_rejects_noise_for_statevector() -> None:
    with pytest.raises(BackendError, match="only supported for backend_target"):
        build_backend_execution_context(
            backend_target="statevector",
            noise_profile={
                "source": "custom_preset",
                "preset": "depolarizing_cx",
                "strength": 0.01,
            },
        )


def test_backend_context_rejects_invalid_noise_profile() -> None:
    with pytest.raises(BackendError, match="must be between 0 and 1"):
        build_backend_execution_context(
            backend_target="aer_simulator",
            noise_profile={
                "source": "custom_preset",
                "preset": "depolarizing_cx",
                "strength": 2.0,
            },
        )
