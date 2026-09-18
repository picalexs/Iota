from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from worker.chemistry.algorithms.vqe.scipy import run_scipy_vqe_optimizer


@pytest.mark.parametrize("scipy_method", ["L-BFGS-B", "SLSQP", "COBYLA"])
def test_run_scipy_vqe_optimizer_normalizes_scipy_result(scipy_method: str) -> None:
    initial_point = np.array([0.2, -0.1], dtype=float)
    scipy_result = SimpleNamespace(
        x=np.array([0.0, 0.3]),
        fun=-0.25,
        success=True,
        status=0,
        message="converged",
        nfev=4,
        nit=2,
    )
    calls: list[dict[str, object]] = []

    def fake_minimize(*args: object, **kwargs: object) -> SimpleNamespace:
        calls.append({"args": args, **kwargs})
        return scipy_result

    result = run_scipy_vqe_optimizer(
        objective=lambda _point: 0.0,
        initial_point=initial_point,
        optimizer=SimpleNamespace(
            scipy_method=scipy_method,
            options=None,
            max_iterations=5,
        ),
        optimizer_diagnostics={"optimizer_kind": "scipy"},
        convergence_trace=[-0.1, -0.2],
        parameter_bounds=[(-1.0, 1.0), (-1.0, 1.0)],
        best_point_getter=lambda: np.array([0.0, 0.3]),
        best_energy_getter=lambda: -0.25,
        minimize_fn=fake_minimize,
    )

    optimal_point, final_energy, iterations, converged, diagnostics = result
    np.testing.assert_allclose(optimal_point, [0.0, 0.3])
    assert final_energy == pytest.approx(-0.25)
    assert iterations == 2
    assert converged is True
    assert diagnostics["scipy_method"] == scipy_method
    assert diagnostics["function_evaluations"] == 4
    assert diagnostics["optimizer_function_evaluations"] == 4
    assert diagnostics["termination_reason"] == "optimizer_success"
    assert diagnostics["final_delta_energy"] == pytest.approx(0.1)
    assert calls[0]["bounds"] == [(-1.0, 1.0), (-1.0, 1.0)]
