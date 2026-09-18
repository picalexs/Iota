"""Pure QSE reference-input normalization helpers for the algorithm package."""

from __future__ import annotations

from typing import Any

import numpy as np


def string_option(value: Any, *, default: str) -> str:
    """Normalize optional string settings where API payloads may contain null."""
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def parse_reference_scalar(value: Any) -> complex:
    """Parse a JSON-safe real or complex reference amplitude."""
    if isinstance(value, complex):
        return value
    if isinstance(value, (int, float)):
        return complex(float(value), 0.0)
    if isinstance(value, dict):
        real = value.get("real", 0.0)
        imag = value.get("imag", value.get("imaginary", 0.0))
        if isinstance(real, (int, float)) and isinstance(imag, (int, float)):
            return complex(float(real), float(imag))
    if isinstance(value, (list, tuple)) and len(value) == 2:
        real, imag = value
        if isinstance(real, (int, float)) and isinstance(imag, (int, float)):
            return complex(float(real), float(imag))
    raise ValueError("QSE reference amplitudes must be numeric or real/imag pairs")


def normalize_reference_state_vector(raw_vector: Any, *, vector_size: int) -> np.ndarray:
    """Normalize and validate a provided QSE reference-state vector."""
    if isinstance(raw_vector, np.ndarray):
        vector = np.asarray(raw_vector, dtype=complex)
    elif isinstance(raw_vector, (list, tuple)):
        vector = np.asarray([parse_reference_scalar(value) for value in raw_vector], dtype=complex)
    else:
        raise ValueError("QSE provided_state_vector must be a numeric list")

    if vector.ndim != 1:
        raise ValueError("QSE provided_state_vector must be one-dimensional")
    if vector.size != vector_size:
        raise ValueError("QSE provided_state_vector size must match Hamiltonian dimension")

    norm = float(np.linalg.norm(vector))
    if not np.isfinite(norm) or norm == 0.0:
        raise ValueError("QSE provided_state_vector norm must be non-zero")
    return vector / norm


def vector_size_to_qubits(vector_size: int) -> int:
    """Resolve qubit count from a dense state-vector dimension."""
    if vector_size < 1:
        raise ValueError("QSE reference vector size must be positive")
    num_qubits = int(round(np.log2(vector_size)))
    if 2**num_qubits != vector_size:
        raise ValueError("QSE operator dimension must be a power of two")
    return num_qubits


__all__ = [
    "normalize_reference_state_vector",
    "parse_reference_scalar",
    "string_option",
    "vector_size_to_qubits",
]
