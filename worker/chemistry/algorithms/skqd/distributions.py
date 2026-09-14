"""Pure computational-basis distribution helpers for the SKQD algorithm package."""

from __future__ import annotations

import numpy as np

from worker.chemistry.time_evolution import (
    exact_time_evolution_state_from_spectrum,
    prepare_exact_time_evolution,
)


def statevector_bitstring_distribution(
    state: np.ndarray | None,
    *,
    max_entries: int = 32,
) -> list[dict[str, float | str]]:
    """Return the largest computational-basis probabilities in a statevector."""
    if state is None:
        return []
    vector = np.asarray(state, dtype=complex).reshape(-1)
    if vector.size < 1:
        return []
    num_qubits = int(round(np.log2(vector.size)))
    if 2**num_qubits != vector.size:
        return []

    probabilities = np.abs(vector) ** 2
    order = np.argsort(probabilities)[::-1]
    distribution: list[dict[str, float | str]] = []
    for basis_index in order[:max_entries]:
        probability = float(probabilities[basis_index])
        if probability <= 1e-12:
            break
        distribution.append(
            {
                "bitstring": format(int(basis_index), f"0{num_qubits}b"),
                "probability": round(probability, 12),
            }
        )
    return distribution


def time_evolved_bitstring_distribution(
    operator: np.ndarray,
    seed_state: np.ndarray,
    *,
    num_steps: int,
    time_step: float,
    max_entries: int = 32,
) -> list[dict[str, float | str]]:
    """Aggregate computational-basis probabilities from exact evolved states."""
    seed = np.asarray(seed_state, dtype=complex).reshape(-1)
    seed_norm = float(np.linalg.norm(seed))
    if np.isclose(seed_norm, 0.0) or num_steps < 1:
        return []
    seed = seed / seed_norm

    dim = seed.size
    num_qubits = int(round(np.log2(dim)))
    if 2**num_qubits != dim:
        return []

    eigenvalues, eigenvectors = prepare_exact_time_evolution(operator)
    seed_projection = eigenvectors.conj().T @ seed
    aggregate = np.zeros(dim, dtype=float)
    for step in range(num_steps):
        current_time = float(step * time_step)
        if np.isclose(current_time, 0.0):
            evolved = seed
        else:
            evolved = exact_time_evolution_state_from_spectrum(
                eigenvalues,
                eigenvectors,
                seed,
                time_step=current_time,
                state_projection=seed_projection,
            )
        aggregate += np.abs(evolved) ** 2

    aggregate /= float(num_steps)
    pseudo_state = np.sqrt(aggregate).astype(complex)
    return statevector_bitstring_distribution(pseudo_state, max_entries=max_entries)


__all__ = ["statevector_bitstring_distribution", "time_evolved_bitstring_distribution"]
