"""Tests for pure SKQD state-distribution diagnostics."""

import numpy as np

from worker.chemistry.algorithms.skqd.distributions import (
    statevector_bitstring_distribution,
    time_evolved_bitstring_distribution,
)


def test_statevector_distribution_orders_and_limits_probabilities() -> None:
    state = np.array([0.0, 0.5, 0.0, np.sqrt(0.75)], dtype=complex)

    distribution = statevector_bitstring_distribution(state, max_entries=1)

    assert distribution == [{"bitstring": "11", "probability": 0.75}]


def test_statevector_distribution_rejects_non_power_of_two_vectors() -> None:
    assert statevector_bitstring_distribution(np.ones(3, dtype=complex)) == []
    assert statevector_bitstring_distribution(None) == []


def test_time_evolved_distribution_normalizes_seed_and_averages_steps() -> None:
    operator = np.diag([0.0, 1.0]).astype(complex)
    seed = np.array([3.0, 0.0], dtype=complex)

    distribution = time_evolved_bitstring_distribution(
        operator,
        seed,
        num_steps=3,
        time_step=0.5,
        max_entries=1,
    )

    assert distribution == [{"bitstring": "0", "probability": 1.0}]
