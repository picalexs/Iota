"""Reference-state provenance and deterministic identity helpers."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any

import numpy as np

_STATE_FINGERPRINT_PREFIX = b"licenta-reference-state:v1\0"
_CIRCUIT_FINGERPRINT_PREFIX = b"licenta-reference-circuit:v1\0"


@dataclass(frozen=True)
class ReferenceDescriptor:
    """Describe how a reference state was prepared and executed."""

    reference_source: str
    preparation_path: str
    execution_mode: str
    target_sector: Mapping[str, Any] | None = None
    sector_probability: float | None = None
    reference_energy: float | None = None
    variance: float | None = None
    state_fingerprint: str | None = None
    circuit_fingerprint: str | None = None
    backend_target: str | None = None
    ansatz_name: str | None = None
    metadata: Mapping[str, Any] | None = None

    def to_metadata(self) -> dict[str, Any]:
        """Return a JSON-safe copy of the descriptor."""
        return _json_safe(
            {
                "reference_source": self.reference_source,
                "preparation_path": self.preparation_path,
                "target_sector": self.target_sector,
                "sector_probability": self.sector_probability,
                "reference_energy": self.reference_energy,
                "variance": self.variance,
                "state_fingerprint": self.state_fingerprint,
                "circuit_fingerprint": self.circuit_fingerprint,
                "backend_target": self.backend_target,
                "execution_mode": self.execution_mode,
                "ansatz_name": self.ansatz_name,
                "metadata": self.metadata,
            }
        )


def build_reference_descriptor(
    *,
    state: Any,
    reference_source: str,
    preparation_path: str,
    execution_mode: str,
    target_sector: Mapping[str, Any] | None = None,
    sector_probability: float | None = None,
    reference_energy: float | None = None,
    variance: float | None = None,
    circuit_metadata: Any | None = None,
    backend_target: str | None = None,
    ansatz_name: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a persisted descriptor for one prepared reference state."""
    return ReferenceDescriptor(
        reference_source=reference_source,
        preparation_path=preparation_path,
        execution_mode=execution_mode,
        target_sector=target_sector,
        sector_probability=sector_probability,
        reference_energy=reference_energy,
        variance=variance,
        state_fingerprint=fingerprint_state_vector(state),
        circuit_fingerprint=(
            fingerprint_circuit_metadata(circuit_metadata)
            if circuit_metadata is not None
            else None
        ),
        backend_target=backend_target,
        ansatz_name=ansatz_name,
        metadata=metadata,
    ).to_metadata()


def fingerprint_state_vector(state: Any) -> str:
    """Return a deterministic fingerprint for a normalized complex state vector.

    The input is normalized to unit Euclidean norm and canonicalized up to a
    global phase. This makes equivalent state representations produce the same
    fingerprint while preserving vector dimension and amplitudes.
    """
    vector = np.asarray(state, dtype=np.complex128)
    if vector.ndim != 1:
        raise ValueError("state must be a one-dimensional vector")
    if vector.size == 0:
        raise ValueError("state must not be empty")
    if not np.all(np.isfinite(vector)):
        raise ValueError("state must contain only finite values")

    norm = float(np.linalg.norm(vector))
    if not np.isfinite(norm) or norm <= 0.0:
        raise ValueError("state must have a finite, non-zero norm")
    vector = vector / norm

    nonzero = np.flatnonzero(np.abs(vector) > 0.0)
    phase = vector[nonzero[0]] / abs(vector[nonzero[0]])
    vector = vector / phase
    vector.real[vector.real == 0.0] = 0.0
    vector.imag[vector.imag == 0.0] = 0.0

    canonical = np.empty(vector.size * 2, dtype=">f8")
    canonical[0::2] = vector.real
    canonical[1::2] = vector.imag
    payload = len(vector).to_bytes(8, byteorder="big") + canonical.tobytes()
    return hashlib.sha256(_STATE_FINGERPRINT_PREFIX + payload).hexdigest()


def fingerprint_circuit_metadata(serialized_metadata: Any) -> str:
    """Return a deterministic fingerprint for serialized circuit metadata."""
    serialized = _canonical_json(serialized_metadata).encode("utf-8")
    return hashlib.sha256(_CIRCUIT_FINGERPRINT_PREFIX + serialized).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(
        _json_safe(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _json_safe_mapping(value: Mapping[Any, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise TypeError("metadata mapping keys must be strings")
        normalized[key] = _json_safe(item)
    return normalized


def _json_safe_complex(value: complex) -> dict[str, float]:
    if not np.isfinite(value.real) or not np.isfinite(value.imag):
        raise ValueError("metadata must contain only finite numbers")
    return {"imag": float(value.imag), "real": float(value.real)}


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not np.isfinite(value):
            raise ValueError("metadata must contain only finite numbers")
        return value
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, np.ndarray):
        return _json_safe(value.tolist())
    if isinstance(value, Mapping):
        return _json_safe_mapping(value)
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if is_dataclass(value) and not isinstance(value, type):
        return _json_safe(asdict(value))
    if isinstance(value, complex):
        return _json_safe_complex(value)
    raise TypeError(f"value of type {type(value).__name__} is not JSON-safe")


__all__ = [
    "ReferenceDescriptor",
    "build_reference_descriptor",
    "fingerprint_circuit_metadata",
    "fingerprint_state_vector",
]
