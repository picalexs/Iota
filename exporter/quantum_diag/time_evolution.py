"""Time evolution operators for quantum systems."""

from __future__ import annotations

import numpy as np
from scipy.linalg import expm


def build_trotter_time_evolution(
    hamiltonian: np.ndarray, time_step: float, trotter_steps: int
) -> np.ndarray:
    """Build Trotter approximation of exp(-i H t).

    Uses first-order Trotter with matrix exponential for each step.
    For a Hamiltonian H and time step dt, applies:
        U(dt) ≈ exp(-i H dt)
    repeatedly for trotter_steps.

    Args:
        hamiltonian: Hermitian Hamiltonian matrix of shape (n, n).
        time_step: Time step dt for each Trotter step.
        trotter_steps: Number of Trotter steps to apply.

    Returns:
        Unitary matrix U of shape (n, n) representing exp(-i H t_total)
        where t_total = time_step * trotter_steps.
    """
    if trotter_steps < 1:
        raise ValueError(f"trotter_steps must be >= 1, got {trotter_steps}")

    n = hamiltonian.shape[0]
    u_total = np.eye(n, dtype=complex)

    for _ in range(trotter_steps):
        # Single Trotter step: U(dt) = exp(-i H dt)
        exponent = -1j * hamiltonian * time_step
        u_step = expm(exponent)
        u_total = u_step @ u_total

    return u_total


def exact_time_evolution(hamiltonian: np.ndarray, total_time: float) -> np.ndarray:
    """Exact unitary time evolution via matrix exponential.

    Computes U(t) = exp(-i H t) directly using scipy.linalg.expm.

    Args:
        hamiltonian: Hermitian Hamiltonian matrix of shape (n, n).
        total_time: Total evolution time.

    Returns:
        Unitary matrix U of shape (n, n) representing exp(-i H t).
    """
    exponent = -1j * hamiltonian * total_time
    return expm(exponent)
