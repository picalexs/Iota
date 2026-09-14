"""Ansatz registry for worker VQE execution."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import numpy as np
from qiskit.circuit import Parameter, QuantumCircuit
from qiskit.circuit.library import (
    PauliEvolutionGate,
    XXPlusYYGate,
    efficient_su2,
    n_local,
    real_amplitudes,
)
from qiskit.quantum_info import SparsePauliOp

from shared.contracts.registry_metadata import (
    supported_ansatz_aliases as _shared_supported_ansatz_aliases,
)
from shared.contracts.registry_metadata import (
    supported_ansatz_metadata as _shared_supported_ansatz_metadata,
)


@lru_cache(maxsize=1)
def _cached_supported_ansatz_aliases() -> dict[str, str]:
    """Build normalized aliases from the shared public catalog."""
    return _shared_supported_ansatz_aliases()


def _supported_ansatz_aliases() -> dict[str, str]:
    """Return a defensive copy of the cached normalized alias map."""
    return dict(_cached_supported_ansatz_aliases())


def supported_ansatzes() -> set[str]:
    """Return canonical ansatz identifiers supported in the current rollout."""
    return set(_shared_supported_ansatz_metadata())


def supported_ansatz_metadata() -> dict[str, dict[str, Any]]:
    """Return public metadata without importing API code."""
    return _shared_supported_ansatz_metadata()


def _number_preserving_ansatz(
    *,
    num_qubits: int,
    reps: int,
    num_electrons_alpha: int | None,
    num_electrons_beta: int | None,
) -> QuantumCircuit:
    """Build an ansatz that preserves alpha and beta occupations separately."""
    num_orbitals = _validate_number_preserving_inputs(
        num_qubits,
        num_electrons_alpha,
        num_electrons_beta,
    )
    circuit = QuantumCircuit(num_qubits, name="NumberPreserving")
    _initialize_number_preserving_state(circuit, num_orbitals, num_electrons_alpha, num_electrons_beta)
    _append_number_preserving_layers(circuit, num_orbitals, reps)
    return circuit


def _validate_number_preserving_inputs(
    num_qubits: int,
    num_electrons_alpha: int | None,
    num_electrons_beta: int | None,
) -> int:
    if num_qubits < 2 or num_qubits % 2:
        raise ValueError("NumberPreserving requires an even qubit count")
    if num_electrons_alpha is None or num_electrons_beta is None:
        raise ValueError(
            "NumberPreserving requires num_electrons_alpha and num_electrons_beta"
        )

    num_orbitals = num_qubits // 2
    for count in (num_electrons_alpha, num_electrons_beta):
        if isinstance(count, bool) or not 0 <= count <= num_orbitals:
            raise ValueError("NumberPreserving electron counts must fit the spatial orbitals")
    return num_orbitals


def _initialize_number_preserving_state(
    circuit: QuantumCircuit,
    num_orbitals: int,
    num_electrons_alpha: int | None,
    num_electrons_beta: int | None,
) -> None:
    assert num_electrons_alpha is not None and num_electrons_beta is not None
    for orbital in range(num_electrons_alpha):
        circuit.x(orbital)
    for orbital in range(num_electrons_beta):
        circuit.x(num_orbitals + orbital)


def _append_number_preserving_layers(
    circuit: QuantumCircuit,
    num_orbitals: int,
    reps: int,
) -> None:
    parameter_index = 0
    for layer in range(reps):
        parity = layer % 2
        for spin_offset in (0, num_orbitals):
            for orbital in range(parity, num_orbitals - 1, 2):
                circuit.append(
                    XXPlusYYGate(Parameter(f"theta_{parameter_index}"), 0.0),
                    [spin_offset + orbital, spin_offset + orbital + 1],
                )
                parameter_index += 1
        for first_orbital in range(num_orbitals):
            for second_orbital in range(first_orbital + 1, num_orbitals):
                circuit.append(
                    PauliEvolutionGate(
                        _paired_double_excitation_generator(),
                        time=Parameter(f"theta_{parameter_index}"),
                    ),
                    [
                        first_orbital,
                        second_orbital,
                        num_orbitals + first_orbital,
                        num_orbitals + second_orbital,
                    ],
                )
                parameter_index += 1


@lru_cache(maxsize=1)
def _paired_double_excitation_generator() -> SparsePauliOp:
    """Return a four-qubit spin-balanced double-excitation generator."""
    generator = np.zeros((16, 16), dtype=complex)
    # The local qubit order is alpha-i, alpha-j, beta-i, beta-j. The
    # anti-symmetric Hermitian generator produces a real determinant rotation
    # while preserving both spin counts.
    generator[10, 5] = 1j
    generator[5, 10] = -1j
    return SparsePauliOp.from_operator(generator)


def number_preserving_parameter_count(*, num_orbitals: int, reps: int) -> int:
    """Return the parameter count without requiring an electron-sector choice."""
    if num_orbitals < 1:
        raise ValueError("num_orbitals must be positive")
    return sum(
        2 * len(range(layer % 2, num_orbitals - 1, 2))
        + num_orbitals * (num_orbitals - 1) // 2
        for layer in range(max(1, reps))
    )


def build_ansatz(
    *,
    ansatz_name: str,
    num_qubits: int,
    reps: int = 2,
    num_electrons_alpha: int | None = None,
    num_electrons_beta: int | None = None,
) -> QuantumCircuit:
    """Construct a supported ansatz circuit for VQE execution."""
    normalized = _supported_ansatz_aliases().get(ansatz_name.strip().lower())
    if normalized is None:
        supported = ", ".join(sorted(supported_ansatzes()))
        raise ValueError(f"Unsupported ansatz '{ansatz_name}'. Supported: {supported}")

    if normalized == "numberpreserving":
        return _number_preserving_ansatz(
            num_qubits=num_qubits,
            reps=reps,
            num_electrons_alpha=num_electrons_alpha,
            num_electrons_beta=num_electrons_beta,
        )

    if normalized == "realamplitudes":
        return real_amplitudes(num_qubits=num_qubits, reps=reps)

    if normalized == "twolocal":
        return n_local(
            num_qubits=num_qubits,
            rotation_blocks=["ry", "rz"],
            entanglement_blocks="cx",
            reps=reps,
        )

    return efficient_su2(num_qubits=num_qubits, reps=reps)


__all__ = [
    "build_ansatz",
    "number_preserving_parameter_count",
    "supported_ansatz_metadata",
    "supported_ansatzes",
]
