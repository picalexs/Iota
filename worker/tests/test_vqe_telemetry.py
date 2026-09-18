"""Tests for VQE objective bookkeeping and progress telemetry."""

from __future__ import annotations

import numpy as np
import pytest

from worker.chemistry.algorithms.vqe.telemetry import (
    FunctionEvaluationLimitReached,
    VQEObjectiveState,
)


def _build_state(
    evaluator,
    *,
    progress_callback=None,
    max_function_evaluations: int | None = None,
) -> VQEObjectiveState:
    return VQEObjectiveState(
        energy_evaluator=evaluator,
        progress_callback=progress_callback,
        ansatz_name="EfficientSU2",
        optimizer_name="COBYLA",
        optimizer_kind="scipy",
        max_iterations=4,
        max_function_evaluations=max_function_evaluations,
        parameter_count=2,
        num_qubits=1,
    )


def test_objective_state_tracks_best_point_and_emits_progress() -> None:
    progress_events: list[dict[str, object]] = []
    state = _build_state(
        lambda parameters: float(np.sum(parameters**2)),
        progress_callback=progress_events.append,
    )
    first_point = np.asarray([2.0, 0.0])
    second_point = np.asarray([0.5, 0.0])

    assert state(first_point) == pytest.approx(4.0)
    assert state(second_point) == pytest.approx(0.25)

    first_point[0] = 99.0
    assert state.evaluation_count == 2
    assert state.convergence_trace == pytest.approx([4.0, 0.25])
    assert state.best_energy == pytest.approx(0.25)
    assert state.best_point is not second_point
    assert state.best_point is not None
    assert state.best_point[0] == pytest.approx(0.5)
    assert [event["objective_evaluations"] for event in progress_events] == [1, 2]


def test_objective_state_stops_before_evaluator_after_cap() -> None:
    evaluations: list[np.ndarray] = []
    state = _build_state(
        lambda parameters: evaluations.append(parameters.copy()) or 1.0,
        max_function_evaluations=1,
    )

    state(np.asarray([0.0, 0.0]))
    with pytest.raises(FunctionEvaluationLimitReached, match="max_function_evaluations=1"):
        state(np.asarray([1.0, 1.0]))

    assert len(evaluations) == 1


def test_objective_state_counts_failed_evaluation_attempts() -> None:
    def failed_evaluator(_parameters: np.ndarray) -> float:
        raise RuntimeError("backend failed")

    state = _build_state(failed_evaluator)

    with pytest.raises(RuntimeError, match="backend failed"):
        state(np.asarray([0.0, 0.0]))

    assert state.evaluation_count == 0
    assert state.evaluation_attempt_count == 1
    assert state.evaluation_failure_count == 1
