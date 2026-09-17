"""KQD circuit-artifact construction helpers for the algorithm package."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from worker.chemistry.circuit_artifacts import (
    build_hf_reference_circuit,
    prepare_hf_reference_bits,
    serialize_circuit_artifact,
)
from worker.chemistry.projected_execution import num_qubits
from worker.chemistry.time_evolution import is_zero_time


def build_kqd_circuit_artifacts(
    *,
    hamiltonian: object,
    time_step: float,
    trotter_steps: int,
    evolution_method: str,
    use_branch_matrix_elements: bool,
    build_hf_reference_circuit_fn: Callable[..., Any] = build_hf_reference_circuit,
    build_representative_circuit_fn: Callable[..., Any] | None = None,
    serialize_circuit_artifact_fn: Callable[..., dict[str, Any]] = serialize_circuit_artifact,
) -> list[dict[str, Any]]:
    """Build representative KQD reference and evolution circuit artifacts."""
    artifacts: list[dict[str, Any]] = []

    reference_circuit = build_hf_reference_circuit_fn(hamiltonian)
    if reference_circuit is not None:
        artifacts.append(
            serialize_circuit_artifact_fn(
                reference_circuit,
                artifact_id="kqd.reference",
                algorithm="kqd",
                role="reference",
                phase="reference",
                representative=False,
                label="Hartree-Fock reference",
                source="hf_reference",
            )
        )

    if build_representative_circuit_fn is None:
        build_representative_circuit_fn = build_representative_kqd_circuit
    evolution_circuit = build_representative_circuit_fn(
        hamiltonian=hamiltonian,
        time_step=time_step,
        trotter_steps=trotter_steps,
        evolution_method=evolution_method,
        use_branch_matrix_elements=use_branch_matrix_elements,
    )
    if evolution_circuit is None:
        return artifacts

    artifacts.append(
        serialize_circuit_artifact_fn(
            evolution_circuit,
            artifact_id="kqd.evolution",
            algorithm="kqd",
            role="evolution",
            phase="time_evolution",
            representative=True,
            label=(
                "Representative KQD branch circuit"
                if use_branch_matrix_elements
                else "Representative KQD evolution circuit"
            ),
            source=(
                "branch_estimator_template"
                if use_branch_matrix_elements
                else "logical_time_evolution_template"
            ),
            parameters={
                "time_step": float(time_step),
                "trotter_steps": int(trotter_steps),
                "evolution_method": evolution_method,
                "execution_mode": (
                    "branch_estimator" if use_branch_matrix_elements else "time_evolution"
                ),
            },
        )
    )
    return artifacts


def build_representative_kqd_circuit(
    *,
    hamiltonian: object,
    time_step: float,
    trotter_steps: int,
    evolution_method: str,
    use_branch_matrix_elements: bool,
    build_hf_reference_circuit_fn: Callable[..., Any] = build_hf_reference_circuit,
    prepare_hf_reference_bits_fn: Callable[..., None] = prepare_hf_reference_bits,
    num_qubits_fn: Callable[[object], int | None] = num_qubits,
) -> Any | None:
    """Build a logical KQD circuit template for visualization."""
    if is_zero_time(time_step):
        return None

    try:
        from qiskit import QuantumCircuit
        from qiskit.circuit.library import PauliEvolutionGate
        from qiskit.quantum_info import SparsePauliOp
        from qiskit.synthesis import LieTrotter
    except Exception:
        return None

    pauli_hamiltonian = getattr(hamiltonian, "pauli_hamiltonian", None)
    if not isinstance(pauli_hamiltonian, SparsePauliOp):
        return None

    resolved_num_qubits = num_qubits_fn(hamiltonian) or pauli_hamiltonian.num_qubits
    if not isinstance(resolved_num_qubits, int) or resolved_num_qubits < 1:
        return None

    if use_branch_matrix_elements:
        circuit = QuantumCircuit(resolved_num_qubits + 1)
        ancilla = resolved_num_qubits
        prepare_hf_reference_bits_fn(
            circuit,
            hamiltonian,
            num_qubits=resolved_num_qubits,
        )
        circuit.h(ancilla)
        branch_gate = PauliEvolutionGate(
            pauli_hamiltonian,
            time=float(time_step),
            synthesis=LieTrotter(reps=int(trotter_steps)),
        )
        circuit.append(
            branch_gate.control(1, ctrl_state=1),
            [ancilla, *range(resolved_num_qubits)],
        )
        return circuit

    circuit = build_hf_reference_circuit_fn(
        hamiltonian,
        num_qubits=resolved_num_qubits,
    )
    if circuit is None:
        return None

    synthesis = None if evolution_method == "exact" else LieTrotter(reps=int(trotter_steps))
    evolution_gate = (
        PauliEvolutionGate(pauli_hamiltonian, time=float(time_step))
        if synthesis is None
        else PauliEvolutionGate(
            pauli_hamiltonian,
            time=float(time_step),
            synthesis=synthesis,
        )
    )
    circuit.append(evolution_gate, list(range(resolved_num_qubits)))
    return circuit


__all__ = ["build_kqd_circuit_artifacts", "build_representative_kqd_circuit"]
