"""Optional VQE state-visualization payload construction for the algorithm package."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
from qiskit.quantum_info import Statevector

logger = logging.getLogger(__name__)

_BLOCH_QUBIT_CAP = 20
_DM_QUBIT_CAP = 6  # 2^6 = 64 -> 64x64 density matrix, manageable JSON payload


def bloch_vectors_from_statevector(
    amplitudes: np.ndarray,
    num_qubits: int,
) -> list[list[float]]:
    """Compute per-qubit Bloch vectors without materializing a density matrix."""
    indices = np.arange(amplitudes.size)
    probabilities = np.abs(amplitudes) ** 2
    vectors: list[list[float]] = []

    for qubit in range(num_qubits):
        mask = 1 << qubit
        bit_is_one = (indices & mask) != 0
        paired = amplitudes[indices ^ mask]

        bx = np.sum(np.conjugate(paired) * amplitudes)
        y_coeff = np.where(bit_is_one, -1j, 1j)
        by = np.sum(np.conjugate(paired) * y_coeff * amplitudes)
        bz = np.sum(np.where(bit_is_one, -probabilities, probabilities))
        vectors.append([float(np.real(bx)), float(np.real(by)), float(np.real(bz))])

    return vectors


def compute_quantum_state_data(
    ansatz: Any,
    optimal_point: np.ndarray,
    num_qubits: int,
) -> tuple[list[list[float]] | None, list[list[float]] | None, list[list[float]] | None]:
    """Compute bounded Bloch-vector and density-matrix payloads."""
    if num_qubits > _BLOCH_QUBIT_CAP:
        return None, None, None
    try:
        bound = ansatz.assign_parameters(optimal_point)
        statevector = Statevector(bound)
        amplitudes = np.asarray(statevector.data, dtype=complex)
        vectors = bloch_vectors_from_statevector(amplitudes, num_qubits)

        dm_real: list[list[float]] | None = None
        dm_imag: list[list[float]] | None = None
        if num_qubits <= _DM_QUBIT_CAP:
            matrix = np.outer(amplitudes, np.conjugate(amplitudes))
            dm_real = [
                [float(np.real(matrix[row, column])) for column in range(matrix.shape[1])]
                for row in range(matrix.shape[0])
            ]
            dm_imag = [
                [float(np.imag(matrix[row, column])) for column in range(matrix.shape[1])]
                for row in range(matrix.shape[0])
            ]

        return vectors, dm_real, dm_imag
    except Exception:
        logger.debug("Quantum state data computation failed (non-fatal)", exc_info=True)
        return None, None, None


def sector_diagnostics_from_ansatz(
    ansatz: Any,
    parameter_values: np.ndarray,
    *,
    num_spatial_orbitals: int,
    num_electrons_alpha: int,
    num_electrons_beta: int,
) -> dict[str, Any]:
    """Measure ideal sector leakage of the circuit used by a VQE result."""
    if num_spatial_orbitals < 1 or any(
        count < 0 or count > num_spatial_orbitals
        for count in (num_electrons_alpha, num_electrons_beta)
    ):
        raise ValueError("VQE sector diagnostics received an invalid electron sector")

    bound = ansatz.assign_parameters(np.asarray(parameter_values, dtype=float))
    amplitudes = np.asarray(Statevector(bound).data, dtype=complex)
    probabilities = np.abs(amplitudes) ** 2
    alpha_mask = (1 << num_spatial_orbitals) - 1
    valid_probability = 0.0
    for index, probability in enumerate(probabilities):
        alpha_count = (index & alpha_mask).bit_count()
        beta_count = ((index >> num_spatial_orbitals) & alpha_mask).bit_count()
        if alpha_count == num_electrons_alpha and beta_count == num_electrons_beta:
            valid_probability += float(probability)

    leakage = max(0.0, min(1.0, 1.0 - valid_probability))
    return {
        "sector_target": {
            "num_spatial_orbitals": num_spatial_orbitals,
            "num_electrons_alpha": num_electrons_alpha,
            "num_electrons_beta": num_electrons_beta,
        },
        "ideal_sector_probability": valid_probability,
        "ideal_sector_leakage": leakage,
        "sector_diagnostic_source": "ideal_statevector_from_ansatz",
    }


def should_compute_statevector_data(backend: Any, config: dict[str, Any]) -> bool:
    """Return True only when the run context represents an ideal statevector path."""
    backend_target = str(config.get("backend_target") or config.get("backend") or "").lower()
    if backend_target in {"aer", "aer_simulator", "ibm", "ibm_runtime"}:
        return False

    noise_profile = config.get("noise_profile")
    if isinstance(noise_profile, dict) and bool(noise_profile.get("enabled")):
        return False

    backend_name = backend.__class__.__name__.lower()
    backend_module = backend.__class__.__module__.lower()
    if "statevector" in backend_name or "statevector" in backend_module:
        return True

    return backend_target == "statevector"


__all__ = [
    "bloch_vectors_from_statevector",
    "compute_quantum_state_data",
    "sector_diagnostics_from_ansatz",
    "should_compute_statevector_data",
]
