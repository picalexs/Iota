"""Independent correctness checks for the exact QSE projected pencil."""

import numpy as np
import pytest

from worker.chemistry.algorithms.qse.excitations import (
    apply_fermionic_excitation,
    fermionic_excitation_specs,
    same_spin_count,
)
from worker.chemistry.algorithms.qse.workflow import _build_excitation_basis, run_qse
from worker.chemistry.eigensolver import solve_exact_generalized_eigensystem


class _DenseHamiltonian:
    num_qubits = 4

    def __init__(self, matrix: np.ndarray) -> None:
        self.dense_operator_matrix = matrix


def _independent_ladder_matrix(num_qubits: int, orbital: int, *, create: bool) -> np.ndarray:
    """Build one Jordan-Wigner ladder matrix without using the QSE helper."""
    dimension = 2**num_qubits
    matrix = np.zeros((dimension, dimension), dtype=complex)
    bit = 1 << orbital
    for basis_index in range(dimension):
        occupied = bool(basis_index & bit)
        if occupied == create:
            continue
        lower_occupancy = (basis_index & (bit - 1)).bit_count()
        sign = -1.0 if lower_occupancy % 2 else 1.0
        target = basis_index | bit if create else basis_index & ~bit
        matrix[target, basis_index] = sign
    return matrix


def test_qse_excitation_action_matches_independent_fermionic_matrix() -> None:
    rng = np.random.default_rng(11)
    reference = rng.normal(size=16) + 1j * rng.normal(size=16)
    reference /= np.linalg.norm(reference)

    create_orbitals = (1, 3)
    annihilate_orbitals = (0, 2)
    expected_operator = (
        _independent_ladder_matrix(4, 1, create=True)
        @ _independent_ladder_matrix(4, 3, create=True)
        @ _independent_ladder_matrix(4, 2, create=False)
        @ _independent_ladder_matrix(4, 0, create=False)
    )

    actual = apply_fermionic_excitation(
        reference,
        create_orbitals=create_orbitals,
        annihilate_orbitals=annihilate_orbitals,
        num_qubits=4,
    )

    assert actual == pytest.approx(expected_operator @ reference)


def test_qse_excitation_specs_are_unique_ordered_and_spin_preserving() -> None:
    specs = list(fermionic_excitation_specs(4, excitation_level="singles_doubles"))

    assert len(specs) == len(set(specs))
    assert all(
        same_spin_count(create_orbitals, annihilate_orbitals, norb=2)
        for _kind, create_orbitals, annihilate_orbitals in specs
    )
    assert all(
        create_orbitals == tuple(sorted(create_orbitals))
        and annihilate_orbitals == tuple(sorted(annihilate_orbitals))
        for _kind, create_orbitals, annihilate_orbitals in specs
    )
    assert [kind for kind, *_ in specs] == ["single"] * 4 + ["double"] * 4


def test_qse_identity_is_first_and_sector_support_is_preserved() -> None:
    reference = np.zeros(16, dtype=complex)
    reference[5] = 1.0
    operator = np.diag(np.linspace(-1.0, 1.0, 16)).astype(complex)

    basis = _build_excitation_basis(
        reference,
        operator,
        excitation_level="singles_doubles",
        target_rank=16,
        overlap_threshold=1e-10,
        regularization=1e-8,
        progress_callback=None,
    )

    assert basis[0] == pytest.approx(reference)
    for state in basis:
        for basis_index, amplitude in enumerate(state):
            if abs(amplitude) <= 1e-10:
                continue
            alpha_count = (basis_index & 0b0011).bit_count()
            beta_count = ((basis_index >> 2) & 0b0011).bit_count()
            assert (alpha_count, beta_count) == (1, 1)


def test_qse_exact_pencil_reports_hermiticity_psd_and_generalized_residuals() -> None:
    rng = np.random.default_rng(23)
    basis = rng.normal(size=(8, 3)) + 1j * rng.normal(size=(8, 3))
    operator = rng.normal(size=(8, 8)) + 1j * rng.normal(size=(8, 8))
    operator = 0.5 * (operator + operator.conj().T)
    hamiltonian = basis.conj().T @ operator @ basis
    overlap = basis.conj().T @ basis

    eigenvalues, eigenvectors, diagnostics = solve_exact_generalized_eigensystem(
        hamiltonian,
        overlap,
    )
    assert np.allclose(hamiltonian, hamiltonian.conj().T)
    assert np.allclose(overlap, overlap.conj().T)
    assert np.min(np.linalg.eigvalsh(overlap)) > 0.0
    assert diagnostics["overlap_psd"] is True
    assert diagnostics["hamiltonian_hermiticity_error"] == pytest.approx(0.0)
    assert diagnostics["overlap_hermiticity_error"] == pytest.approx(0.0)
    assert np.allclose(eigenvectors.conj().T @ overlap @ eigenvectors, np.eye(3))
    assert diagnostics["metric_normalization_error"] < 1e-10
    assert diagnostics["max_relative_generalized_residual"] < 1e-10
    assert eigenvalues.shape == (3,)


def test_qse_identity_only_returns_reference_energy() -> None:
    operator = np.diag(np.linspace(-1.0, 1.0, 16)).astype(complex)
    reference = np.zeros(16, dtype=complex)
    reference[5] = 1.0

    result = run_qse(
        hamiltonian=_DenseHamiltonian(operator),
        backend=object(),
        config={
            "algorithm": "qse",
            "advanced_config": {
                "algorithm": "qse",
                "reference_method": "provided_state",
                "provided_state_vector": reference.tolist(),
                "excitation_level": "singles_doubles",
                "max_subspace_dim": 16,
                "overlap_threshold": 1.1,
            },
        },
    )

    assert result.primary_iterations == 1
    assert result.primary_energy == pytest.approx(operator[5, 5].real)
    assert result.reference_state_energy == pytest.approx(operator[5, 5].real)
    assert result.converged is True
