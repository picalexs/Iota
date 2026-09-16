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
from worker.chemistry.types import SQDResult


def _result(package: dict[str, object]) -> SQDResult:
    return SQDResult(
        algorithm="sqd",
        primary_energy=-1.0,
        primary_iterations=1,
        converged=True,
        sci_energies=[-1.0],
        configuration_recovery_trace=[],
        spin_diagnostics={},
        sci_result_package=package,
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


def test_seed_state_from_sqd_result_prefers_bitstrings_then_occupancies() -> None:
    bitstring_state, bitstring_source = seed_state_from_sqd_result_with_source(
        _result(
            {
                "final_occupancies": [0.6, 0.4, 0.7, 0.3],
                "nelec": [1, 1],
                "final_bitstring_probabilities": [{"bitstring": "0101", "probability": 1.0}],
            }
        ),
        target_size=16,
    )
    assert bitstring_source == "sqd_bitstring_probabilities"
    assert bitstring_state is not None
    assert int(np.argmax(np.abs(bitstring_state))) == 5

    occupancy_state, occupancy_source = seed_state_from_sqd_result_with_source(
        _result(
            {
                "final_occupancies": [0.9, 0.8, 0.7, 0.6],
                "nelec": [1, 1],
            }
        ),
        target_size=16,
    )
    assert occupancy_source == "sqd_occupancies"
    assert occupancy_state is not None
    assert int(np.argmax(np.abs(occupancy_state))) == 5
    assert seed_state_from_sqd_result(_result({}), target_size=16) is None


@pytest.mark.parametrize("occupancies", [[float("nan"), 0.4, 0.7, 0.3], [float("inf")] * 4])
def test_seed_state_from_sqd_result_rejects_non_finite_occupancies(
    occupancies: list[float],
) -> None:
    state, source = seed_state_from_sqd_result_with_source(
        _result({"final_occupancies": occupancies, "nelec": [1, 1]}),
        target_size=16,
    )

    assert state is None
    assert source == "invalid_occupancies"


@pytest.mark.parametrize(
    ("package", "target_size", "source"),
    [
        ({"final_occupancies": [0.5, 0.5]}, 8, "dimension_mismatch"),
        ({"final_occupancies": [0.5, 0.5, 0.5, 0.5]}, 16, "missing_electron_sector"),
        (
            {"final_occupancies": [0.5, 0.5, 0.5, 0.5], "nelec": [3, 0]},
            16,
            "invalid_electron_sector",
        ),
    ],
)
def test_seed_state_from_sqd_result_reports_unusable_seed_sources(
    package: dict[str, object],
    target_size: int,
    source: str,
) -> None:
    state, actual_source = seed_state_from_sqd_result_with_source(
        _result(package), target_size=target_size
    )

    assert state is None
    assert actual_source == source


def test_sector_seed_state_from_sqd_result_uses_sector_normalization() -> None:
    state, source = sector_seed_state_from_sqd_result_with_source(
        _result({"final_bitstring_probabilities": [{"bitstring": "0101", "probability": 1.0}]}),
        action=SimpleNamespace(norb=2, nelec=(1, 1), dimension=4),  # type: ignore[arg-type]
    )

    assert source == "sqd_bitstring_probabilities"
    assert state is not None
    assert np.linalg.norm(state) == pytest.approx(1.0)


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
