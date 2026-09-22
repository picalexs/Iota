"""Compatibility helpers for Qiskit Aer primitives across V1 and V2 APIs."""

from __future__ import annotations

from typing import Iterable

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import SparsePauliOp

try:
    from qiskit_aer.primitives import EstimatorV2 as AerEstimator

    HAS_ESTIMATOR_V2 = True
except ImportError:  # pragma: no cover - depends on installed qiskit-aer version
    from qiskit_aer.primitives import Estimator as AerEstimator

    HAS_ESTIMATOR_V2 = False

try:
    from qiskit_aer.primitives import SamplerV2 as AerSampler

    HAS_SAMPLER_V2 = True
except ImportError:  # pragma: no cover - depends on installed qiskit-aer version
    from qiskit_aer.primitives import Sampler as AerSampler

    HAS_SAMPLER_V2 = False


def create_estimator() -> AerEstimator:
    """Instantiate an Aer estimator, preferring V2 when available."""
    return AerEstimator()


def create_sampler() -> AerSampler:
    """Instantiate an Aer sampler, preferring V2 when available."""
    return AerSampler()


def _as_float_list(values: Iterable[float] | np.ndarray) -> list[float]:
    return [float(v) for v in np.asarray(values, dtype=float).reshape(-1)]


def estimate_expectation(
    estimator: AerEstimator,
    circuit: QuantumCircuit,
    observable: SparsePauliOp,
) -> float:
    """Evaluate expectation value for a bound circuit and observable."""
    if HAS_ESTIMATOR_V2:
        result = estimator.run([(circuit, observable)]).result()
        return float(np.asarray(result[0].data.evs).reshape(-1)[0])

    result = estimator.run(circuit, observable).result()
    return float(result.values[0])


def sample_counts(
    sampler: AerSampler,
    circuit: QuantumCircuit,
    shots: int,
    parameter_values: Iterable[float] | np.ndarray | None = None,
) -> dict[str, int]:
    """Sample bitstring counts from a (possibly parameterized) measured circuit."""
    if HAS_SAMPLER_V2:
        if parameter_values is None:
            pub = circuit
        else:
            pub = (circuit, _as_float_list(parameter_values))

        result = sampler.run([pub], shots=shots).result()
        data = result[0].data

        if hasattr(data, "meas"):
            counts = data.meas.get_counts()
        else:  # pragma: no cover - defensive fallback for register naming variants
            counts = None
            for field_name in data.keys():
                field_value = getattr(data, field_name)
                if hasattr(field_value, "get_counts"):
                    counts = field_value.get_counts()
                    break
            if counts is None:
                raise RuntimeError("Sampler result did not expose measurement counts")

        return {str(bitstring): int(count) for bitstring, count in counts.items()}

    if parameter_values is None:
        job = sampler.run([circuit], shots=shots)
    else:
        job = sampler.run([circuit], parameter_values=[_as_float_list(parameter_values)], shots=shots)

    result = job.result()
    quasi_dist = result.quasi_dists[0]
    counts: dict[str, int] = {}

    for bitstring, prob in quasi_dist.items():
        if isinstance(bitstring, int):
            key = format(bitstring, f"0{circuit.num_qubits}b")
        else:
            key = str(bitstring)
        counts[key] = int(np.round(float(prob) * shots))

    return counts
