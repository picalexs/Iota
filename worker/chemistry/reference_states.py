"""Reference-state construction helpers shared by worker chemistry solvers."""

from __future__ import annotations

import numpy as np

from worker.chemistry.types import HamiltonianBundle


def _hamiltonian_num_qubits(hamiltonian: object) -> int | None:
    raw_num_qubits = getattr(hamiltonian, "num_qubits", None)
    if isinstance(raw_num_qubits, int) and raw_num_qubits > 0:
        return int(raw_num_qubits)
    pauli = getattr(hamiltonian, "pauli_hamiltonian", None)
    pauli_num_qubits = getattr(pauli, "num_qubits", None)
    if isinstance(pauli_num_qubits, int) and pauli_num_qubits > 0:
        return int(pauli_num_qubits)
    return None


def _hamiltonian_hf_metadata(hamiltonian: object) -> tuple[int, int, int] | None:
    if isinstance(hamiltonian, HamiltonianBundle):
        return (
            int(hamiltonian.num_spatial_orbitals),
            int(hamiltonian.num_electrons_alpha),
            int(hamiltonian.num_electrons_beta),
        )

    raw_n_orb = getattr(hamiltonian, "num_spatial_orbitals", None)
    raw_n_alpha = getattr(hamiltonian, "num_electrons_alpha", None)
    raw_n_beta = getattr(hamiltonian, "num_electrons_beta", None)
    if isinstance(raw_n_orb, int) and isinstance(raw_n_alpha, int) and isinstance(raw_n_beta, int):
        return int(raw_n_orb), int(raw_n_alpha), int(raw_n_beta)
    return None


def build_hf_reference_state(
    hamiltonian: object,
    *,
    fallback_dim: int | None = None,
) -> np.ndarray:
    """Return the Hartree-Fock reference state in the Jordan-Wigner basis.

    Qubits 0..n_orb-1 represent alpha spin-orbitals. Qubits n_orb..2*n_orb-1
    represent beta spin-orbitals. The HF state occupies the lowest n_alpha
    alpha and n_beta beta orbitals.
    """
    state, _source = build_hf_reference_state_with_source(
        hamiltonian,
        fallback_dim=fallback_dim,
    )
    return state


def build_hf_reference_state_with_source(
    hamiltonian: object,
    *,
    fallback_dim: int | None = None,
) -> tuple[np.ndarray, str]:
    """Return the HF-like reference state and its preparation source.

    The source is ``hartree_fock`` when electron and orbital metadata defines
    the occupied determinant. If that metadata is missing, the returned state
    is a computational-basis fallback and callers must persist that fact.
    """
    hf_metadata = _hamiltonian_hf_metadata(hamiltonian)
    num_qubits = _hamiltonian_num_qubits(hamiltonian)
    if hf_metadata is not None and num_qubits is not None:
        n_orb, n_alpha, n_beta = hf_metadata
        dim = 2 ** (2 * n_orb)
        hf_index = 0
        for index in range(n_alpha):
            hf_index |= 1 << index
        for index in range(n_beta):
            hf_index |= 1 << (n_orb + index)
        state = np.zeros(dim, dtype=complex)
        state[hf_index if 0 <= hf_index < dim else 0] = 1.0
        return state, "hartree_fock"

    if num_qubits is not None:
        return build_reference_state(2**num_qubits), "computational_basis_fallback"

    if fallback_dim is not None:
        return build_reference_state(fallback_dim), "computational_basis_fallback"

    raise ValueError("Cannot determine Hilbert space dimension for HF reference state")


def hf_reference_source(hamiltonian: object) -> str:
    """Return the declared source for an HF-like reference construction."""
    if _hamiltonian_hf_metadata(hamiltonian) is not None and _hamiltonian_num_qubits(
        hamiltonian
    ) is not None:
        return "hartree_fock"
    return "computational_basis_fallback"


def build_reference_state(vector_size: int) -> np.ndarray:
    """Return the computational zero state for a given vector dimension."""
    if vector_size < 1:
        raise ValueError("vector_size must be positive")

    state = np.zeros(vector_size, dtype=complex)
    state[0] = 1.0
    return state


__all__ = [
    "build_hf_reference_state",
    "build_hf_reference_state_with_source",
    "build_reference_state",
    "hf_reference_source",
]
