"""Tests for VQE state visualization payloads."""

import numpy as np
import pytest
from qiskit import QuantumCircuit

from worker.chemistry.algorithms.vqe import state_data as vqe_state_data
from worker.chemistry.algorithms.vqe import workflow as vqe_solver
from worker.chemistry.algorithms.vqe.workflow import _compute_quantum_state_data


def test_vqe_state_data_includes_bloch_vectors_for_larger_circuits() -> None:
    circuit = QuantumCircuit(12)

    bloch_vectors, dm_real, dm_imag = _compute_quantum_state_data(circuit, np.array([]), 12)

    assert bloch_vectors is not None
    assert len(bloch_vectors) == 12
    assert bloch_vectors[0] == pytest.approx([0.0, 0.0, 1.0])
    assert dm_real is None
    assert dm_imag is None


def test_solver_keeps_state_data_compatibility_alias() -> None:
    assert vqe_solver._compute_quantum_state_data is vqe_state_data.compute_quantum_state_data


def test_vqe_state_data_includes_full_density_matrix_for_small_circuits() -> None:
    circuit = QuantumCircuit(2)
    circuit.h(0)

    bloch_vectors, dm_real, dm_imag = _compute_quantum_state_data(circuit, np.array([]), 2)

    assert bloch_vectors is not None
    assert bloch_vectors[0] == pytest.approx([1.0, 0.0, 0.0])
    assert bloch_vectors[1] == pytest.approx([0.0, 0.0, 1.0])
    assert dm_real is not None
    assert dm_imag is not None
    assert len(dm_real) == 4
    assert dm_real[0][0] == pytest.approx(0.5)
    assert dm_real[0][1] == pytest.approx(0.5)
