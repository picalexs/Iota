"""Tests for sector-basis input validation."""

from __future__ import annotations

import math

from worker.chemistry.sector_basis import (
    state_from_bitstring_probabilities,
    state_from_sector_amplitudes,
)


def test_state_from_bitstring_probabilities_rejects_non_finite_weights() -> None:
    for probability in (math.nan, math.inf):
        state = state_from_bitstring_probabilities(
            [{"bitstring": "10", "probability": probability}],
            norb=1,
            nelec=(1, 0),
        )

        assert state is None


def test_sector_state_builders_keep_small_nonzero_inputs() -> None:
    probability_state = state_from_bitstring_probabilities(
        [{"bitstring": "10", "probability": 1e-26}],
        norb=1,
        nelec=(1, 0),
    )
    amplitude_state = state_from_sector_amplitudes(
        [{"bitstring": "10", "amplitude": 1e-13}],
        norb=1,
        nelec=(1, 0),
    )

    assert probability_state is not None
    assert amplitude_state is not None
    assert probability_state[0] == 1.0
    assert amplitude_state[0] == 1.0
