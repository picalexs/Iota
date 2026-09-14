"""Tests for pure QSE fixed-sector ranking helpers."""

import numpy as np
import pytest

from worker.chemistry.algorithms.qse.sector import (
    dominant_sector_occupations,
    sector_excitation_coupling_score,
    sector_excitation_specs,
)
from worker.chemistry.sector_basis import (
    apply_fermionic_excitation_sector,
    hartree_fock_sector_state,
    sector_dimension,
)


class _SectorAction:
    norb = 4
    nelec = (2, 2)
    dimension = sector_dimension(norb, nelec)

    def __init__(self, coupled_address: int) -> None:
        self.coupled_address = coupled_address

    def matvec(self, _vector: np.ndarray) -> np.ndarray:
        result = np.zeros(self.dimension, dtype=complex)
        result[self.coupled_address] = 1.0
        return result


def test_dominant_sector_occupations_preserve_particle_counts() -> None:
    action = _SectorAction(coupled_address=0)

    occupations = dominant_sector_occupations(hartree_fock_sector_state(4, (2, 2)), action)

    assert occupations is not None
    occupied, virtual = occupations
    assert len(occupied) == 4
    assert len(virtual) == 4
    assert set(occupied).isdisjoint(virtual)


def test_sector_specs_rank_by_reference_coupling() -> None:
    reference = hartree_fock_sector_state(4, (2, 2))
    target_state = apply_fermionic_excitation_sector(
        reference,
        create_orbitals=(2, 6),
        annihilate_orbitals=(0, 4),
        norb=4,
        nelec=(2, 2),
    )
    action = _SectorAction(int(np.argmax(np.abs(target_state))))

    specs = sector_excitation_specs(reference, action, excitation_level="singles_doubles")
    top_spec = specs[0]
    score = sector_excitation_coupling_score(
        reference,
        action,
        h_reference=action.matvec(reference),
        spec=top_spec,
    )

    assert top_spec == ("double", (2, 6), (0, 4))
    assert score == pytest.approx(1.0)
