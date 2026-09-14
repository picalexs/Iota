"""Tests for bounded dense-operator caching in eigensolver helpers."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
from qiskit.quantum_info import SparsePauliOp

from worker.chemistry.eigensolver import (
    clear_operator_matrix_cache,
    operator_matrix_cache_info,
    resolve_operator_matrix,
)


def test_resolve_operator_matrix_uses_sparse_cache(monkeypatch) -> None:
    clear_operator_matrix_cache()
    pauli = SparsePauliOp.from_list([("ZI", 0.5), ("IZ", -0.25)])

    original_to_matrix = SparsePauliOp.to_matrix
    call_count = 0

    def _counting_to_matrix(self, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        return original_to_matrix(self, *args, **kwargs)

    monkeypatch.setattr(SparsePauliOp, "to_matrix", _counting_to_matrix)

    matrix_one = resolve_operator_matrix(pauli)
    matrix_two = resolve_operator_matrix(pauli)

    assert np.allclose(matrix_one, matrix_two)
    assert call_count == 1


def test_resolve_operator_matrix_uses_bundle_pauli_cache(monkeypatch) -> None:
    clear_operator_matrix_cache()
    bundle = SimpleNamespace(pauli_hamiltonian=SparsePauliOp.from_list([("Z", 1.0)]))

    original_to_matrix = SparsePauliOp.to_matrix
    call_count = 0

    def _counting_to_matrix(self, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        return original_to_matrix(self, *args, **kwargs)

    monkeypatch.setattr(SparsePauliOp, "to_matrix", _counting_to_matrix)

    _ = resolve_operator_matrix(bundle)
    _ = resolve_operator_matrix(bundle)

    assert call_count == 1


def test_operator_matrix_cache_is_bounded() -> None:
    clear_operator_matrix_cache()
    max_entries = operator_matrix_cache_info()["max_entries"]

    for idx in range(max_entries + 5):
        pauli = SparsePauliOp.from_list([("Z", float(idx + 1))])
        _ = resolve_operator_matrix(pauli)

    info = operator_matrix_cache_info()
    assert info["size"] == max_entries
