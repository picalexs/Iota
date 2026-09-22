"""Parameterized quantum circuit builders for VQE."""

from __future__ import annotations

from qiskit import QuantumCircuit, QuantumRegister
from qiskit.circuit import Parameter
from qiskit.circuit.library import n_local, real_amplitudes


def create_real_amplitudes_ansatz(
    num_qubits: int,
    depth: int,
    entanglement: str = 'full',
) -> QuantumCircuit:
    """Create RealAmplitudes-style ansatz with rotation and entanglement layers.

    Args:
        num_qubits: Number of qubits in the circuit.
        depth: Number of rotation and entanglement layers.
        entanglement: Entanglement pattern ('full', 'linear', 'circular').

    Returns:
        Parameterized QuantumCircuit with RealAmplitudes structure.
    """
    ansatz = real_amplitudes(
        num_qubits=num_qubits,
        reps=depth,
        entanglement=entanglement,
    )
    return ansatz


def create_two_local_ansatz(
    num_qubits: int,
    depth: int,
    rotation_blocks: str = 'ry',
    entanglement_blocks: str = 'cx',
) -> QuantumCircuit:
    """Create TwoLocal ansatz with specified rotation and entanglement blocks.

    Args:
        num_qubits: Number of qubits in the circuit.
        depth: Number of rotation and entanglement layers.
        rotation_blocks: Rotation gate type (e.g., 'ry', 'rz', 'rx').
        entanglement_blocks: Entanglement gate type (e.g., 'cx', 'cz').

    Returns:
        Parameterized QuantumCircuit with TwoLocal structure.
    """
    ansatz = n_local(
        num_qubits=num_qubits,
        rotation_blocks=rotation_blocks,
        entanglement_blocks=entanglement_blocks,
        entanglement='full',
        reps=depth,
    )
    return ansatz


def create_uccsd_ansatz_stub(
    num_qubits: int,
    num_parameters: int,
) -> QuantumCircuit:
    """Create simplified UCCSD-inspired ansatz stub.

    For now, returns a shallow circuit with parameterized gates
    to approximate excitation patterns.

    Args:
        num_qubits: Number of qubits in the circuit.
        num_parameters: Requested number of parameters.

    Returns:
        Parameterized QuantumCircuit with UCCSD-like structure.
    """
    qr = QuantumRegister(num_qubits, 'q')
    circuit = QuantumCircuit(qr)

    # Create enough parameters to meet the request
    # Each single + double excitation pair requires ~2 parameters
    depth = max(1, (num_parameters + 1) // 2)

    # Build layers of parameterized gates (single + double excitation-like)
    for layer in range(depth):
        # Single excitations: ry gates on each qubit
        for i in range(num_qubits):
            theta = Parameter(f'θ_{layer}_{i}')
            circuit.ry(theta, qr[i])

        # Double excitations: controlled rotations between adjacent qubits
        for i in range(num_qubits - 1):
            phi = Parameter(f'φ_{layer}_{i}')
            circuit.cx(qr[i], qr[i + 1])
            circuit.ry(phi, qr[i + 1])
            circuit.cx(qr[i], qr[i + 1])

    return circuit


def create_lucj_ansatz(
    num_qubits: int,
    depth: int,
) -> QuantumCircuit:
    """Create a lightweight LUCJ-style ansatz proxy.

    This uses linear entangling layers with alternating single-qubit
    rotations to approximate a low-depth unitary-cluster/Jastrow pattern.

    Args:
        num_qubits: Number of qubits in the circuit.
        depth: Number of repeated layers.

    Returns:
        Parameterized QuantumCircuit with a LUCJ-like structure.
    """
    return n_local(
        num_qubits=num_qubits,
        rotation_blocks=['ry', 'rz'],
        entanglement_blocks='cz',
        entanglement='linear',
        reps=depth,
    )
