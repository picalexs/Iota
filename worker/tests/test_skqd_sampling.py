"""Tests for the paper-faithful SKQD sample-union kernel."""

from __future__ import annotations

import numpy as np
import pytest
from qiskit.quantum_info import SparsePauliOp
from scipy.sparse.linalg import aslinearoperator

from worker.chemistry.algorithms.skqd import sample_union as workflow
from worker.chemistry.algorithms.skqd.sampling import (
    sample_exact_krylov_states,
    sample_krylov_state_sources,
    sample_sector_krylov_states,
)
from worker.chemistry.hamiltonian_action import build_hamiltonian_action
from worker.chemistry.hamiltonian_action import HamiltonianAction


def test_sample_krylov_state_sources_samples_every_index_and_keeps_provenance() -> None:
    states = (
        np.asarray([1.0, 0.0, 0.0, 0.0], dtype=complex),
        np.asarray([0.0, 1.0, 0.0, 0.0], dtype=complex),
        np.asarray([0.0, 0.0, 1.0, 0.0], dtype=complex),
    )

    result = sample_krylov_state_sources(
        lambda index, _time: states[index],
        num_states=3,
        time_step=0.2,
        samples_per_state=4,
        num_qubits=2,
        rng=np.random.default_rng(7),
    )

    assert [sample.krylov_index for sample in result.samples_by_state] == [0, 1, 2]
    assert [sample.bitstring_matrix.shape[0] for sample in result.samples_by_state] == [4, 4, 4]
    assert result.merged_bitstring_matrix.shape == (3, 2)
    assert result.merged_counts.tolist() == [4, 4, 4]
    assert [entry["krylov_indices"] for entry in result.provenance] == [[0], [1], [2]]
    assert [entry["counts_by_krylov_index"] for entry in result.provenance] == [
        {"0": 4},
        {"1": 4},
        {"2": 4},
    ]
    assert result.work_ledger == {
        "ledger_version": 1,
        "counting_scope": "worker_observed",
        "local_exact_sampling_runs": 3,
        "local_exact_requested_samples_total": 12,
        "local_exact_returned_raw_sample_rows": 12,
    }


def test_sample_exact_krylov_states_uses_time_evolved_probabilities() -> None:
    operator = np.asarray([[0.0, 1e10], [1e10, 0.0]], dtype=complex)
    reference = np.asarray([1.0, 0.0], dtype=complex)

    result = sample_exact_krylov_states(
        operator,
        reference,
        num_states=2,
        time_step=7e-10,
        samples_per_state=200,
        num_qubits=1,
        rng=np.random.default_rng(11),
    )

    assert result.samples_by_state[0].bitstring_matrix[:, 0].sum() == 0
    assert result.samples_by_state[1].bitstring_matrix[:, 0].sum() > 50
    assert [sample.krylov_index for sample in result.samples_by_state] == [0, 1]


def test_sample_sector_krylov_states_evolves_small_nonzero_time() -> None:
    action = HamiltonianAction(
        norb=2,
        nelec=(1, 0),
        dimension=2,
        linear_operator=aslinearoperator(
            np.asarray([[0.0, 1e10], [1e10, 0.0]], dtype=complex)
        ),
    )
    reference = np.asarray([1.0, 0.0], dtype=complex)

    result = sample_sector_krylov_states(
        action,
        reference,
        num_states=2,
        time_step=7e-10,
        samples_per_state=200,
        rng=np.random.default_rng(11),
    )

    assert np.unique(result.samples_by_state[1].bitstring_matrix, axis=0).shape[0] == 2


def test_sample_sector_krylov_states_returns_target_sector_bitstrings() -> None:
    hamiltonian = type(
        "SectorHamiltonian",
        (),
        {
            "num_spatial_orbitals": 2,
            "num_electrons_alpha": 1,
            "num_electrons_beta": 1,
            "one_body_tensor": np.diag([-1.0, 0.5]),
            "two_body_tensor": np.zeros((2, 2, 2, 2)),
            "constant": 0.0,
        },
    )()
    action = build_hamiltonian_action(hamiltonian)
    reference = np.zeros(action.dimension, dtype=complex)
    reference[0] = 1.0

    result = sample_sector_krylov_states(
        action,
        reference,
        num_states=2,
        time_step=0.1,
        samples_per_state=8,
        rng=np.random.default_rng(5),
    )

    assert result.merged_bitstring_matrix.shape[1] == 4
    assert all(np.sum(row[:2]) == 1 for row in result.merged_bitstring_matrix)
    assert all(np.sum(row[2:]) == 1 for row in result.merged_bitstring_matrix)


def test_sampler_sample_union_builds_and_samples_each_krylov_circuit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []
    ledgers: list[dict[str, object]] = []
    sampling_options: list[dict[str, object]] = []
    from qiskit.quantum_info import Operator

    def fake_sample_bitstring_matrix(backend, **kwargs):
        del backend
        ledger = kwargs["work_ledger"]
        ledgers.append(ledger)
        sampling_options.append(kwargs)
        ledger["sampler_run_attempts"] += 1
        ledger["sampler_successful_runs"] += 1
        ledger["sampler_requested_shots_total"] += kwargs["total_samples"]
        circuit = kwargs["sampling_circuit_factory"]()
        calls.append(circuit)
        index = len(calls) - 1
        returned_rows = 6 if index == 1 else 3
        ledger["sampler_returned_raw_sample_rows"] += returned_rows
        return np.asarray([[index == 1]], dtype=bool).repeat(returned_rows, axis=0), circuit

    monkeypatch.setattr(workflow, "sample_bitstring_matrix", fake_sample_bitstring_matrix)
    hamiltonian = type(
        "QubitHamiltonian",
        (),
        {
            "num_qubits": 1,
            "pauli_hamiltonian": SparsePauliOp.from_list([("X", 1.0), ("Z", 0.7)]),
        },
    )()
    config = type(
        "SKQDConfig",
        (),
        {
            "krylov_extension_dim": 3,
            "sampling_time_step": 7e-10,
            "samples_per_state": 3,
            "seed": 7,
            "trotter_steps": 1,
        },
    )()

    result, metadata = workflow.execute_sampler_sample_union_workflow(
        hamiltonian=hamiltonian,
        backend=object(),
        skqd_config=config,
        backend_context=type("Context", (), {"backend_target": "aer_simulator"})(),
    )

    assert len(calls) == 3
    assert result.samples_by_state[0].time_point == pytest.approx(0.0)
    assert result.samples_by_state[1].time_point == pytest.approx(7e-10)
    assert result.samples_by_state[2].time_point == pytest.approx(14e-10)
    assert result.merged_counts.tolist() == [6, 3]
    assert metadata["sampling_mode"] == "sample_union_sampler"
    assert metadata["sampling_source"] == "sampler_krylov_circuits"
    assert len(ledgers) == 3
    assert ledgers[0] is ledgers[1]
    assert all(option.get("retry_with_increased_shots") is False for option in sampling_options)
    assert metadata["work_ledger"] is not ledgers[0]
    assert metadata["work_ledger"]["ledger_version"] == 1
    assert metadata["work_ledger"]["sampler_run_attempts"] == 3
    assert metadata["work_ledger"]["sampler_successful_runs"] == 3
    assert metadata["work_ledger"]["sampler_requested_shots_total"] == 9
    assert metadata["work_ledger"]["sampler_returned_raw_sample_rows"] == 12
    assert metadata["work_ledger"]["sampler_retained_sample_rows"] == 9
    assert all(instruction.operation.name != "PauliEvolution" for instruction in calls[1].data)
    one_step_unitary = Operator(calls[1]).data
    two_step_unitary = Operator(calls[2]).data
    assert np.linalg.norm(one_step_unitary - np.eye(2)) > 1e-10
    assert two_step_unitary == pytest.approx(one_step_unitary @ one_step_unitary)
    assert metadata["krylov_circuit_metadata"][1]["trotter_repetitions"] == 1
    assert metadata["krylov_circuit_metadata"][2]["trotter_repetitions"] == 2


def test_sampler_sample_union_rejects_too_few_rows_for_a_krylov_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def fake_sample_bitstring_matrix(_backend, **kwargs):
        nonlocal calls
        circuit = kwargs["sampling_circuit_factory"]()
        returned_rows = 2 if calls == 0 else 3
        calls += 1
        return np.zeros((returned_rows, 1), dtype=bool), circuit

    monkeypatch.setattr(workflow, "sample_bitstring_matrix", fake_sample_bitstring_matrix)
    hamiltonian = type(
        "QubitHamiltonian",
        (),
        {
            "num_qubits": 1,
            "pauli_hamiltonian": SparsePauliOp.from_list([("X", 1.0), ("Z", 0.7)]),
        },
    )()
    config = type(
        "SKQDConfig",
        (),
        {
            "krylov_extension_dim": 2,
            "sampling_time_step": 0.2,
            "samples_per_state": 3,
            "seed": 7,
            "trotter_steps": 1,
        },
    )()

    with pytest.raises(RuntimeError, match="returned 2 rows.*requested 3"):
        workflow.execute_sampler_sample_union_workflow(
            hamiltonian=hamiltonian,
            backend=object(),
            skqd_config=config,
            backend_context=type("Context", (), {"backend_target": "ibm_runtime"})(),
        )


@pytest.mark.parametrize(
    ("num_states", "samples_per_state"),
    [(0, 1), (1, 0)],
)
def test_sample_krylov_state_sources_rejects_empty_sampling_budget(
    num_states: int,
    samples_per_state: int,
) -> None:
    with pytest.raises(ValueError):
        sample_krylov_state_sources(
            lambda _index, _time: np.asarray([1.0, 0.0], dtype=complex),
            num_states=num_states,
            time_step=0.1,
            samples_per_state=samples_per_state,
            num_qubits=1,
            rng=np.random.default_rng(1),
        )


def _large_qubit_hamiltonian(num_qubits: int) -> object:
    return type(
        "LargeHamiltonian",
        (),
        {
            "num_qubits": num_qubits,
            "pauli_hamiltonian": SparsePauliOp.from_list(
                [("Z" * num_qubits, 1.0), ("X" * num_qubits, 0.5)]
            ),
        },
    )()


def _sampler_config() -> object:
    return type(
        "SKQDConfig",
        (),
        {
            "krylov_extension_dim": 2,
            "sampling_time_step": 0.2,
            "time_step_policy": "explicit_user_time_step",
            "samples_per_state": 8,
            "seed": 7,
            "trotter_steps": 1,
            "trotter_order": 2,
        },
    )()


def test_sampler_workflow_guards_large_local_aer_circuits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The guardrail must fire before any circuit sampling is attempted.
    def fail_if_sampled(*_args, **_kwargs):
        raise AssertionError("guardrail must reject before sampling")

    monkeypatch.setattr(workflow, "sample_bitstring_matrix", fail_if_sampled)

    from worker.exceptions import RunExcludedError

    with pytest.raises(RunExcludedError, match="exceeds the 14-qubit limit") as excinfo:
        workflow.execute_sampler_sample_union_workflow(
            hamiltonian=_large_qubit_hamiltonian(16),
            backend=object(),
            skqd_config=_sampler_config(),
            backend_context=type("Context", (), {"backend_target": "aer_simulator"})(),
        )

    assert excinfo.value.reason == "skqd_sampler_circuit_exceeds_local_aer_limit"


def test_sampler_workflow_allows_large_circuits_on_ibm_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []

    def fake_sample_bitstring_matrix(backend, **kwargs):
        del backend
        circuit = kwargs["sampling_circuit_factory"]()
        calls.append(circuit)
        return np.asarray([[True] * 16], dtype=bool).repeat(2, axis=0), circuit

    monkeypatch.setattr(workflow, "sample_bitstring_matrix", fake_sample_bitstring_matrix)

    # ibm_runtime runs circuits remotely, so the local-Aer guardrail must not fire.
    result, metadata = workflow.execute_sampler_sample_union_workflow(
        hamiltonian=_large_qubit_hamiltonian(16),
        backend=object(),
        skqd_config=_sampler_config(),
        backend_context=type("Context", (), {"backend_target": "ibm_runtime"})(),
    )

    assert len(calls) == 2
    assert metadata["backend_target"] == "ibm_runtime"
