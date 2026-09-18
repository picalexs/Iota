"""Spectral-width estimation for the paper-faithful SKQD time step.

The SKQD convergence analysis (Yu, Robledo-Moreno et al., arXiv:2501.09702)
requires the Krylov time step to be ``Delta t = pi / Delta E_{N-1}``, where
``Delta E_{N-1} = E_{N-1} - E_0`` is the spectral width of the Hamiltonian.
This module estimates that width from whichever representation is available,
preferring an exact extreme-eigenvalue solve when the operator is small enough
and otherwise using a conservative Pauli-coefficient bound.
"""

from __future__ import annotations

from typing import Any

import numpy as np

# Exact extreme eigenvalues via ``eigvalsh`` stay cheap only for modest dense
# operators. Above this dimension, use the conservative Pauli L1 bound.
_MAX_EXACT_SPECTRAL_DIMENSION = 4096
_MIN_SPECTRAL_WIDTH = 1e-9


def estimate_dense_spectral_width(operator: np.ndarray) -> tuple[float, str]:
    """Estimate ``Delta E_{N-1}`` for a dense Hermitian operator matrix."""
    matrix = np.asarray(operator, dtype=complex)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("SKQD spectral-width estimation requires a square operator")
    hermitian = 0.5 * (matrix + matrix.conj().T)
    dimension = int(hermitian.shape[0])
    if dimension <= _MAX_EXACT_SPECTRAL_DIMENSION:
        eigenvalues = np.linalg.eigvalsh(hermitian)
        width = float(eigenvalues[-1] - eigenvalues[0])
        return max(width, _MIN_SPECTRAL_WIDTH), "exact_dense_spectrum"
    # ``2 * ||H||_2`` upper-bounds ``E_{N-1} - E_0`` for any Hermitian operator.
    spectral_norm = float(np.linalg.norm(hermitian, ord=2))
    return max(2.0 * spectral_norm, _MIN_SPECTRAL_WIDTH), "dense_spectral_norm_bound"


def estimate_pauli_spectral_width(pauli_hamiltonian: Any) -> tuple[float, str]:
    """Estimate ``Delta E_{N-1}`` from a Pauli-sum Hamiltonian.

    ``sum_i |c_i|`` upper-bounds ``||H||`` for ``H = sum_i c_i P_i`` since each
    Pauli string has unit spectral norm. Twice that bounds the spectral width.
    """
    coeffs = getattr(pauli_hamiltonian, "coeffs", None)
    if coeffs is None:
        raise ValueError("SKQD Pauli spectral-width estimation requires coeffs")
    coefficient_l1 = float(np.sum(np.abs(np.asarray(coeffs, dtype=complex))))
    return max(2.0 * coefficient_l1, _MIN_SPECTRAL_WIDTH), "pauli_coefficient_l1_bound"


def estimate_action_spectral_width(
    action: Any,
    *,
    pauli_hamiltonian: Any | None = None,
) -> tuple[float, str]:
    """Estimate ``Delta E_{N-1}`` for a matrix-free fixed-sector action.

    Small sectors are diagonalized exactly via a dense reconstruction. Large
    sectors require a conservative bound from the Pauli representation. Power
    iteration estimates an extremal eigenvalue but does not bound the spectrum.
    """
    dimension = int(getattr(action, "dimension", 0))
    if dimension < 1:
        raise ValueError("SKQD action spectral-width estimation requires a positive dimension")
    if dimension <= _MAX_EXACT_SPECTRAL_DIMENSION:
        basis = np.eye(dimension, dtype=complex)
        columns = [action.matvec(basis[:, index]) for index in range(dimension)]
        matrix = np.column_stack(columns)
        matrix = 0.5 * (matrix + matrix.conj().T)
        eigenvalues = np.linalg.eigvalsh(matrix)
        width = float(eigenvalues[-1] - eigenvalues[0])
        return max(width, _MIN_SPECTRAL_WIDTH), "exact_sector_spectrum"
    if pauli_hamiltonian is None:
        raise ValueError(
            "Large-sector SKQD time-step resolution requires a conservative Pauli spectral bound"
        )
    return estimate_pauli_spectral_width(pauli_hamiltonian)


def paper_time_step(spectral_width: float) -> float:
    """Return the paper-faithful Krylov time step ``Delta t = pi / Delta E_{N-1}``."""
    width = max(float(spectral_width), _MIN_SPECTRAL_WIDTH)
    return float(np.pi / width)


__all__ = [
    "estimate_action_spectral_width",
    "estimate_dense_spectral_width",
    "estimate_pauli_spectral_width",
    "paper_time_step",
]
