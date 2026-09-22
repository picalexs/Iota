"""Unit tests for pure SQD sampler-output helpers."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from worker.chemistry.algorithms.sqd import workflow as sqd_solver
from worker.chemistry.algorithms.sqd.sampling import (
    aggregate_bitstring_frequencies,
    bitstring_from_row,
    bitstrings_to_matrix,
    extract_sampler_bitstrings,
    resolve_measurement_register,
    summarize_bitstring_distribution,
)
from worker.chemistry.algorithms.sqd.sampling_execution import _ensure_measurements


def test_bitstrings_to_matrix_normalizes_spaced_shot_values() -> None:
    matrix = bitstrings_to_matrix(["10 1", "001"], num_bits=3)

    assert matrix.tolist() == [[True, False, True], [False, False, True]]


def test_bitstrings_to_matrix_rejects_width_mismatch() -> None:
    with pytest.raises(ValueError, match="width"):
        bitstrings_to_matrix(["01"], num_bits=3)


def test_bitstrings_to_matrix_rejects_non_binary_characters() -> None:
    with pytest.raises(ValueError, match="binary"):
        bitstrings_to_matrix(["0x1"], num_bits=3)


def test_sqd_sampling_circuit_rejects_nonterminal_measurements() -> None:
    from qiskit import QuantumCircuit

    circuit = QuantumCircuit(2, 2)
    circuit.measure([0, 1], [0, 1])
    circuit.x(0)

    with pytest.raises(ValueError, match="terminal"):
        _ensure_measurements(circuit, num_bits=2)


class _MeasurementRegister:
    def __init__(self, bitstrings: list[str]) -> None:
        self._bitstrings = bitstrings

    def get_bitstrings(self) -> list[str]:
        return self._bitstrings


def test_extract_sampler_bitstrings_resolves_measurement_register() -> None:
    register = _MeasurementRegister(["010", "111"])
    result = [type("PubResult", (), {"data": type("Data", (), {"meas": register})()})()]

    assert resolve_measurement_register(result[0].data) is register
    assert extract_sampler_bitstrings(result) == ["010", "111"]


def test_extract_sampler_bitstrings_returns_none_for_missing_or_empty_payloads() -> None:
    assert extract_sampler_bitstrings([]) is None
    assert extract_sampler_bitstrings([type("PubResult", (), {"data": None})()]) is None
    empty_register = _MeasurementRegister([])
    result = [type("PubResult", (), {"data": SimpleNamespace(meas=empty_register)})()]
    assert extract_sampler_bitstrings(result) is None


def test_aggregate_bitstring_frequencies_returns_counts_and_probabilities() -> None:
    unique, probabilities, counts = aggregate_bitstring_frequencies(
        np.array([[True, False], [True, False], [False, True]], dtype=bool)
    )

    assert unique.tolist() == [[False, True], [True, False]]
    assert counts.tolist() == [1, 2]
    assert probabilities.tolist() == pytest.approx([1 / 3, 2 / 3])


def test_aggregate_bitstring_frequencies_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="no measurement"):
        aggregate_bitstring_frequencies(np.empty((0, 2), dtype=bool))


def test_summarize_bitstring_distribution_orders_ties_deterministically() -> None:
    summary = summarize_bitstring_distribution(
        np.array([[True, False], [False, True]], dtype=bool),
        np.array([0.5, 0.5]),
        counts=np.array([4, 4]),
    )

    assert summary == [
        {
            "bitstring": "01",
            "probability": 0.5,
            "normalized_probability": 0.5,
            "count": 4,
        },
        {
            "bitstring": "10",
            "probability": 0.5,
            "normalized_probability": 0.5,
            "count": 4,
        },
    ]


def test_summarize_bitstring_distribution_rejects_mismatched_shapes() -> None:
    assert (
        summarize_bitstring_distribution(
            np.zeros((2, 2), dtype=bool),
            np.array([1.0]),
        )
        == []
    )


def test_bitstring_from_row_uses_addon_display_order() -> None:
    assert bitstring_from_row(np.array([True, False, True], dtype=bool)) == "101"


def test_sqd_solver_keeps_legacy_sampling_aliases() -> None:
    assert sqd_solver._aggregate_bitstring_frequencies is aggregate_bitstring_frequencies
    assert sqd_solver._bitstring_from_sqd_row is bitstring_from_row
    assert sqd_solver._bitstrings_to_matrix is bitstrings_to_matrix
    assert sqd_solver._extract_sqd_sampler_bitstrings is extract_sampler_bitstrings
    assert sqd_solver._resolve_sqd_measurement_register is resolve_measurement_register
    assert sqd_solver._summarize_bitstring_distribution is summarize_bitstring_distribution
