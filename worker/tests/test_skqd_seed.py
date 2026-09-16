"""Unit tests for pure SQD-to-SKQD seed-state helpers."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from worker.chemistry.algorithms.skqd import workflow as skqd_solver
from worker.chemistry.algorithms.skqd.seed import (
    matches_spin_sector,
    parse_bitstring_index,
    resolve_sqd_electron_sector,
    sector_seed_state_from_sqd_result_with_source,
    seed_state_from_sqd_bitstrings,
    seed_state_from_sqd_result,
    seed_state_from_sqd_result_with_source,
)
from worker.chemistry.sector_basis import state_from_sector_amplitudes


def _result(package: dict[str, object], *, best_sci_state=None) -> SimpleNamespace:
    return SimpleNamespace(
        sci_result_package=package,
        best_sci_state=best_sci_state,
    )


def test_parse_bitstring_index_uses_little_endian_basis_indices() -> None:
    assert parse_bitstring_index("10 1", num_qubits=3) == 5
    assert parse_bitstring_index("102", num_qubits=3) is None
    assert parse_bitstring_index("01", num_qubits=3) is None


def test_matches_spin_sector_counts_alpha_and_beta_halves() -> None:
    assert matches_spin_sector(0b0101, norb=2, num_elec_a=1, num_elec_b=1) is True
    assert matches_spin_sector(0b0111, norb=2, num_elec_a=2, num_elec_b=1) is True
    assert matches_spin_sector(0b0001, norb=2, num_elec_a=1, num_elec_b=1) is False


def test_resolve_sqd_electron_sector_accepts_numeric_pair_only() -> None:
    assert resolve_sqd_electron_sector({"nelec": [1, 2.0]}) == (1, 2)
    assert resolve_sqd_electron_sector({"nelec": [1]}) is None
    assert resolve_sqd_electron_sector({"nelec": "1,2"}) is None
    assert resolve_sqd_electron_sector({"nelec": [1.5, 2]}) is None
    assert resolve_sqd_electron_sector({"nelec": [float("nan"), 2]}) is None
    assert resolve_sqd_electron_sector({"nelec": [10**1000, 2]}) is None
    assert resolve_sqd_electron_sector({"nelec": [True, 2]}) is None


def test_seed_state_from_sqd_bitstrings_filters_invalid_and_wrong_sector_rows() -> None:
    state = seed_state_from_sqd_bitstrings(
        {
            "final_bitstring_probabilities": [
                {"bitstring": "1111", "probability": 0.9},
                {"bitstring": "0101", "probability": 0.25},
                {"bitstring": "1010", "probability": 0.75},
                {"bitstring": "0000", "probability": 4.0},
            ]
        },
        target_size=16,
        num_qubits=4,
        norb=2,
        num_elec_a=1,
        num_elec_b=1,
    )

    assert state is not None
    assert np.linalg.norm(state) == pytest.approx(1.0)
    assert abs(state[5]) ** 2 == pytest.approx(0.25)
    assert abs(state[10]) ** 2 == pytest.approx(0.75)
    assert state[15] == pytest.approx(0.0)


@pytest.mark.parametrize("probability", [float("nan"), float("inf")])
def test_seed_state_from_sqd_bitstrings_skips_non_finite_probabilities(
    probability: float,
) -> None:
    state = seed_state_from_sqd_bitstrings(
        {
            "final_bitstring_probabilities": [
                {"bitstring": "0101", "probability": probability},
            ]
        },
        target_size=16,
        num_qubits=4,
        norb=2,
        num_elec_a=1,
        num_elec_b=1,
    )

    assert state is None


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


def test_sector_seed_state_from_sqd_result_uses_sector_normalization() -> None:
    state, source = sector_seed_state_from_sqd_result_with_source(
        _result({"final_bitstring_probabilities": [{"bitstring": "0101", "probability": 1.0}]}),
        action=SimpleNamespace(norb=2, nelec=(1, 1), dimension=4),  # type: ignore[arg-type]
    )

    assert source == "missing_sqd_selected_ci_state"
    assert state is None


def test_skqd_solver_keeps_legacy_seed_aliases() -> None:
    assert skqd_solver._parse_bitstring_index is parse_bitstring_index
    assert skqd_solver._matches_spin_sector is matches_spin_sector
    assert skqd_solver._resolve_sqd_electron_sector is resolve_sqd_electron_sector
    assert skqd_solver._seed_state_from_sqd_bitstrings is seed_state_from_sqd_bitstrings
    assert skqd_solver._seed_state_from_sqd_result is seed_state_from_sqd_result
    assert (
        skqd_solver._seed_state_from_sqd_result_with_source
        is seed_state_from_sqd_result_with_source
    )
    assert (
        skqd_solver._sector_seed_state_from_sqd_result_with_source
        is sector_seed_state_from_sqd_result_with_source
    )
