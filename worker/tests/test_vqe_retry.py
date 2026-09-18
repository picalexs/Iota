from types import SimpleNamespace

import numpy as np

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
