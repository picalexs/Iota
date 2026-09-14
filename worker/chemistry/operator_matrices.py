"""Dense operator-matrix resolution and caching for worker chemistry solvers."""

from __future__ import annotations

import hashlib
import json
from collections import OrderedDict

import numpy as np
from qiskit.quantum_info import SparsePauliOp

from worker.chemistry.types import HamiltonianBundle

_MAX_OPERATOR_MATRIX_CACHE_ENTRIES = 32
_MAX_QUBITS_DENSE_MATRIX = 12  # 2^12 = 4096 states → ~256 MB dense matrix
_OPERATOR_MATRIX_CACHE: OrderedDict[str, np.ndarray] = OrderedDict()


def _matrix_cache_get(cache_key: str) -> np.ndarray | None:
    cached = _OPERATOR_MATRIX_CACHE.get(cache_key)
    if cached is None:
        return None
    _OPERATOR_MATRIX_CACHE.move_to_end(cache_key)
    return cached


def _matrix_cache_set(cache_key: str, matrix: np.ndarray) -> np.ndarray:
    cached = np.asarray(matrix, dtype=complex)
    cached.setflags(write=False)
    _OPERATOR_MATRIX_CACHE[cache_key] = cached
    _OPERATOR_MATRIX_CACHE.move_to_end(cache_key)
    while len(_OPERATOR_MATRIX_CACHE) > _MAX_OPERATOR_MATRIX_CACHE_ENTRIES:
        _OPERATOR_MATRIX_CACHE.popitem(last=False)
    return cached


def _sparse_pauli_cache_key(pauli: SparsePauliOp) -> str:
    terms: list[tuple[str, float, float]] = []
    for label, coeff in pauli.to_list():
        coeff_complex = complex(coeff)
        terms.append((label, float(coeff_complex.real), float(coeff_complex.imag)))

    payload = {
        "num_qubits": int(pauli.num_qubits or 0),
        "terms": terms,
    }
    canonical_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
    return f"sparse:{digest}"


def operator_matrix_cache_info() -> dict[str, int]:
    """Return bounded-cache sizing info for dense operator matrices."""
    return {
        "size": len(_OPERATOR_MATRIX_CACHE),
        "max_entries": _MAX_OPERATOR_MATRIX_CACHE_ENTRIES,
    }


def clear_operator_matrix_cache() -> None:
    """Clear all cached dense operator matrices."""
    _OPERATOR_MATRIX_CACHE.clear()


def _resolve_sparse_matrix(pauli: SparsePauliOp) -> np.ndarray:
    cache_key = _sparse_pauli_cache_key(pauli)
    cached = _matrix_cache_get(cache_key)
    if cached is not None:
        return cached
    return _matrix_cache_set(cache_key, pauli.to_matrix())


def _hamiltonian_num_qubits(hamiltonian: object) -> int | None:
    raw_num_qubits = (
        hamiltonian.num_qubits
        if isinstance(hamiltonian, HamiltonianBundle)
        else getattr(hamiltonian, "num_qubits", None)
    )
    return int(raw_num_qubits) if isinstance(raw_num_qubits, int) else None


def _hamiltonian_pauli(hamiltonian: object) -> SparsePauliOp | None:
    pauli = (
        hamiltonian.pauli_hamiltonian
        if isinstance(hamiltonian, HamiltonianBundle)
        else getattr(hamiltonian, "pauli_hamiltonian", None)
    )
    return pauli if isinstance(pauli, SparsePauliOp) else None


def _sparse_pauli_num_qubits(pauli: SparsePauliOp) -> int | None:
    raw_num_qubits = pauli.num_qubits
    return int(raw_num_qubits) if isinstance(raw_num_qubits, int) else None


def _check_qubit_count_for_dense(hamiltonian: object) -> None:
    """Raise ValueError if the Hamiltonian is too large for a dense matrix."""
    num_qubits = _hamiltonian_num_qubits(hamiltonian)
    if num_qubits is None:
        pauli = _hamiltonian_pauli(hamiltonian)
        if pauli is not None:
            num_qubits = _sparse_pauli_num_qubits(pauli)
    if num_qubits is None and isinstance(hamiltonian, SparsePauliOp):
        num_qubits = _sparse_pauli_num_qubits(hamiltonian)

    if num_qubits is not None and num_qubits > _MAX_QUBITS_DENSE_MATRIX:
        dim = 2**num_qubits
        matrix_gb = round(dim * dim * 16 / 1e9, 1)
        raise ValueError(
            f"Cannot materialize dense matrix for {num_qubits}-qubit Hamiltonian "
            f"({dim}×{dim}, ~{matrix_gb} GB): exceeds the {_MAX_QUBITS_DENSE_MATRIX}-qubit "
            "limit for dense-matrix solvers (KQD/QFD/QSE/SKQD). "
            "Use VQE or SQD which do not require full matrix materialization."
        )


def resolve_operator_matrix(hamiltonian: object) -> np.ndarray:
    """Resolve a dense Hermitian matrix from a worker Hamiltonian input."""
    _check_qubit_count_for_dense(hamiltonian)

    dense_operator_matrix = getattr(hamiltonian, "dense_operator_matrix", None)
    if dense_operator_matrix is not None:
        matrix = np.asarray(dense_operator_matrix, dtype=complex)
        matrix.setflags(write=False)
        return matrix

    pauli = _hamiltonian_pauli(hamiltonian)
    if pauli is not None:
        return _resolve_sparse_matrix(pauli)

    if isinstance(hamiltonian, SparsePauliOp):
        return _resolve_sparse_matrix(hamiltonian)

    to_matrix = getattr(hamiltonian, "to_matrix", None)
    if callable(to_matrix):
        cache_key_value = getattr(hamiltonian, "matrix_cache_key", None)
        if isinstance(cache_key_value, str) and cache_key_value.strip():
            cache_key = f"generic:{cache_key_value.strip()}"
            cached = _matrix_cache_get(cache_key)
            if cached is not None:
                return cached
            matrix = np.asarray(to_matrix(), dtype=complex)
            return _matrix_cache_set(cache_key, matrix)

        matrix = np.asarray(to_matrix(), dtype=complex)
        matrix.setflags(write=False)
        return matrix

    raise ValueError(
        "Unable to resolve operator matrix from hamiltonian; expected "
        "HamiltonianBundle.pauli_hamiltonian, SparsePauliOp, or to_matrix()."
    )


__all__ = [
    "clear_operator_matrix_cache",
    "operator_matrix_cache_info",
    "resolve_operator_matrix",
]
