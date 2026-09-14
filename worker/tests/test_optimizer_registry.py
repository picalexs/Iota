"""Tests for VQE optimizer registry behavior."""

import pytest

from worker.chemistry.optimizer_registry import build_optimizer, supported_optimizers


def test_supported_optimizers_contains_phase2_set() -> None:
    assert supported_optimizers() == {"COBYLA", "SPSA", "SLSQP", "L_BFGS_B"}


def test_build_optimizer_accepts_supported_name() -> None:
    optimizer = build_optimizer(
        optimizer_name="cobyla",
        max_iterations=5,
        minimum_iterations=12,
    )

    assert optimizer.name == "COBYLA"
    assert optimizer.kind == "scipy"
    assert optimizer.scipy_method == "COBYLA"
    assert optimizer.max_iterations == 12
    assert optimizer.options == {"maxiter": 12}


def test_build_optimizer_stores_function_evaluation_cap_for_runtime_stop() -> None:
    optimizer = build_optimizer(
        optimizer_name="COBYLA",
        max_iterations=5,
        max_function_evaluations=9,
    )

    assert optimizer.max_function_evaluations == 9
    assert optimizer.options == {"maxiter": 5}


def test_build_optimizer_passes_native_maxfun_when_supported() -> None:
    optimizer = build_optimizer(
        optimizer_name="L_BFGS_B",
        max_iterations=5,
        max_function_evaluations=9,
    )

    assert optimizer.max_function_evaluations == 9
    assert optimizer.options == {"maxiter": 5, "maxfun": 9}


def test_build_optimizer_rejects_unknown_name() -> None:
    with pytest.raises(ValueError, match="Unsupported optimizer"):
        build_optimizer(optimizer_name="Unknown", max_iterations=5)
