from __future__ import annotations

import warnings

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import SparsePauliOp

from quantum_diag.ansatz_factory import create_real_amplitudes_ansatz
from quantum_diag.primitive_adapter import (
    create_estimator,
    create_sampler,
    estimate_expectation,
    sample_counts,
)


def test_real_amplitudes_ansatz_has_no_deprecation_warning() -> None:
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        ansatz = create_real_amplitudes_ansatz(num_qubits=2, depth=1)

    assert ansatz.num_qubits == 2
    deprecation_msgs = [str(w.message).lower() for w in captured if issubclass(w.category, DeprecationWarning)]
    assert not deprecation_msgs


def test_estimator_adapter_expectation_value() -> None:
    circuit = QuantumCircuit(2)
    circuit.h(0)
    circuit.cx(0, 1)

    observable = SparsePauliOp.from_list([("ZZ", 1.0)])
    estimator = create_estimator()
    energy = estimate_expectation(estimator, circuit, observable)

    assert np.isclose(energy, 1.0, atol=1e-6)


def test_sampler_adapter_returns_counts() -> None:
    circuit = QuantumCircuit(1)
    circuit.h(0)
    circuit.measure_all()

    sampler = create_sampler()
    counts = sample_counts(sampler, circuit, shots=64)

    assert counts
    assert sum(counts.values()) > 0
