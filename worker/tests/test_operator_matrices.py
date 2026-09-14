from types import SimpleNamespace

import numpy as np
import pytest
from qiskit.quantum_info import SparsePauliOp

from worker.chemistry.operator_matrices import (
    clear_operator_matrix_cache,
    operator_matrix_cache_info,
    resolve_operator_matrix,
)


def test_generic_matrix_cache_uses_declared_cache_key() -> None:
    clear_operator_matrix_cache()
    calls = 0

    class _Operator:
        matrix_cache_key = "operator-a"

        def to_matrix(self) -> np.ndarray:
            nonlocal calls
            calls += 1
            return np.diag([1.0, -1.0])

    first = resolve_operator_matrix(_Operator())
    second = resolve_operator_matrix(_Operator())

    assert calls == 1
    assert np.array_equal(first, second)
    assert first.flags.writeable is False


def test_dense_matrix_guard_rejects_large_sparse_pauli_inputs() -> None:
    large_operator = SparsePauliOp.from_list([("I" * 13, 1.0)])

    with pytest.raises(ValueError, match="exceeds the 12-qubit limit"):
        resolve_operator_matrix(large_operator)


def test_dense_operator_input_is_read_only() -> None:
    source = np.eye(2, dtype=complex)

    matrix = resolve_operator_matrix(SimpleNamespace(dense_operator_matrix=source))

    assert np.array_equal(matrix, source)
    assert matrix.flags.writeable is False


def test_cache_info_reports_bounded_capacity() -> None:
    clear_operator_matrix_cache()

    info = operator_matrix_cache_info()

    assert info == {"size": 0, "max_entries": 32}
