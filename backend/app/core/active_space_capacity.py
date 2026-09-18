"""Basis-capacity helpers for active-space validation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

_VALENCE_ELECTRONS: dict[str, int] = {
    "H": 1,
    "He": 2,
    "Li": 1,
    "Be": 2,
    "B": 3,
    "C": 4,
    "N": 5,
    "O": 6,
    "F": 7,
    "Ne": 8,
    "Na": 1,
    "Mg": 2,
    "Al": 3,
    "Si": 4,
    "P": 5,
    "S": 6,
    "Cl": 7,
    "Ar": 8,
}

_VALENCE_ORBITALS: dict[str, int] = {
    **dict.fromkeys(("H", "He"), 1),
    **dict.fromkeys(("Li", "Be", "B", "C", "N", "O", "F", "Ne"), 4),
    **dict.fromkeys(
        ("Na", "Mg", "Al", "Si", "P", "S", "Cl", "Ar"),
        4,
    ),
}

_MINIMAL_BASIS_ORBITALS: dict[str, int] = {
    **dict.fromkeys(("H", "He"), 1),
    **dict.fromkeys(("Li", "Be", "B", "C", "N", "O", "F", "Ne"), 5),
    **dict.fromkeys(
        ("Na", "Mg", "Al", "Si", "P", "S", "Cl", "Ar"),
        9,
    ),
}


def _canonical_symbol(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    symbol = value.strip()
    if not symbol:
        return None
    return symbol[0].upper() + symbol[1:].lower()


def minimum_basis_active_orbital_limit(
    atoms: Sequence[Mapping[str, Any]],
    *,
    active_electrons: int,
    charge: int = 0,
) -> int | None:
    """Return active-orbital capacity after frozen-core orbitals are counted."""
    total_valence_electrons = 0
    total_valence_orbitals = 0
    minimal_basis_orbitals = 0

    for atom in atoms:
        symbol = _canonical_symbol(atom.get("symbol"))
        if symbol is None:
            return None
        valence_electrons = _VALENCE_ELECTRONS.get(symbol)
        valence_orbitals = _VALENCE_ORBITALS.get(symbol)
        minimal_orbitals = _MINIMAL_BASIS_ORBITALS.get(symbol)
        if valence_electrons is None or valence_orbitals is None or minimal_orbitals is None:
            return None
        total_valence_electrons += valence_electrons
        total_valence_orbitals += valence_orbitals
        minimal_basis_orbitals += minimal_orbitals

    total_electrons = total_valence_electrons + 2 * (
        minimal_basis_orbitals - total_valence_orbitals
    ) - charge
    inactive_electrons = total_electrons - active_electrons
    if inactive_electrons < 0 or inactive_electrons % 2 != 0:
        return None

    return minimal_basis_orbitals - inactive_electrons // 2
