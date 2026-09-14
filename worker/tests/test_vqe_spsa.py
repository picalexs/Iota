"""Direct tests for the VQE SPSA optimization seam."""

import numpy as np

from worker.chemistry.algorithms.vqe.spsa import is_delta_converged, run_spsa


def test_delta_convergence_requires_a_complete_stable_window() -> None:
    assert not is_delta_converged([1.0, 1.0], threshold=0.0)
    assert is_delta_converged([1.0, 1.0, 1.0, 1.0, 1.0], threshold=0.0)
    assert not is_delta_converged([1.0, 1.0, 1.0, 1.0, 1.01], threshold=0.0)


def test_run_spsa_returns_a_bounded_best_point_and_diagnostics() -> None:
    def objective(point: np.ndarray) -> float:
        return float(np.sum((point - np.array([0.1, -0.1])) ** 2))

    best_point, iterations, converged, diagnostics = run_spsa(
        objective=objective,
        initial_point=np.array([0.0, 0.0]),
        max_iterations=4,
        options={"learning_rate": 0.25, "perturbation": 0.1},
        threshold=1e-12,
        seed=7,
        convergence_trace=[],
        parameter_bounds=[(-0.05, 0.05), (-0.05, 0.05)],
    )

    assert np.all(best_point <= 0.05)
    assert np.all(best_point >= -0.05)
    assert iterations >= 1
    assert not converged
    assert diagnostics["optimizer_kind"] == "spsa"
    assert diagnostics["accepted_steps"] == len(diagnostics["accepted_energy_trace"]) - 1


def test_run_spsa_stops_after_five_stable_accepted_energies() -> None:
    best_point, iterations, converged, diagnostics = run_spsa(
        objective=lambda _point: 1.0,
        initial_point=np.array([0.0]),
        max_iterations=20,
        options=None,
        threshold=0.0,
        seed=3,
        convergence_trace=[],
        parameter_bounds=None,
    )

    assert best_point.tolist() == [0.0]
    assert iterations == 4
    assert converged
    assert diagnostics["accepted_steps"] == 4
