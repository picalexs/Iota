from types import SimpleNamespace

import numpy as np
import pytest
from qiskit.quantum_info import SparsePauliOp

from worker.chemistry.eigensolver import build_hf_reference_state as legacy_build_hf_reference_state
from worker.chemistry.eigensolver import build_reference_state as legacy_build_reference_state
from worker.chemistry.reference_states import (
    build_hf_reference_state,
    build_hf_reference_state_with_source,
    build_reference_state,
)


def test_hf_reference_state_occupies_lowest_alpha_and_beta_orbitals() -> None:
    hamiltonian = SimpleNamespace(
        num_qubits=4,
        num_spatial_orbitals=2,
        num_electrons_alpha=1,
        num_electrons_beta=1,
    )

    state = build_hf_reference_state(hamiltonian)

    assert state.shape == (16,)
    assert state[5] == 1.0
    assert np.count_nonzero(state) == 1


def test_hf_reference_state_falls_back_to_qubit_dimension() -> None:
    state = build_hf_reference_state(SimpleNamespace(num_qubits=2))

    assert state.tolist() == [1.0 + 0.0j, 0.0j, 0.0j, 0.0j]


def test_hf_reference_state_uses_pauli_width_when_bundle_lacks_num_qubits() -> None:
    hamiltonian = SimpleNamespace(
        pauli_hamiltonian=SparsePauliOp.from_list([("IIII", 1.0)]),
        num_spatial_orbitals=2,
        num_electrons_alpha=1,
        num_electrons_beta=1,
    )

    state, source = build_hf_reference_state_with_source(hamiltonian)

    assert source == "hartree_fock"
    assert state.shape == (16,)
    assert state[5] == 1.0


def test_hf_reference_state_uses_explicit_fallback_dimension() -> None:
    state = build_hf_reference_state(object(), fallback_dim=4)

    assert state.tolist() == [1.0 + 0.0j, 0.0j, 0.0j, 0.0j]


def test_hf_reference_state_source_marks_computational_fallback() -> None:
    state, source = build_hf_reference_state_with_source(object(), fallback_dim=4)

    assert source == "computational_basis_fallback"
    assert state.tolist() == [1.0 + 0.0j, 0.0j, 0.0j, 0.0j]


def test_hf_reference_state_source_marks_chemistry_determinant() -> None:
    _state, source = build_hf_reference_state_with_source(
        SimpleNamespace(
            num_qubits=4,
            num_spatial_orbitals=2,
            num_electrons_alpha=1,
            num_electrons_beta=1,
        )
    )

    assert source == "hartree_fock"


def test_hf_reference_state_requires_a_dimension() -> None:
    with pytest.raises(ValueError, match="determine Hilbert space dimension"):
        build_hf_reference_state(object())


def test_reference_state_validates_vector_size() -> None:
    with pytest.raises(ValueError, match="vector_size must be positive"):
        build_reference_state(0)


def test_eigensolver_exports_reference_state_compatibility_aliases() -> None:
    assert legacy_build_hf_reference_state is build_hf_reference_state
    assert legacy_build_reference_state is build_reference_state
