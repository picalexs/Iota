"""Overlap measurement and inner product estimation."""

from __future__ import annotations

import numpy as np


def estimate_overlap(state_a: np.ndarray, state_b: np.ndarray) -> complex:
    """Estimate overlap (inner product) <a|b>.

    Computes the inner product of two quantum states using np.vdot,
    which is <a|b> = conj(a) · b.

    Args:
        state_a: Quantum state vector of shape (n,).
        state_b: Quantum state vector of shape (n,).

    Returns:
        Complex inner product <a|b>.
    """
    return np.vdot(state_a, state_b)


def hadamard_test_overlap_proxy(state_a: np.ndarray, state_b: np.ndarray) -> float:
    """Deterministic proxy for Hadamard test overlap measurement.

    For now, returns Re(<a|b>) bounded in [-1, 1].
    In a quantum setting, this would come from a Hadamard test;
    here it is deterministic but captures the real part of the overlap.

    Args:
        state_a: Quantum state vector of shape (n,).
        state_b: Quantum state vector of shape (n,).

    Returns:
        Real number in [-1, 1] representing Re(<a|b>).
    """
    overlap = estimate_overlap(state_a, state_b)
    real_part = float(np.real(overlap))
    # Clamp to [-1, 1] to ensure proxy bounds
    return np.clip(real_part, -1.0, 1.0)
