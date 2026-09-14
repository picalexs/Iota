"""Qiskit estimator objective adapter for the VQE algorithm package."""

from __future__ import annotations

from typing import Any

import numpy as np
from qiskit.quantum_info import SparsePauliOp


def extract_pub_energy(pub_result: Any) -> float:
    """Extract a scalar expectation value from a Qiskit V2 PUB result."""
    data = getattr(pub_result, "data", None)
    if data is None:
        raise ValueError("Estimator PUB result missing data payload")

    evs = getattr(data, "evs", None)
    if evs is None:
        raise ValueError("Estimator PUB result missing expectation values")

    if isinstance(evs, np.ndarray):
        if evs.size < 1:
            raise ValueError("Estimator PUB returned an empty expectation array")
        return float(np.real(evs.reshape(-1)[0]))

    if isinstance(evs, (list, tuple)) and evs:
        if not isinstance(evs[0], (int, float)):
            raise ValueError("Estimator PUB expectation value is not numeric")
        return float(evs[0])

    if isinstance(evs, (int, float)):
        return float(evs)

    raise ValueError("Estimator PUB expectation values have an unsupported format")


def extract_pub_standard_error(pub_result: Any) -> float | None:
    """Extract an optional V2 estimator standard error from one PUB result."""
    data = getattr(pub_result, "data", None)
    standard_errors = getattr(data, "stds", None) if data is not None else None
    if standard_errors is None:
        return None
    if isinstance(standard_errors, np.ndarray):
        if standard_errors.size < 1:
            return None
        value = float(np.real(standard_errors.reshape(-1)[0]))
    elif isinstance(standard_errors, (list, tuple)) and standard_errors:
        if not isinstance(standard_errors[0], (int, float, np.number)):
            return None
        value = float(np.real(standard_errors[0]))
    elif isinstance(standard_errors, (int, float, np.number)):
        value = float(np.real(standard_errors))
    else:
        return None
    return value if np.isfinite(value) and value >= 0.0 else None


def evaluate_energy(
    *,
    backend: Any,
    ansatz: Any,
    operator: SparsePauliOp,
    parameter_values: np.ndarray,
) -> float:
    """Evaluate the VQE objective with a Qiskit V2 estimator PUB."""
    pub = (ansatz, [operator], [parameter_values.tolist()])
    result = backend.run([pub]).result()
    if len(result) < 1:
        raise ValueError("Estimator returned no PUB results")
    return extract_pub_energy(result[0])


def evaluate_energy_with_uncertainty(
    *,
    backend: Any,
    ansatz: Any,
    operator: SparsePauliOp,
    parameter_values: np.ndarray,
) -> tuple[float, float | None]:
    """Evaluate VQE energy and return an optional estimator standard error."""
    pub = (ansatz, [operator], [parameter_values.tolist()])
    result = backend.run([pub]).result()
    if len(result) < 1:
        raise ValueError("Estimator returned no PUB results")
    return extract_pub_energy(result[0]), extract_pub_standard_error(result[0])
