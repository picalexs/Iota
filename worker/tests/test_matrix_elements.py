from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
from qiskit.primitives import StatevectorEstimator
from qiskit.quantum_info import SparsePauliOp

from worker.adapters.aer_adapter import AerAdapter
from worker.adapters.base import BackendExecutionContext
from worker.chemistry import matrix_elements
from worker.chemistry.algorithms.kqd.workflow import run_kqd
from worker.chemistry.algorithms.qfd.workflow import run_qfd
from worker.chemistry.eigensolver import (
    StabilizedGeneralizedEigenproblemResult,
    build_reference_state,
)
from worker.chemistry.matrix_elements import (
    _estimator_pub_chunk_size,
    estimate_projected_matrices_with_branch_estimator,
)
from worker.chemistry.time_evolution import exact_time_evolution_state


def test_branch_estimator_matrix_elements_match_dense_projection() -> None:
    hamiltonian = SimpleNamespace(
        pauli_hamiltonian=SparsePauliOp.from_list([("X", 1.0)]),
        num_qubits=1,
    )
    time_points = [0.0, 0.4]
    estimate = estimate_projected_matrices_with_branch_estimator(
        hamiltonian=hamiltonian,
        estimator=StatevectorEstimator(),
        time_points=time_points,
        trotter_steps=1,
        algorithm="kqd",
    )

    operator = hamiltonian.pauli_hamiltonian.to_matrix()
    reference = build_reference_state(2)
    states = [
        exact_time_evolution_state(operator, reference, time_step=time_point)
        for time_point in time_points
    ]
    basis = np.column_stack(states)
    expected_hamiltonian = basis.conj().T @ operator @ basis
    expected_overlap = basis.conj().T @ basis

    assert estimate.projected_hamiltonian == pytest.approx(expected_hamiltonian)
    assert estimate.overlap == pytest.approx(expected_overlap)
    assert estimate.summary["matrix_element_strategy"] == "branch_estimator"
    assert estimate.summary["estimator_pub_count"] == 3


def test_branch_estimator_handles_symmetric_negative_time_grid() -> None:
    hamiltonian = SimpleNamespace(
        pauli_hamiltonian=SparsePauliOp.from_list([("X", 1.0)]),
        num_qubits=1,
    )
    time_points = [-0.4, 0.0, 0.4]
    estimate = estimate_projected_matrices_with_branch_estimator(
        hamiltonian=hamiltonian,
        estimator=StatevectorEstimator(),
        time_points=time_points,
        trotter_steps=1,
        algorithm="qfd",
    )

    operator = hamiltonian.pauli_hamiltonian.to_matrix()
    reference = build_reference_state(2)
    states = [
        exact_time_evolution_state(operator, reference, time_step=time_point)
        for time_point in time_points
    ]
    basis = np.column_stack(states)

    assert estimate.projected_hamiltonian == pytest.approx(basis.conj().T @ operator @ basis)
    assert estimate.overlap == pytest.approx(basis.conj().T @ basis)
    assert estimate.summary["time_points"] == pytest.approx(time_points)


def test_branch_estimator_matrix_elements_run_through_aer_adapter() -> None:
    hamiltonian = SimpleNamespace(
        pauli_hamiltonian=SparsePauliOp.from_list([("X", 1.0)]),
        num_qubits=1,
    )
    context = BackendExecutionContext(
        backend_target="aer_simulator",
        shots=8192,
        simulator_method="statevector",
    )
    estimator = AerAdapter().create_estimator(context)

    estimate = estimate_projected_matrices_with_branch_estimator(
        hamiltonian=hamiltonian,
        estimator=estimator,
        time_points=[0.0, 0.4],
        trotter_steps=1,
        algorithm="kqd",
        backend_context=context,
    )

    assert estimate.overlap[0, 1].real == pytest.approx(np.cos(0.4), abs=1e-3)
    assert estimate.overlap[0, 1].imag == pytest.approx(0.0, abs=1e-3)
    assert estimate.projected_hamiltonian[0, 1].real == pytest.approx(0.0, abs=1e-3)
    assert estimate.projected_hamiltonian[0, 1].imag == pytest.approx(-np.sin(0.4), abs=1e-3)
    assert estimate.summary["backend_target"] == "aer_simulator"


def test_branch_estimator_emits_progress_events() -> None:
    events: list[dict[str, object]] = []
    hamiltonian = SimpleNamespace(
        pauli_hamiltonian=SparsePauliOp.from_list([("X", 1.0)]),
        num_qubits=1,
    )

    estimate = estimate_projected_matrices_with_branch_estimator(
        hamiltonian=hamiltonian,
        estimator=StatevectorEstimator(),
        time_points=[0.0, 0.1],
        trotter_steps=1,
        algorithm="qfd",
        progress_callback=events.append,
    )

    assert events[0]["step"] == "hardware_matrix_elements"
    assert events[0]["status"] == "preparing_branch_circuits"
    assert events[0]["estimator_pub_count"] == 3
    diagonal_events = [
        event for event in events if event.get("matrix_element_pair") == [1, 1]
    ]
    assert diagonal_events
    assert diagonal_events[-1]["energy"] is None
    assert diagonal_events[-1]["matrix_element_value"] == pytest.approx(0.0)
    assert diagonal_events[-1]["value_kind"] == "diagonal_hamiltonian_element"
    projected_events = [
        event for event in events if event.get("step") == "projected_subspace_progress"
    ]
    assert [event["convergence_iteration"] for event in projected_events] == [1, 2]
    assert projected_events[0]["energy"] == pytest.approx(0.0)
    assert projected_events[0]["energy_state"] == "provisional"
    assert isinstance(projected_events[-1]["energy"], float)
    assert projected_events[-1]["energy_state"] == "provisional"
    assert estimate.summary["overlap_diagonal_normalized"] is True
    assert np.diag(estimate.overlap) == pytest.approx(np.ones(2))


def test_branch_estimator_does_not_infer_zero_uncertainty_when_stds_are_missing() -> None:
    class _FakeJob:
        def result(self):
            return [
                SimpleNamespace(data=SimpleNamespace(evs=np.array([0.25, 0.0, 1.0, 0.0]))),
            ]

    class _EstimatorWithoutStds:
        def run(self, pubs):
            assert len(pubs) == 1
            return _FakeJob()

    hamiltonian = SimpleNamespace(
        pauli_hamiltonian=SparsePauliOp.from_list([("Z", 1.0)]),
        num_qubits=1,
    )
    estimate = estimate_projected_matrices_with_branch_estimator(
        hamiltonian=hamiltonian,
        estimator=_EstimatorWithoutStds(),
        time_points=[0.0],
        trotter_steps=1,
        algorithm="kqd",
    )

    assert estimate.summary["max_standard_error"] is None


def test_branch_estimator_separates_hamiltonian_and_overlap_uncertainty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeJob:
        def result(self):
            return [
                SimpleNamespace(
                    data=SimpleNamespace(
                        evs=np.array([-1.0, 0.0, 1.0, 0.0]),
                        stds=np.array([5.0, 7.0, 0.02, 0.03]),
                    )
                )
                for _ in range(3)
            ]

    class _Estimator:
        def run(self, pubs):
            assert len(pubs) == 3
            return _FakeJob()

    solver_errors: list[float | None] = []
    original_solver = matrix_elements.solve_stabilized_generalized_eigenproblem

    def _record_solver_error(hamiltonian, overlap, **kwargs):
        solver_errors.append(kwargs.get("max_standard_error"))
        return original_solver(hamiltonian, overlap, **kwargs)

    monkeypatch.setattr(
        "worker.chemistry.matrix_elements.solve_stabilized_generalized_eigenproblem",
        _record_solver_error,
    )
    events: list[dict[str, object]] = []
    hamiltonian = SimpleNamespace(
        pauli_hamiltonian=SparsePauliOp.from_list([("Z", -1.0)]),
        num_qubits=1,
    )

    estimate = estimate_projected_matrices_with_branch_estimator(
        hamiltonian=hamiltonian,
        estimator=_Estimator(),
        time_points=[0.0, 0.1],
        trotter_steps=1,
        algorithm="kqd",
        progress_callback=events.append,
    )

    assert estimate.summary["max_hamiltonian_standard_error"] == pytest.approx(7.0)
    assert estimate.summary["max_overlap_standard_error"] == pytest.approx(0.03)
    assert estimate.summary["max_standard_error"] == pytest.approx(7.0)
    assert estimate.summary["max_standard_error_compatibility"] == {
        "definition": "legacy_max_across_hamiltonian_and_overlap_entries",
        "units": "mixed_hamiltonian_energy_and_dimensionless_overlap",
        "deprecated": True,
    }
    assert solver_errors == pytest.approx([0.03, 0.03])
    matrix_events = [event for event in events if "matrix_element_pair" in event]
    assert matrix_events
    assert matrix_events[-1]["max_hamiltonian_standard_error"] == pytest.approx(7.0)
    assert matrix_events[-1]["max_overlap_standard_error"] == pytest.approx(0.03)
    assert matrix_events[-1]["max_standard_error"] == pytest.approx(7.0)
    assert matrix_events[-1]["standard_error_units"]["max_overlap_standard_error"] == (
        "dimensionless"
    )
    assert matrix_events[-1]["max_standard_error_compatibility"]["deprecated"] is True
    projected_events = [
        event for event in events if event.get("step") == "projected_subspace_progress"
    ]
    assert projected_events[-1]["max_hamiltonian_standard_error"] == pytest.approx(7.0)
    assert projected_events[-1]["max_overlap_standard_error"] == pytest.approx(0.03)


class _FixedUncertaintyEstimator:
    """Return valid rank-one H/S data with deliberately different error scales."""

    def run(self, pubs):
        class _Job:
            def result(self):
                return [
                    SimpleNamespace(
                        data=SimpleNamespace(
                            evs=np.array([-1.0, 0.0, 1.0, 0.0]),
                            stds=np.array([5.0, 7.0, 0.02, 0.03]),
                        )
                    )
                    for _ in pubs
                ]

        return _Job()


def test_kqd_branch_solve_uses_only_dimensionless_overlap_error() -> None:
    result = run_kqd(
        hamiltonian=SimpleNamespace(
            pauli_hamiltonian=SparsePauliOp.from_list([("Z", -1.0)]),
            num_qubits=1,
        ),
        backend=_FixedUncertaintyEstimator(),
        config={
            "algorithm": "kqd",
            "advanced_config": {
                "algorithm": "kqd",
                "krylov_dim": 2,
                "time_step": 0.1,
                "evolution_method": "trotter",
                "trotter_steps": 1,
            },
        },
        backend_context=BackendExecutionContext(backend_target="ibm_runtime"),
    )

    assert result.matrix_element_summary["max_hamiltonian_standard_error"] == pytest.approx(7.0)
    assert result.matrix_element_summary["max_overlap_standard_error"] == pytest.approx(0.03)
    assert result.stability_summary["max_standard_error"] == pytest.approx(0.03)


def test_qfd_branch_solve_uses_only_dimensionless_overlap_error() -> None:
    result = run_qfd(
        hamiltonian=SimpleNamespace(
            pauli_hamiltonian=SparsePauliOp.from_list([("Z", -1.0)]),
            num_qubits=1,
        ),
        backend=_FixedUncertaintyEstimator(),
        config={
            "algorithm": "qfd",
            "advanced_config": {
                "algorithm": "qfd",
                "num_time_points": 2,
                "max_time": 0.1,
                "time_grid_type": "linear",
                "trotter_steps": 1,
            },
        },
        backend_context=BackendExecutionContext(backend_target="ibm_runtime"),
    )

    assert result.matrix_element_summary["max_hamiltonian_standard_error"] == pytest.approx(7.0)
    assert result.matrix_element_summary["max_overlap_standard_error"] == pytest.approx(0.03)
    assert result.conditioning_summary["max_standard_error"] == pytest.approx(0.03)


def test_branch_estimator_submits_pub_chunks_for_live_progress() -> None:
    class _FakeJob:
        def __init__(self, count: int) -> None:
            self._count = count

        def result(self):
            return [
                SimpleNamespace(
                    data=SimpleNamespace(
                        evs=np.array([0.25, 0.0, 1.0, 0.0], dtype=float),
                        stds=np.zeros(4, dtype=float),
                    )
                )
                for _ in range(self._count)
            ]

    class _ChunkedEstimator:
        def __init__(self) -> None:
            self.run_sizes: list[int] = []

        def run(self, pubs):
            self.run_sizes.append(len(pubs))
            return _FakeJob(len(pubs))

    events: list[dict[str, object]] = []
    estimator = _ChunkedEstimator()
    hamiltonian = SimpleNamespace(
        pauli_hamiltonian=SparsePauliOp.from_list([("Z", 1.0)]),
        num_qubits=1,
    )

    estimate = estimate_projected_matrices_with_branch_estimator(
        hamiltonian=hamiltonian,
        estimator=estimator,
        time_points=[0.0, 0.1, 0.2],
        trotter_steps=1,
        algorithm="kqd",
        progress_callback=events.append,
    )

    assert estimator.run_sizes == [4, 2]
    assert any(event.get("estimator_pub_chunk") == [1, 4] for event in events)
    assert any(event.get("estimator_pub_chunk") == [5, 6] for event in events)
    assert events[-1]["completed_iterations"] == 6
    assert events[-1]["step"] == "projected_subspace_progress"
    assert events[-1]["convergence_iteration"] == 3
    assert estimate.summary["work_ledger"] == {
        "ledger_version": 1,
        "counting_scope": "worker_observed",
        "primitive_run_calls": 2,
        "primitive_successful_runs": 2,
        "primitive_pub_count": 6,
        "primitive_observable_slots": 24,
    }


def test_branch_estimator_batches_cpu_aer_noise_pubs() -> None:
    class _FakeJob:
        def __init__(self, count: int) -> None:
            self._count = count

        def result(self):
            return [
                SimpleNamespace(
                    data=SimpleNamespace(
                        evs=np.array([0.25, 0.0, 1.0, 0.0], dtype=float),
                        stds=np.zeros(4, dtype=float),
                    )
                )
                for _ in range(self._count)
            ]

    class _ChunkedEstimator:
        def __init__(self) -> None:
            self.run_sizes: list[int] = []

        def run(self, pubs):
            self.run_sizes.append(len(pubs))
            return _FakeJob(len(pubs))

    estimator = _ChunkedEstimator()
    hamiltonian = SimpleNamespace(
        pauli_hamiltonian=SparsePauliOp.from_list([("Z", 1.0)]),
        num_qubits=1,
    )

    estimate = estimate_projected_matrices_with_branch_estimator(
        hamiltonian=hamiltonian,
        estimator=estimator,
        time_points=[0.0, 0.1, 0.2],
        trotter_steps=1,
        algorithm="qfd",
        backend_context=BackendExecutionContext(
            backend_target="aer_simulator",
            noise_profile={"source": "backend_derived", "reference_backend": "ibm_brisbane"},
        ),
    )

    assert estimator.run_sizes == [4, 2]
    assert estimate.summary["estimator_pub_chunk_size"] == 4


def test_branch_estimator_accepts_bounded_aer_pub_chunk_override() -> None:
    context = BackendExecutionContext(
        backend_target="aer_simulator",
        backend_options={"aer_pub_chunk_size": 99},
        noise_profile={
            "source": "custom_preset",
            "preset": "depolarizing_cx",
            "strength": 0.01,
        },
    )

    assert _estimator_pub_chunk_size(context) == 32


def test_branch_estimator_marks_invalid_projected_progress_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[dict[str, object]] = []

    def _fake_stabilized(*args, **kwargs):
        del args, kwargs
        return StabilizedGeneralizedEigenproblemResult(
            eigenvalues=np.array([], dtype=float),
            raw_eigenvalues=np.array([-10.0], dtype=float),
            diagnostics={
                "stability_state": "invalid",
                "overlap_condition": float("inf"),
                "overlap_min_eigenvalue": 0.0,
                "retained_rank": 0,
                "dropped_rank": 2,
                "threshold": 1e-4,
                "psd_projected": True,
            },
        )

    monkeypatch.setattr(
        "worker.chemistry.matrix_elements.solve_stabilized_generalized_eigenproblem",
        _fake_stabilized,
    )

    hamiltonian = SimpleNamespace(
        pauli_hamiltonian=SparsePauliOp.from_list([("Z", 1.0)]),
        num_qubits=1,
    )
    estimate_projected_matrices_with_branch_estimator(
        hamiltonian=hamiltonian,
        estimator=StatevectorEstimator(),
        time_points=[0.0, 0.1],
        trotter_steps=1,
        algorithm="kqd",
        progress_callback=events.append,
    )

    projected_events = [
        event for event in events if event.get("step") == "projected_subspace_progress"
    ]
    assert projected_events[-1]["energy"] is None
    assert projected_events[-1]["energy_state"] == "unavailable"
    assert projected_events[-1]["stability_state"] == "invalid"


def test_branch_estimator_marks_stabilized_projected_progress_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[dict[str, object]] = []

    def _fake_stabilized(*args, **kwargs):
        del args, kwargs
        return StabilizedGeneralizedEigenproblemResult(
            eigenvalues=np.array([-93.0], dtype=float),
            raw_eigenvalues=np.array([-1.0], dtype=float),
            diagnostics={
                "stability_state": "stabilized",
                "overlap_condition": 128.0,
                "overlap_min_eigenvalue": 1e-3,
                "retained_rank": 1,
                "dropped_rank": 1,
                "threshold": 1e-3,
                "psd_projected": True,
            },
        )

    monkeypatch.setattr(
        "worker.chemistry.matrix_elements.solve_stabilized_generalized_eigenproblem",
        _fake_stabilized,
    )

    hamiltonian = SimpleNamespace(
        pauli_hamiltonian=SparsePauliOp.from_list([("Z", 1.0)]),
        num_qubits=1,
    )
    estimate_projected_matrices_with_branch_estimator(
        hamiltonian=hamiltonian,
        estimator=StatevectorEstimator(),
        time_points=[0.0, 0.1],
        trotter_steps=1,
        algorithm="kqd",
        progress_callback=events.append,
    )

    projected_events = [
        event for event in events if event.get("step") == "projected_subspace_progress"
    ]
    assert projected_events
    assert all(event["energy"] is None for event in projected_events)
    assert all(event["energy_state"] == "unavailable" for event in projected_events)
    assert projected_events[-1]["stability_state"] == "stabilized"
