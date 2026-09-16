"""Tests for shared worker state-vector boundary normalization."""

from __future__ import annotations

import numpy as np
import pytest

from worker.chemistry.state_vectors import normalize_state_vector


def test_normalize_state_vector_flattens_and_normalizes() -> None:
    normalized = normalize_state_vector(
        np.array([[3.0], [4.0]], dtype=complex),
        error_message="state must be non-zero",
        expected_size=2,
    )

    np.testing.assert_allclose(normalized, [0.6, 0.8])


def test_normalize_state_vector_rejects_zero_and_wrong_size() -> None:
    with pytest.raises(ValueError, match="state must be non-zero"):
        normalize_state_vector(
            np.zeros(2, dtype=complex),
            error_message="state must be non-zero",
        )

    with pytest.raises(ValueError, match="expected size"):
        normalize_state_vector(
            np.ones(2, dtype=complex),
            error_message="state must be non-zero",
            expected_size=3,
        )
