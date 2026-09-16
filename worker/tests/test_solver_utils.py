"""Tests for shared chemistry solver configuration helpers."""

from __future__ import annotations

import math

from worker.chemistry.solver_utils import bounded_int


def test_bounded_int_uses_default_for_non_finite_float() -> None:
    for value in (math.nan, math.inf, -math.inf):
        assert bounded_int(value, default=7, low=0, high=10) == 7
