"""Unit tests for pure SQD recovery convergence helpers."""

from __future__ import annotations

import numpy as np
import pytest

from worker.chemistry.algorithms.sqd import workflow as sqd_solver
from worker.chemistry.algorithms.sqd.convergence import (
    build_iteration_signature,
    compute_iteration_deltas,
    iteration_values_are_finite,
    is_iteration_converged,
    is_iteration_stalled,
)


def test_compute_iteration_deltas_marks_first_iteration_unbounded() -> None:
    energy_delta, occupancy_delta = compute_iteration_deltas(
        previous_energy=None,
        previous_occupancies=None,
        occupancy_vector=np.array([0.1, 0.2]),
        energy_value=-1.0,
    )

    assert np.isinf(energy_delta)
    assert np.isinf(occupancy_delta)


def test_compute_iteration_deltas_compares_energy_and_occupancies() -> None:
    energy_delta, occupancy_delta = compute_iteration_deltas(
        previous_energy=-1.0,
        previous_occupancies=np.array([0.1, 0.4]),
        occupancy_vector=np.array([0.3, 0.2]),
        energy_value=-1.25,
    )

    assert energy_delta == pytest.approx(0.25)
    assert occupancy_delta == pytest.approx(0.2)


@pytest.mark.parametrize(
    "values",
    [
        {"energy_value": np.nan, "delta_energy": 0.0, "occupancy_delta": 0.0},
        {"energy_value": -1.0, "delta_energy": np.inf, "occupancy_delta": 0.0},
        {"energy_value": -1.0, "delta_energy": 0.0, "occupancy_delta": np.nan},
    ],
)
def test_iteration_values_are_finite_rejects_invalid_scalars(
    values: dict[str, float],
) -> None:
    assert not iteration_values_are_finite(
        **values,
        occupancy_vector=np.asarray([1.0, 0.0]),
    )


def test_iteration_values_are_finite_rejects_invalid_occupancies() -> None:
    assert not iteration_values_are_finite(
        energy_value=-1.0,
        delta_energy=0.0,
        occupancy_delta=0.0,
        occupancy_vector=np.asarray([1.0, np.inf]),
    )


def test_iteration_values_are_finite_accepts_valid_inputs() -> None:
    assert iteration_values_are_finite(
        energy_value=-1.0,
        delta_energy=1e-6,
        occupancy_delta=1e-6,
        occupancy_vector=np.asarray([1.0, 0.0]),
    )


def test_iteration_values_are_finite_accepts_first_iteration_delta_sentinels() -> None:
    assert iteration_values_are_finite(
        energy_value=-1.0,
        delta_energy=float("inf"),
        occupancy_delta=float("inf"),
        occupancy_vector=np.asarray([1.0, 0.0]),
        deltas_available=False,
    )


@pytest.mark.parametrize(
    ("iteration", "energy_delta", "occupancy_delta", "selected_count", "expected"),
    [
        (1, 0.0, 0.0, 10, False),
        (2, 0.01, 0.0, 10, False),
        (2, 0.0, 0.01, 10, False),
        (2, np.nan, 0.0, 10, False),
        (2, 0.0, np.inf, 10, False),
        (2, 0.0, 0.0, 1, False),
        (2, 0.0, 0.0, 2, True),
    ],
)
def test_is_iteration_converged_applies_all_gates(
    iteration: int,
    energy_delta: float,
    occupancy_delta: float,
    selected_count: int,
    expected: bool,
) -> None:
    assert (
        is_iteration_converged(
            iteration=iteration,
            delta_energy=energy_delta,
            occupancy_delta=occupancy_delta,
            selected_count=selected_count,
            energy_tolerance=1e-3,
            occupancy_tolerance=1e-3,
            min_selected_configurations=2,
        )
        is expected
    )


def test_sqd_solver_keeps_legacy_delta_alias() -> None:
    assert sqd_solver._compute_iteration_deltas is compute_iteration_deltas


def test_sqd_solver_wrapper_uses_resolved_options_for_convergence() -> None:
    options = type(
        "Options",
        (),
        {"energy_tol": 1e-3, "occupancies_tol": 1e-3, "min_selected_configurations": 2},
    )()

    assert (
        sqd_solver._is_sqd_iteration_converged(
            iteration=2,
            delta_energy=1e-4,
            occupancy_delta=1e-4,
            selected_count=2,
            options=options,
        )
        is True
    )


def test_stalled_gate_requires_an_unchanged_selected_space() -> None:
    signature = build_iteration_signature(
        selected_distribution=[{"bitstring": "1010", "probability": 1.0}],
        selected_ci_summary={
            "selected_ci_strings_alpha": [2],
            "selected_ci_strings_beta": [2],
        },
        occupancy_vector=np.asarray([1.0, 0.0, 1.0, 0.0]),
        recovery_applied=False,
    )

    assert is_iteration_stalled(
        iteration=2,
        delta_energy=0.0,
        occupancy_delta=0.0,
        selected_count=1,
        min_selected_configurations=2,
        energy_tolerance=1e-6,
        occupancy_tolerance=1e-6,
        previous_signature=signature,
        current_signature=signature,
    )
    assert not is_iteration_stalled(
        iteration=2,
        delta_energy=0.0,
        occupancy_delta=0.0,
        selected_count=1,
        min_selected_configurations=2,
        energy_tolerance=1e-6,
        occupancy_tolerance=1e-6,
        previous_signature=signature,
        current_signature=("different",),
    )
