"""Unit tests for the pure QSE fermionic excitation helpers."""

from __future__ import annotations

import numpy as np

from worker.chemistry.algorithms.qse.excitations import (
    apply_fermionic_excitation,
    apply_fermionic_ladder,
    build_sector_excitation_candidates,
    fermionic_excitation_specs,
    same_spin_count,
)


def test_apply_fermionic_ladder_enforces_occupancy_and_jordan_wigner_sign() -> None:
    assert apply_fermionic_ladder(0, 0, create=False) is None
    assert apply_fermionic_ladder(0, 0, create=True) == (1, 1)
    assert apply_fermionic_ladder(1, 0, create=True) is None
    assert apply_fermionic_ladder(3, 1, create=False) == (1, -1)


def test_apply_fermionic_excitation_moves_dense_state_amplitude() -> None:
    reference = np.zeros(4, dtype=complex)
    reference[1] = 2.0

    result = apply_fermionic_excitation(
        reference,
        create_orbitals=(1,),
        annihilate_orbitals=(0,),
        num_qubits=2,
    )

    expected = np.zeros(4, dtype=complex)
    expected[2] = 2.0
    np.testing.assert_array_equal(result, expected)


def test_apply_fermionic_excitation_keeps_small_nonzero_amplitudes() -> None:
    reference = np.zeros(4, dtype=complex)
    reference[1] = 1e-12

    result = apply_fermionic_excitation(
        reference,
        create_orbitals=(1,),
        annihilate_orbitals=(0,),
        num_qubits=2,
    )

    assert result[2] == 1e-12


def test_fermionic_excitation_specs_preserve_spin_sectors() -> None:
    singles = list(fermionic_excitation_specs(4, excitation_level="singles"))
    doubles = list(fermionic_excitation_specs(4, excitation_level="singles_doubles"))

    assert len(singles) == 4
    assert len(doubles) > len(singles)
    assert all(same_spin_count(targets, sources, norb=2) for _kind, targets, sources in doubles)


def test_build_sector_excitation_candidates_filters_spin_changes() -> None:
    candidates = build_sector_excitation_candidates(
        occupied=[0, 2],
        virtual=[1, 3],
        excitation_level="singles_doubles",
        norb=2,
    )

    assert candidates == [
        ("double", (1, 3), (0, 2)),
        ("single", (1,), (0,)),
        ("single", (3,), (2,)),
    ]
