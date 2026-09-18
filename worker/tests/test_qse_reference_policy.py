"""Direct tests for QSE reference-state policy boundaries."""

from types import SimpleNamespace

import numpy as np
from qiskit import QuantumCircuit

from worker.chemistry.algorithms.qse.reference_policy import (
    build_vqe_reference_state,
    resolve_reference_state,
    resolve_sector_reference_state,
)


def test_build_vqe_reference_state_uses_injected_runtime_seams() -> None:
    progress_events: list[dict[str, object]] = []

    def fake_run_vqe(**kwargs: object) -> SimpleNamespace:
        callback = kwargs["progress_callback"]
        assert callable(callback)
        callback({"energy": -1.0})
        return SimpleNamespace(
            optimal_parameters=np.array([], dtype=float),
            converged=False,
            optimizer_diagnostics={
                "objective_evaluations": 4,
                "optimizer_iterations": 2,
                "max_function_evaluations": 8,
                "termination_reason": "max_function_evaluations",
                "convergence_threshold": 1e-6,
                "final_delta_energy": 1e-7,
                "best_observed_energy": -1.2,
                "final_energy": -1.1,
            },
            circuit_artifacts=[{"id": "vqe-ansatz", "role": "ansatz"}],
        )

    state, artifacts = build_vqe_reference_state(
        hamiltonian=object(),
        backend=object(),
        vector_size=2,
        resolved_config={"vqe_reference_reps": 1},
        progress_callback=progress_events.append,
        run_vqe_fn=fake_run_vqe,
        build_ansatz_fn=lambda **_kwargs: QuantumCircuit(1),
    )

    assert np.isclose(np.linalg.norm(state), 1.0)
    assert progress_events[0]["step"] == "reference_vqe"
    assert artifacts[0]["id"] == "qse.reference.vqe-ansatz"
    assert artifacts[0]["role"] == "reference"
    assert artifacts[0]["reference_cost"] == {
        "cost_type": "vqe_reference_optimization",
        "execution_mode": "exact_emulation",
        "cost_status": "measured",
        "ansatz_name": "EfficientSU2",
        "optimizer_name": "COBYLA",
        "reps": 1,
        "objective_evaluations": 4,
        "optimizer_iterations": 2,
        "max_function_evaluations": 8,
        "state_preparations": 4,
        "optimizer_converged": False,
        "scientific_converged": True,
        "budget_exhausted": True,
        "termination_reason": "max_function_evaluations",
        "best_observed_energy": -1.2,
        "final_energy": -1.1,
    }


def test_resolve_reference_state_normalizes_provided_state() -> None:
    method, state, artifacts = resolve_reference_state(
        hamiltonian=object(),
        backend=object(),
        operator_matrix=np.eye(2),
        resolved_config={
            "reference_method": "provided_state",
            "provided_state_vector": [1, 1j],
        },
        progress_callback=None,
        build_vqe_reference_state_fn=lambda **_kwargs: (
            np.array([1, 0], dtype=complex),
            [],
        ),
        build_hf_reference_state_fn=lambda *_args, **_kwargs: np.array([1, 0], dtype=complex),
        hf_reference_artifacts_fn=lambda _hamiltonian: [],
    )

    assert method == "provided_state"
    assert np.isclose(np.linalg.norm(state), 1.0)
    assert artifacts == []


def test_resolve_sector_reference_state_uses_injected_sector_policy() -> None:
    action = SimpleNamespace(norb=2, nelec=(1, 1), dimension=4)
    captured: dict[str, object] = {}

    def fake_amplitudes(raw: object, **kwargs: object) -> np.ndarray:
        captured["raw"] = raw
        captured.update(kwargs)
        return np.array([0, 1, 0, 0], dtype=complex)

    method, state, artifacts = resolve_sector_reference_state(
        hamiltonian=object(),
        action=action,
        resolved_config={
            "reference_method": "provided_sector",
            "provided_sector_reference": {"amplitudes": {"0": 1}},
        },
        hf_reference_artifacts_fn=lambda _hamiltonian: [],
        state_from_sector_amplitudes_fn=fake_amplitudes,
    )

    assert method == "provided_sector"
    assert np.array_equal(state, np.array([0, 1, 0, 0], dtype=complex))
    assert artifacts == []
    assert captured == {"raw": {"0": 1}, "norb": 2, "nelec": (1, 1), "dimension": 4}
