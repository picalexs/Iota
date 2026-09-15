"""Regression tests for VQE budget, uncertainty, and work-ledger metadata."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
from qiskit.quantum_info import SparsePauliOp

from worker.adapters.base import BackendExecutionContext
from worker.chemistry.algorithms.vqe import workflow as vqe_solver
from worker.chemistry.algorithms.vqe.telemetry import VQEObjectiveState
from worker.chemistry.algorithms.vqe.workflow import run_vqe


class _Job:
    def __init__(self, energy: float, standard_error: float = 0.125) -> None:
        self.energy = energy
        self.standard_error = standard_error

    def result(self):
        return [
            SimpleNamespace(
                data=SimpleNamespace(
                    evs=np.asarray([self.energy]),
                    stds=np.asarray([self.standard_error]),
                )
            )
        ]


class _Estimator:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def run(self, pubs):
        self.calls.append(pubs)
        parameters = np.asarray(pubs[0][2][0], dtype=float)
        return _Job(float(np.sum(parameters**2)))


def _config(**overrides: object) -> dict[str, object]:
    config: dict[str, object] = {
        "algorithm": "vqe",
        "max_iterations": 4,
        "optimizer_name": "COBYLA",
        "ansatz_name": "EfficientSU2",
        "initial_point": [0.2, -0.3, 0.1, -0.1, 0.05, -0.05],
    }
    config.update(overrides)
    return config


def test_objective_state_accepts_float_and_retains_standard_error_trace() -> None:
    state = VQEObjectiveState(
        energy_evaluator=lambda point: (float(np.sum(point**2)), 0.25),
        progress_callback=None,
        ansatz_name="EfficientSU2",
        optimizer_name="COBYLA",
        optimizer_kind="scipy",
        max_iterations=4,
        max_function_evaluations=None,
        parameter_count=1,
        num_qubits=1,
    )

    assert state(np.asarray([2.0])) == pytest.approx(4.0)
    assert state.standard_error_trace == [pytest.approx(0.25)]

    float_state = VQEObjectiveState(
        energy_evaluator=lambda _point: 1.0,
        progress_callback=None,
        ansatz_name="EfficientSU2",
        optimizer_name="COBYLA",
        optimizer_kind="scipy",
        max_iterations=4,
        max_function_evaluations=None,
        parameter_count=1,
        num_qubits=1,
    )
    assert float_state(np.asarray([0.0])) == pytest.approx(1.0)
    assert float_state.standard_error_trace == [None]


def test_vqe_work_ledger_counts_objective_and_final_reevaluation_once(monkeypatch) -> None:
    backend = _Estimator()

    def fake_minimize(objective, x0, method, options, bounds):
        del method, options, bounds
        energy = objective(np.asarray(x0, dtype=float))
        return SimpleNamespace(
            x=np.asarray(x0, dtype=float),
            fun=energy,
            success=True,
            status=0,
            message="converged",
            nfev=1,
            nit=1,
        )

    monkeypatch.setattr(vqe_solver, "minimize", fake_minimize)
    result = run_vqe(
        hamiltonian=SparsePauliOp.from_list([("Z", 1.0)]),
        backend=backend,
        config=_config(),
        backend_context=BackendExecutionContext(backend_target="aer_simulator", shots=256),
    )

    diagnostics = result.optimizer_diagnostics
    assert len(backend.calls) == diagnostics["primitive_jobs"]
    assert diagnostics["primitive_pubs"] == diagnostics["primitive_jobs"] == 2
    assert diagnostics["objective_evaluations"] == 1
    assert diagnostics["final_reevaluation_evaluations"] == 1
    assert diagnostics["objective_standard_error_trace"] == [pytest.approx(0.125)]
    assert diagnostics["objective_uncertainty_status"] == "available"
    assert diagnostics["primitive_shots"] == 2 * 256


def test_vqe_reports_effective_limiter_for_120_iteration_360_evaluation_split(
    monkeypatch,
) -> None:
    backend = _Estimator()
    observed_options: list[dict[str, object]] = []

    def fake_minimize(objective, x0, method, options, bounds):
        del method, bounds
        observed_options.append(options)
        energy = objective(np.asarray(x0, dtype=float))
        return SimpleNamespace(
            x=np.asarray(x0, dtype=float),
            fun=energy,
            success=False,
            status=1,
            message="maximum iterations reached",
            nfev=1,
            nit=120,
        )

    monkeypatch.setattr(vqe_solver, "minimize", fake_minimize)
    result = run_vqe(
        hamiltonian=SparsePauliOp.from_list([("Z", 1.0)]),
        backend=backend,
        config=_config(max_iterations=120, max_function_evaluations=360),
    )

    diagnostics = result.optimizer_diagnostics
    assert observed_options == [{"maxiter": 120}]
    assert diagnostics["requested_max_iterations"] == 120
    assert diagnostics["effective_max_iterations"] == 120
    assert diagnostics["effective_max_function_evaluations"] == 360
    assert diagnostics["optimizer_function_limit_source"] == "objective_callback"
    assert diagnostics["budget_limit_warning"]
    assert diagnostics["termination_reason"] == "max_iterations"


def test_vqe_budget_exhaustion_is_non_scientific_and_finite(monkeypatch) -> None:
    backend = _Estimator()

    def fake_minimize(objective, x0, method, options, bounds):
        del method, options, bounds
        while True:
            objective(np.asarray(x0, dtype=float))

    monkeypatch.setattr(vqe_solver, "minimize", fake_minimize)
    result = run_vqe(
        hamiltonian=SparsePauliOp.from_list([("Z", 1.0)]),
        backend=backend,
        config=_config(max_function_evaluations=3),
    )

    diagnostics = result.optimizer_diagnostics
    assert result.converged is False
    assert np.isfinite(result.primary_energy)
    assert diagnostics["termination_reason_code"] == "max_function_evaluations"
    assert diagnostics["scientific_converged"] is False
    assert diagnostics["budget_exhausted"] is True
    assert diagnostics["primitive_pubs"] == diagnostics["primitive_jobs"] == 3
    assert len(backend.calls) == diagnostics["primitive_pubs"]
