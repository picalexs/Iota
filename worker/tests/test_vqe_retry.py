from types import SimpleNamespace

import numpy as np

from worker.chemistry.optimizer_registry import OptimizerConfig
from worker.chemistry.algorithms.vqe.retry import (
    run_scipy_vqe_with_retry,
    should_retry_stationary_warm_start,
    warm_start_retry_indices,
)


def test_should_retry_stationary_warm_start_requires_an_alternate_gradient_start() -> None:
    optimizer = SimpleNamespace(scipy_method="L-BFGS-B")
    candidate_points = [np.zeros(2), np.ones(2)]

    assert should_retry_stationary_warm_start(
        optimizer=optimizer,
        initial_point=candidate_points[0],
        candidate_points=candidate_points,
        converged=True,
        optimizer_diagnostics={"optimizer_iterations": 0},
    )
    assert not should_retry_stationary_warm_start(
        optimizer=SimpleNamespace(scipy_method="COBYLA"),
        initial_point=candidate_points[0],
        candidate_points=candidate_points,
        converged=True,
        optimizer_diagnostics={"optimizer_iterations": 0},
    )
    assert should_retry_stationary_warm_start(
        optimizer=optimizer,
        initial_point=candidate_points[0],
        candidate_points=candidate_points,
        converged=True,
        optimizer_diagnostics={"optimizer_iterations": None},
    )


def test_unknown_initial_iteration_count_skips_retry_and_reports_reason() -> None:
    point = np.zeros(1)
    objective = SimpleNamespace(best_energy=0.0, best_point=point)
    calls = []

    def run_optimizer(**_kwargs):
        calls.append(True)
        return point, 0.0, 1, True, {"optimizer_iterations": None}

    result = run_scipy_vqe_with_retry(
        objective=objective,
        initial_point=point,
        optimizer=SimpleNamespace(scipy_method="L-BFGS-B"),
        optimizer_diagnostics={},
        convergence_trace=[0.0],
        parameter_bounds=None,
        candidate_points=[point, np.ones(1)],
        selected_initial_diagnostics={"initial_point_best_index": 0},
        run_optimizer_fn=run_optimizer,
    )

    assert calls == [True]
    assert result[3] is False
    assert result[4]["termination_reason"] == "optimizer_iteration_count_unavailable"
    assert (
        result[4]["warm_start_retry_skipped_reason"]
        == "optimizer_iteration_count_unavailable"
    )
    assert result[4]["warm_start_retry_count"] == 0


def test_warm_start_retry_indices_order_alternates_by_candidate_energy() -> None:
    candidates = [np.zeros(1), np.ones(1), np.full(1, 2.0)]

    assert warm_start_retry_indices(
        candidate_points=candidates,
        selected_initial_diagnostics={
            "initial_point_best_index": 0,
            "initial_point_candidate_energies": [0.0, -2.0, -1.0],
        },
    ) == [1, 2]


def test_run_scipy_vqe_with_retry_uses_an_improving_alternate_start() -> None:
    class _Objective:
        best_energy = 0.0
        best_point = np.zeros(1)

    objective = _Objective()
    calls: list[np.ndarray] = []

    def run_optimizer(**kwargs):
        point = np.asarray(kwargs["initial_point"], dtype=float)
        calls.append(point.copy())
        if np.allclose(point, 0.0):
            return point, 0.0, 0, True, {"optimizer_iterations": 0}
        objective.best_energy = -1.0
        objective.best_point = point
        return point, -1.0, 2, True, {"optimizer_iterations": 2}

    result = run_scipy_vqe_with_retry(
        objective=objective,
        initial_point=np.zeros(1),
        optimizer=SimpleNamespace(scipy_method="L-BFGS-B"),
        optimizer_diagnostics={},
        convergence_trace=[0.0],
        parameter_bounds=None,
        candidate_points=[np.zeros(1), np.ones(1)],
        selected_initial_diagnostics={
            "initial_point_best_index": 0,
            "initial_point_candidate_energies": [0.0, 1.0],
        },
        run_optimizer_fn=run_optimizer,
    )

    assert calls == [np.zeros(1), np.ones(1)]
    assert result[1:4] == (-1.0, 2, True)
    assert result[4]["warm_start_retry_selected_index"] == 1


def test_stationary_retries_share_the_total_optimizer_iteration_budget() -> None:
    class _Objective:
        best_energy = 0.0
        best_point = np.zeros(1)

    objective = _Objective()
    optimizer = OptimizerConfig(
        name="L_BFGS_B",
        kind="scipy",
        max_iterations=4,
        scipy_method="L-BFGS-B",
        options={"maxiter": 4},
    )
    candidates = [np.zeros(1), np.ones(1), np.full(1, 2.0)]
    attempts: list[tuple[float, int, int]] = []

    def run_optimizer(**kwargs):
        point = np.asarray(kwargs["initial_point"], dtype=float)
        received_optimizer = kwargs["optimizer"]
        attempts.append(
            (
                float(point[0]),
                received_optimizer.max_iterations,
                received_optimizer.options["maxiter"],
            )
        )
        if np.allclose(point, 0.0):
            return point, 0.0, 1, True, {"optimizer_iterations": 0}
        if np.allclose(point, 2.0):
            return point, 0.1, 3, False, {"optimizer_iterations": 3}

        objective.best_energy = -1.0
        objective.best_point = point
        return point, -1.0, 1, True, {"optimizer_iterations": 1}

    result = run_scipy_vqe_with_retry(
        objective=objective,
        initial_point=candidates[0],
        optimizer=optimizer,
        optimizer_diagnostics={},
        convergence_trace=[0.0],
        parameter_bounds=None,
        candidate_points=candidates,
        selected_initial_diagnostics={
            "initial_point_best_index": 0,
            "initial_point_candidate_energies": [0.0, 2.0, 1.0],
        },
        run_optimizer_fn=run_optimizer,
    )

    assert attempts == [(0.0, 4, 4), (2.0, 4, 4), (1.0, 1, 1)]
    assert result[1:4] == (-1.0, 1, True)
    assert result[4]["optimizer_iterations"] == 4
    assert result[4]["optimizer_iterations_total"] == 4
    assert result[4]["optimizer_iterations_by_attempt"] == [0, 3, 1]
    assert result[4]["selected_optimizer_iterations"] == 1
    assert result[4]["warm_start_retry_count"] == 2


def test_stationary_retry_reports_total_iteration_exhaustion() -> None:
    class _Objective:
        best_energy = 0.0
        best_point = np.zeros(1)

    objective = _Objective()
    optimizer = OptimizerConfig(
        name="L_BFGS_B",
        kind="scipy",
        max_iterations=4,
        scipy_method="L-BFGS-B",
        options={"maxiter": 4},
    )

    def run_optimizer(**kwargs):
        point = np.asarray(kwargs["initial_point"], dtype=float)
        if np.allclose(point, 0.0):
            return point, 0.0, 1, True, {"optimizer_iterations": 0}
        assert kwargs["optimizer"].options["maxiter"] == 4
        return point, 0.1, 4, False, {"optimizer_iterations": 4}

    result = run_scipy_vqe_with_retry(
        objective=objective,
        initial_point=np.zeros(1),
        optimizer=optimizer,
        optimizer_diagnostics={},
        convergence_trace=[0.0],
        parameter_bounds=None,
        candidate_points=[np.zeros(1), np.ones(1), np.full(1, 2.0)],
        selected_initial_diagnostics={
            "initial_point_best_index": 0,
            "initial_point_candidate_energies": [0.0, 1.0, 2.0],
        },
        run_optimizer_fn=run_optimizer,
    )

    assert result[3] is False
    assert result[4]["termination_reason"] == "max_iterations"
    assert result[4]["optimizer_iterations"] == 4
    assert result[4]["optimizer_iterations_by_attempt"] == [0, 4]
    assert result[4]["warm_start_retry_attempted_indices"] == [1]


def test_unknown_retry_iteration_count_stops_further_restarts() -> None:
    point = np.zeros(1)
    objective = SimpleNamespace(best_energy=0.0, best_point=point)
    calls = []

    def run_optimizer(**kwargs):
        calls.append(np.asarray(kwargs["initial_point"], dtype=float))
        if len(calls) == 1:
            return point, 0.0, 1, True, {"optimizer_iterations": 0}
        return calls[-1], 0.1, 1, False, {"optimizer_iterations": None}

    optimizer = OptimizerConfig(
        name="L_BFGS_B",
        kind="scipy",
        max_iterations=4,
        scipy_method="L-BFGS-B",
        options={"maxiter": 4},
    )
    result = run_scipy_vqe_with_retry(
        objective=objective,
        initial_point=point,
        optimizer=optimizer,
        optimizer_diagnostics={},
        convergence_trace=[0.0],
        parameter_bounds=None,
        candidate_points=[point, np.ones(1), np.full(1, 2.0)],
        selected_initial_diagnostics={
            "initial_point_best_index": 0,
            "initial_point_candidate_energies": [0.0, 1.0, 2.0],
        },
        run_optimizer_fn=run_optimizer,
    )

    assert len(calls) == 2
    assert result[4]["termination_reason"] == "optimizer_iteration_count_unavailable"
    assert result[4]["optimizer_iterations"] is None
    assert result[4]["warm_start_retry_attempted_indices"] == [1]
