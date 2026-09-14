"""Direct tests for KQD circuit-artifact construction."""

from types import SimpleNamespace

from qiskit.quantum_info import SparsePauliOp

from worker.chemistry.algorithms.kqd.circuit_artifacts import (
    build_kqd_circuit_artifacts,
    build_representative_kqd_circuit,
)


def _hamiltonian() -> SimpleNamespace:
    return SimpleNamespace(
        pauli_hamiltonian=SparsePauliOp.from_list([("Z", 1.0)]),
        num_qubits=1,
    )


def test_build_representative_kqd_circuit_adds_branch_ancilla() -> None:
    circuit = build_representative_kqd_circuit(
        hamiltonian=_hamiltonian(),
        time_step=0.2,
        trotter_steps=2,
        evolution_method="exact",
        use_branch_matrix_elements=True,
    )

    assert circuit is not None
    assert circuit.num_qubits == 2
    assert circuit.num_clbits == 0


def test_build_representative_kqd_circuit_keeps_dense_evolution_width() -> None:
    circuit = build_representative_kqd_circuit(
        hamiltonian=_hamiltonian(),
        time_step=0.2,
        trotter_steps=2,
        evolution_method="trotter",
        use_branch_matrix_elements=False,
    )

    assert circuit is not None
    assert circuit.num_qubits == 1
    assert circuit.num_clbits == 0


def test_build_kqd_circuit_artifacts_returns_reference_and_evolution() -> None:
    artifacts = build_kqd_circuit_artifacts(
        hamiltonian=_hamiltonian(),
        time_step=0.2,
        trotter_steps=1,
        evolution_method="exact",
        use_branch_matrix_elements=False,
    )

    assert [artifact["role"] for artifact in artifacts] == ["reference", "evolution"]
    assert artifacts[0]["artifact_id"] == "kqd.reference"
    assert artifacts[1]["artifact_id"] == "kqd.evolution"
    assert artifacts[1]["source"] == "logical_time_evolution_template"
