from types import SimpleNamespace

import pytest
from qiskit.quantum_info import SparsePauliOp

from worker.chemistry.matrix_element_circuits import (
    aer_simulator_options,
    augment_system_observable,
    backend_option_int,
    build_branch_state_circuit,
    optimization_level,
)


def test_augment_system_observable_adds_the_branch_ancilla() -> None:
    observable = SparsePauliOp.from_list([("Z", 2.0)])

    resolved = augment_system_observable(observable, "X")

    assert resolved.to_list() == [("XZ", 2.0 + 0.0j)]


def test_augment_system_observable_rejects_non_branch_paulis() -> None:
    with pytest.raises(ValueError, match="ancilla_pauli must be X or Y"):
        augment_system_observable(SparsePauliOp.from_list([("Z", 1.0)]), "Z")


def test_build_branch_state_circuit_prepares_reference_and_branch_evolution() -> None:
    hamiltonian = SimpleNamespace(
        num_spatial_orbitals=1,
        num_electrons_alpha=1,
        num_electrons_beta=0,
    )

    circuit = build_branch_state_circuit(
        hamiltonian=hamiltonian,
        pauli_hamiltonian=SparsePauliOp.from_list([("Z", 1.0)]),
        num_qubits=1,
        left_time=0.0,
        right_time=0.2,
        trotter_steps=1,
    )

    assert circuit.num_qubits == 2
    assert circuit.count_ops()["x"] == 1
    assert circuit.count_ops()["h"] == 1
    assert len(circuit.data) == 3


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, 1), (0, 0), (8, 3), ("invalid", 1), (True, 1)],
)
def test_optimization_level_is_bounded(value: object, expected: int) -> None:
    assert optimization_level(SimpleNamespace(optimization_level=value)) == expected


def test_backend_option_int_accepts_numeric_values_only() -> None:
    context = SimpleNamespace(backend_options={"seed_transpiler": 4.8, "invalid": True})

    assert backend_option_int(context, "seed_transpiler") == 4
    assert backend_option_int(context, "invalid") is None
    assert backend_option_int(context, "missing") is None
    assert backend_option_int(None, "seed_transpiler") is None


def test_aer_simulator_options_forwards_acceleration_and_thread_controls() -> None:
    context = SimpleNamespace(
        simulator_method="statevector",
        backend_options={
            "device": "gpu",
            "batched_shots_gpu": True,
            "runtime_parameter_bind_enable": True,
            "max_parallel_threads": 9999,
            "unrelated": "ignored",
        },
    )

    assert aer_simulator_options(context) == {
        "method": "statevector",
        "device": "GPU",
        "batched_shots_gpu": True,
        "runtime_parameter_bind_enable": True,
        "max_parallel_threads": 1024,
    }


def test_branch_circuit_time_zero_does_not_add_evolution_gate() -> None:
    circuit = build_branch_state_circuit(
        hamiltonian=SimpleNamespace(),
        pauli_hamiltonian=SparsePauliOp.from_list([("Z", 1.0)]),
        num_qubits=1,
        left_time=0.0,
        right_time=0.0,
        trotter_steps=1,
    )

    assert circuit.count_ops() == {"h": 1}


def test_branch_circuit_keeps_small_nonzero_evolution_gate() -> None:
    circuit = build_branch_state_circuit(
        hamiltonian=SimpleNamespace(
            num_spatial_orbitals=1,
            num_electrons_alpha=1,
            num_electrons_beta=0,
        ),
        pauli_hamiltonian=SparsePauliOp.from_list([("Z", 1e10)]),
        num_qubits=1,
        left_time=0.0,
        right_time=7e-10,
        trotter_steps=1,
    )

    assert len(circuit.data) == 3
