"""Unit tests for pure QSE reference-input normalization."""

from __future__ import annotations

import numpy as np
import pytest

from worker.chemistry.algorithms.qse import workflow as qse_solver
from worker.chemistry.algorithms.qse.reference import (
    normalize_reference_state_vector,
    parse_reference_scalar,
    string_option,
    vector_size_to_qubits,
)


def test_string_option_uses_default_for_null_or_blank_values() -> None:
    assert string_option(None, default="vqe") == "vqe"
    assert string_option("  ", default="vqe") == "vqe"
    assert string_option(" hf ", default="vqe") == "hf"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1, 1 + 0j),
        (1.5, 1.5 + 0j),
        (1 + 2j, 1 + 2j),
        ({"real": 1, "imaginary": -2}, 1 - 2j),
        ([1, 2], 1 + 2j),
    ],
)
def test_parse_reference_scalar_accepts_json_safe_shapes(value: object, expected: complex) -> None:
    assert parse_reference_scalar(value) == expected


def test_normalize_reference_state_vector_parses_and_normalizes_values() -> None:
    vector = normalize_reference_state_vector(
        [{"real": 1.0, "imag": 0.0}, {"real": 0.0, "imag": 1.0}],
        vector_size=2,
    )

    assert np.linalg.norm(vector) == pytest.approx(1.0)
    assert vector[0] == pytest.approx(1 / np.sqrt(2))
    assert vector[1] == pytest.approx(1j / np.sqrt(2))


@pytest.mark.parametrize(
    ("vector", "size", "message"),
    [
        ("not-a-vector", 2, "must be a numeric list"),
        ([1.0], 2, "size must match"),
        ([0.0, 0.0], 2, "norm must be non-zero"),
    ],
)
def test_normalize_reference_state_vector_rejects_invalid_values(
    vector: object,
    size: int,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        normalize_reference_state_vector(vector, vector_size=size)


@pytest.mark.parametrize(("size", "expected"), [(1, 0), (2, 1), (8, 3)])
def test_vector_size_to_qubits_accepts_powers_of_two(size: int, expected: int) -> None:
    assert vector_size_to_qubits(size) == expected


def test_vector_size_to_qubits_rejects_non_power_of_two() -> None:
    with pytest.raises(ValueError, match="power of two"):
        vector_size_to_qubits(3)


def test_qse_solver_keeps_legacy_reference_aliases() -> None:
    assert qse_solver._string_option is string_option
    assert qse_solver._parse_reference_scalar is parse_reference_scalar
    assert qse_solver._normalize_reference_state_vector is normalize_reference_state_vector
    assert qse_solver._vector_size_to_qubits is vector_size_to_qubits
