"""Tests for sector-basis input validation."""

from __future__ import annotations

import math

from worker.chemistry.sector_basis import state_from_bitstring_probabilities


def test_state_from_bitstring_probabilities_rejects_non_finite_weights() -> None:
    for probability in (math.nan, math.inf):
        state = state_from_bitstring_probabilities(
            [{"bitstring": "10", "probability": probability}],
            norb=1,
            nelec=(1, 0),
        )

        assert state is None
