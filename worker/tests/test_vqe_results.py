from types import SimpleNamespace

import numpy as np
import pytest

from worker.chemistry.algorithms.vqe.results import (
    build_parameterless_vqe_result,
    build_vqe_initial_point_limit_result,
    build_vqe_result,
    reported_vqe_energy_source,
)


def _build_artifacts(**kwargs):
    return [{"role": "optimizer", "reported_energy_source": kwargs["reported_energy_source"]}]


def test_build_parameterless_vqe_result_records_terminal_objective() -> None:
    result = build_parameterless_vqe_result(
        objective=lambda point: float(np.sum(point) - 1.0),
        initial_point=np.array([1.0]),
        include_statevector_data=False,
        ansatz=SimpleNamespace(),
        num_qubits=1,
        optimizer_diagnostics={"optimizer_name": "none"},
        initial_point_diagnostics={},
        ansatz_name="hf",
        optimizer_name="none",
        reps=1,
        compute_state_data_fn=lambda *_: (None, None, None),
        build_circuit_artifacts_fn=_build_artifacts,
    )

    assert result.primary_energy == pytest.approx(0.0)
    assert result.converged is True
    assert result.optimizer_diagnostics["termination_reason"] == "ansatz_has_no_parameters"
    assert result.circuit_artifacts[0]["reported_energy_source"] == "final_optimizer_objective"


def test_build_vqe_initial_point_limit_result_uses_best_observed_point() -> None:
    result = build_vqe_initial_point_limit_result(
        ansatz=SimpleNamespace(),
        ansatz_name="hf",
        optimizer_name="L_BFGS_B",
        reps=1,
        optimizer_diagnostics={},
        initial_point_diagnostics={},
        best_point=np.array([0.4]),
        best_energy=-1.2,
        candidate_points=[np.zeros(1)],
        convergence_trace=[-1.0, -1.2],
        exc=RuntimeError("limit"),
        best_energy_selector_fn=lambda energy, trace: energy if energy is not None else trace[-1],
        build_circuit_artifacts_fn=_build_artifacts,
    )

    assert result.primary_energy == -1.2
    assert result.optimal_parameters == [0.4]
    assert result.converged is False
    assert result.optimizer_diagnostics["message"] == "limit"


def test_build_vqe_result_prefers_the_best_observed_parameters() -> None:
    diagnostics = {"optimizer_iterations": 2}
    result = build_vqe_result(
        ansatz=SimpleNamespace(),
        ansatz_name="hf",
        optimizer_name="L_BFGS_B",
        reps=1,
        num_qubits=1,
        include_statevector_data=False,
        optimal_point=np.array([0.8]),
        final_energy=-0.5,
        iterations=2,
        converged=True,
        objective_state=SimpleNamespace(
            convergence_trace=[-0.4, -0.6],
            best_energy=-0.6,
            best_point=np.array([0.2]),
        ),
        optimizer_diagnostics=diagnostics,
        compute_state_data_fn=lambda *_: (None, None, None),
        build_circuit_artifacts_fn=_build_artifacts,
    )

    assert result.primary_energy == -0.6
    assert result.optimal_parameters == [0.2]
    assert diagnostics["reported_energy_source"] == "best_observed_optimizer_evaluation"


@pytest.mark.parametrize(
    ("final_energy", "best_energy", "same_point", "expected"),
    [
        (-1.0, -1.0, True, "final_optimizer_objective"),
        (-1.0, -1.1, True, "best_observed_optimizer_evaluation"),
        (-1.0, -1.0, False, "best_observed_optimizer_evaluation"),
    ],
)
def test_reported_vqe_energy_source_tracks_energy_and_point(
    final_energy: float,
    best_energy: float,
    same_point: bool,
    expected: str,
) -> None:
    final_point = np.array([0.1])
    reported_point = final_point if same_point else np.array([0.2])

    assert (
        reported_vqe_energy_source(
            final_energy=final_energy,
            best_observed_energy=best_energy,
            final_point=final_point,
            reported_point=reported_point,
        )
        == expected
    )
