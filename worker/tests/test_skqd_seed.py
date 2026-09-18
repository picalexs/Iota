"""Unit tests for pure SQD-to-SKQD seed-state helpers."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from worker.chemistry.algorithms.skqd import workflow as skqd_solver
from worker.chemistry.algorithms.skqd.seed import (
    sector_seed_state_from_sqd_result_with_source,
    seed_state_from_sqd_result,
    seed_state_from_sqd_result_with_source,
)
from worker.chemistry.sector_basis import bitstring_to_address, state_from_sector_amplitudes


def _result(package: dict[str, object], *, best_sci_state=None) -> SimpleNamespace:
    return SimpleNamespace(
        sci_result_package=package,
        best_sci_state=best_sci_state,
    )


def test_sqd_probabilities_and_occupancies_do_not_claim_to_be_coherent_states() -> None:
    package = {
        "best_occupancies": [0.9, 0.1, 0.9, 0.1],
        "final_occupancies": [0.1, 0.9, 0.1, 0.9],
        "nelec": [1, 1],
        "best_bitstring_probabilities": [{"bitstring": "0101", "probability": 1.0}],
        "final_bitstring_probabilities": [{"bitstring": "1010", "probability": 1.0}],
    }

    dense_state, dense_source = seed_state_from_sqd_result_with_source(
        _result(package), target_size=16
    )
    sector_state, sector_source = sector_seed_state_from_sqd_result_with_source(
        _result(package),
        action=SimpleNamespace(norb=2, nelec=(1, 1), dimension=4),  # type: ignore[arg-type]
    )

    assert dense_state is None
    assert sector_state is None
    assert dense_source == "missing_sqd_selected_ci_state"
    assert sector_source == "missing_sqd_selected_ci_state"


def test_selected_ci_seed_preserves_relative_phase_in_dense_and_sector_bases() -> None:
    coefficient = 1 / np.sqrt(2)
    selected_state = SimpleNamespace(
        amplitudes=np.asarray([[coefficient, -1j * coefficient]], dtype=complex),
        ci_strs_a=np.asarray([1]),
        ci_strs_b=np.asarray([1, 2]),
        norb=2,
        nelec=(1, 1),
    )
    package = {"best_iteration": 2, "iterations": 3}
    result = _result(package, best_sci_state=selected_state)

    dense_state, dense_source = seed_state_from_sqd_result_with_source(
        result, target_size=16
    )
    sector_state, sector_source = sector_seed_state_from_sqd_result_with_source(
        result,
        action=SimpleNamespace(norb=2, nelec=(1, 1), dimension=4),  # type: ignore[arg-type]
    )
    expected_sector_state = state_from_sector_amplitudes(
        [
            {"bitstring": "0101", "amplitude": [coefficient, 0.0]},
            {"bitstring": "1001", "amplitude": [0.0, -coefficient]},
        ],
        norb=2,
        nelec=(1, 1),
        dimension=4,
    )

    assert dense_source == sector_source == "sqd_best_selected_ci_coefficients"
    assert dense_state is not None
    assert dense_state[5] == pytest.approx(coefficient)
    assert dense_state[9] == pytest.approx(-1j * coefficient)
    assert sector_state is not None
    assert np.allclose(sector_state, expected_sector_state)
    for bitstring in ("0101", "1001"):
        sector_address = bitstring_to_address(bitstring, norb=2, nelec=(1, 1))
        assert dense_state[int(bitstring, 2)] == pytest.approx(sector_state[sector_address])


def test_equal_probabilities_with_opposite_phase_produce_distinct_coherent_seeds() -> None:
    coefficient = 1 / np.sqrt(2)

    def state_with_phase(phase: complex) -> SimpleNamespace:
        return SimpleNamespace(
            amplitudes=np.asarray([[coefficient, phase * coefficient]], dtype=complex),
            ci_strs_a=np.asarray([1]),
            ci_strs_b=np.asarray([1, 2]),
            norb=2,
            nelec=(1, 1),
        )

    positive, _ = seed_state_from_sqd_result_with_source(
        _result({}, best_sci_state=state_with_phase(1.0)), target_size=16
    )
    negative, _ = seed_state_from_sqd_result_with_source(
        _result({}, best_sci_state=state_with_phase(-1.0)), target_size=16
    )

    assert positive is not None and negative is not None
    assert np.array_equal(np.abs(positive) ** 2, np.abs(negative) ** 2)
    assert not np.allclose(positive, negative)
    coupling_hamiltonian = np.zeros((16, 16), dtype=complex)
    coupling_hamiltonian[5, 9] = coupling_hamiltonian[9, 5] = 1.0
    assert np.vdot(positive, coupling_hamiltonian @ positive).real == pytest.approx(1.0)
    assert np.vdot(negative, coupling_hamiltonian @ negative).real == pytest.approx(-1.0)


def test_selected_ci_seed_rejects_non_integer_determinant_masks() -> None:
    selected_state = SimpleNamespace(
        amplitudes=np.asarray([[1.0]], dtype=complex),
        ci_strs_a=np.asarray([1.5]),
        ci_strs_b=np.asarray([1]),
        norb=2,
        nelec=(1, 1),
    )

    state, source = seed_state_from_sqd_result_with_source(
        _result({}, best_sci_state=selected_state), target_size=16
    )

    assert state is None
    assert source == "invalid_sqd_selected_ci_state"


def test_sector_seed_state_from_sqd_result_uses_sector_normalization() -> None:
    state, source = sector_seed_state_from_sqd_result_with_source(
        _result({"final_bitstring_probabilities": [{"bitstring": "0101", "probability": 1.0}]}),
        action=SimpleNamespace(norb=2, nelec=(1, 1), dimension=4),  # type: ignore[arg-type]
    )

    assert source == "missing_sqd_selected_ci_state"
    assert state is None


def test_skqd_solver_keeps_legacy_seed_aliases() -> None:
    assert skqd_solver._seed_state_from_sqd_result is seed_state_from_sqd_result
    assert (
        skqd_solver._seed_state_from_sqd_result_with_source
        is seed_state_from_sqd_result_with_source
    )
    assert (
        skqd_solver._sector_seed_state_from_sqd_result_with_source
        is sector_seed_state_from_sqd_result_with_source
    )
