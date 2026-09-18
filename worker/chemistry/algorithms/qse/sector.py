"""Pure fixed-sector excitation ranking helpers for the QSE algorithm package."""

from __future__ import annotations

import numpy as np

from worker.chemistry.algorithms.qse.excitations import (
    build_sector_excitation_candidates,
    fermionic_excitation_specs,
)
from worker.chemistry.hamiltonian_action import HamiltonianAction
from worker.chemistry.sector_basis import (
    address_to_bitstring,
    apply_fermionic_excitation_sector,
    display_bitstring_to_basis_index,
)

DOMINANT_DETERMINANT_SELECTION_THRESHOLD = 0.5


def dominant_sector_occupations(
    reference_state: np.ndarray,
    action: HamiltonianAction,
) -> tuple[list[int], list[int]] | None:
    """Return occupied and virtual orbitals for the dominant sector determinant."""
    vector = np.asarray(reference_state, dtype=complex).reshape(-1)
    if vector.size != action.dimension:
        return None
    if not hasattr(action, "nelec"):
        return None
    probabilities = np.abs(vector) ** 2
    if probabilities.size == 0:
        return None
    dominant_address = int(np.argmax(probabilities))
    if float(probabilities[dominant_address]) < DOMINANT_DETERMINANT_SELECTION_THRESHOLD:
        return None

    bitstring = address_to_bitstring(
        dominant_address,
        norb=action.norb,
        nelec=action.nelec,
    )
    basis_index = display_bitstring_to_basis_index(bitstring, num_qubits=2 * action.norb)
    occupied = [
        orbital for orbital in range(2 * action.norb) if (basis_index & (1 << orbital)) != 0
    ]
    virtual = [orbital for orbital in range(2 * action.norb) if (basis_index & (1 << orbital)) == 0]
    return occupied, virtual


def sector_excitation_coupling_score(
    reference_state: np.ndarray,
    action: HamiltonianAction,
    *,
    h_reference: np.ndarray,
    spec: tuple[str, tuple[int, ...], tuple[int, ...]],
) -> float:
    """Score a sector excitation by its coupling to ``H|reference>``."""
    _kind, create_orbitals, annihilate_orbitals = spec
    candidate = apply_fermionic_excitation_sector(
        reference_state,
        create_orbitals=create_orbitals,
        annihilate_orbitals=annihilate_orbitals,
        norb=action.norb,
        nelec=action.nelec,
    )
    norm = float(np.linalg.norm(candidate))
    if norm == 0.0:
        return 0.0
    return float(abs(np.vdot(candidate / norm, h_reference)))


def sector_excitation_specs(
    reference_state: np.ndarray,
    action: HamiltonianAction,
    *,
    excitation_level: str,
) -> list[tuple[str, tuple[int, ...], tuple[int, ...]]]:
    """Return useful sector excitations ordered by reference coupling."""
    occupations = dominant_sector_occupations(reference_state, action)
    if occupations is None:
        return list(fermionic_excitation_specs(2 * action.norb, excitation_level=excitation_level))

    occupied, virtual = occupations
    h_reference = action.matvec(reference_state)
    candidates = build_sector_excitation_candidates(
        occupied=occupied,
        virtual=virtual,
        excitation_level=excitation_level,
        norb=action.norb,
    )
    return sorted(
        candidates,
        key=lambda spec: sector_excitation_coupling_score(
            reference_state,
            action,
            h_reference=h_reference,
            spec=spec,
        ),
        reverse=True,
    )


__all__ = [
    "DOMINANT_DETERMINANT_SELECTION_THRESHOLD",
    "dominant_sector_occupations",
    "sector_excitation_coupling_score",
    "sector_excitation_specs",
]
