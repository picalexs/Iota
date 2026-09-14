"""Pure SQD sampler-output normalization and distribution helpers for the algorithm package."""

from __future__ import annotations

from typing import Any

import numpy as np


def bitstrings_to_matrix(bitstrings: list[Any], *, num_bits: int) -> np.ndarray:
    """Convert raw primitive bitstrings into a boolean matrix."""
    matrix = np.zeros((len(bitstrings), num_bits), dtype=bool)
    for row, bitstring in enumerate(bitstrings):
        normalized = str(bitstring).replace(" ", "")
        if len(normalized) != num_bits:
            raise ValueError("SQD sampler bitstring width does not match Hamiltonian qubits")
        matrix[row, :] = [char == "1" for char in normalized]
    return matrix


def resolve_measurement_register(data: Any) -> Any | None:
    """Resolve the measurement container from a primitive result payload."""
    if hasattr(data, "keys"):
        for key in data.keys():
            candidate = getattr(data, str(key), None)
            if candidate is not None and hasattr(candidate, "get_bitstrings"):
                return candidate

    candidate = getattr(data, "meas", None)
    if candidate is not None and hasattr(candidate, "get_bitstrings"):
        return candidate
    return None


def extract_sampler_bitstrings(result: Any) -> list[Any] | None:
    """Find the first measurement payload that exposes shot bitstrings."""
    if len(result) < 1:
        return None

    data = getattr(result[0], "data", None)
    if data is None:
        return None

    measured = resolve_measurement_register(data)
    if measured is None:
        return None

    bitstrings = measured.get_bitstrings()
    if not isinstance(bitstrings, list) or not bitstrings:
        return None
    return bitstrings


def aggregate_bitstring_frequencies(
    bitstring_matrix: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Collapse repeated shot-level bitstrings into unique rows and probabilities."""
    matrix = np.asarray(bitstring_matrix, dtype=bool)
    if matrix.ndim != 2 or matrix.shape[0] == 0:
        raise ValueError("SQD sampler returned no measurement bitstrings")

    unique_rows, counts = np.unique(matrix, axis=0, return_counts=True)
    probabilities = counts.astype(float) / float(np.sum(counts))
    return unique_rows.astype(bool), probabilities, counts.astype(int)


def aggregate_weighted_bitstring_probabilities(
    bitstring_matrix: np.ndarray,
    probabilities: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Merge duplicate rows while preserving their supplied probability mass."""
    matrix = np.asarray(bitstring_matrix, dtype=bool)
    probs = np.asarray(probabilities, dtype=float).reshape(-1)
    if matrix.ndim != 2 or matrix.shape[0] == 0:
        raise ValueError("SQD weighted aggregation needs at least one bitstring")
    if probs.size != matrix.shape[0]:
        raise ValueError("SQD weighted probabilities must match bitstring rows")
    if np.any(~np.isfinite(probs)) or np.any(probs < 0.0):
        raise ValueError("SQD weighted probabilities must be finite and non-negative")

    unique_rows, inverse = np.unique(matrix, axis=0, return_inverse=True)
    merged_probabilities = np.zeros(unique_rows.shape[0], dtype=float)
    np.add.at(merged_probabilities, inverse, probs)
    return unique_rows.astype(bool), merged_probabilities


def bitstring_from_row(row: np.ndarray) -> str:
    """Return a display bitstring in qiskit-addon-sqd/ffsim order."""
    return "".join("1" if bool(value) else "0" for value in np.asarray(row, dtype=bool))


def summarize_bitstring_distribution(
    bitstrings: np.ndarray,
    probabilities: np.ndarray,
    *,
    counts: np.ndarray | None = None,
    limit: int | None = 32,
) -> list[dict[str, Any]]:
    """Serialize bitstring probabilities, optionally keeping only the largest rows."""
    rows = np.asarray(bitstrings, dtype=bool)
    probs = np.asarray(probabilities, dtype=float).reshape(-1)
    if rows.ndim != 2 or probs.size != rows.shape[0]:
        return []

    raw_counts = None if counts is None else np.asarray(counts, dtype=int).reshape(-1)
    probability_sum = float(np.sum(probs))
    order = sorted(
        range(rows.shape[0]),
        key=lambda idx: (-float(probs[idx]), bitstring_from_row(rows[idx])),
    )

    summary: list[dict[str, Any]] = []
    for idx in order[:limit]:
        entry: dict[str, Any] = {
            "bitstring": bitstring_from_row(rows[idx]),
            "probability": round(float(probs[idx]), 12),
        }
        if probability_sum > 0.0:
            entry["normalized_probability"] = round(float(probs[idx] / probability_sum), 12)
        if raw_counts is not None and raw_counts.size == rows.shape[0]:
            entry["count"] = int(raw_counts[idx])
        summary.append(entry)
    return summary


__all__ = [
    "aggregate_bitstring_frequencies",
    "aggregate_weighted_bitstring_probabilities",
    "bitstring_from_row",
    "bitstrings_to_matrix",
    "extract_sampler_bitstrings",
    "resolve_measurement_register",
    "summarize_bitstring_distribution",
]
