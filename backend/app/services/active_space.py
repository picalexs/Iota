"""Helpers for deriving and reading active-space metadata."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.core.active_space_capacity import minimum_basis_active_orbital_limit
from app.models.molecule import Molecule

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
    "K": 1,
    "Ca": 2,
    "Sc": 3,
    "Ti": 4,
    "V": 5,
    "Cr": 6,
    "Mn": 7,
    "Fe": 8,
    "Co": 9,
    "Ni": 10,
    "Cu": 11,
    "Zn": 12,
    "Ga": 3,
    "Ge": 4,
    "As": 5,
    "Se": 6,
    "Br": 7,
    "Kr": 8,
    "Rb": 1,
    "Sr": 2,
    "Y": 3,
    "Zr": 4,
    "Nb": 5,
    "Mo": 6,
    "Tc": 7,
    "Ru": 8,
    "Rh": 9,
    "Pd": 10,
    "Ag": 11,
    "Cd": 12,
    "In": 3,
    "Sn": 4,
    "Sb": 5,
    "Te": 6,
    "I": 7,
    "Xe": 8,
}

_VALENCE_ORBITALS: dict[str, int] = {
    "H": 1,
    "He": 1,
    "Li": 4,
    "Be": 4,
    "B": 4,
    "C": 4,
    "N": 4,
    "O": 4,
    "F": 4,
    "Ne": 4,
    "Na": 4,
    "Mg": 4,
    "Al": 4,
    "Si": 4,
    "P": 4,
    "S": 4,
    "Cl": 4,
    "Ar": 4,
    "K": 4,
    "Ca": 4,
    "Sc": 9,
    "Ti": 9,
    "V": 9,
    "Cr": 9,
    "Mn": 9,
    "Fe": 9,
    "Co": 9,
    "Ni": 9,
    "Cu": 9,
    "Zn": 9,
    "Ga": 4,
    "Ge": 4,
    "As": 4,
    "Se": 4,
    "Br": 4,
    "Kr": 4,
    "Rb": 4,
    "Sr": 4,
    "Y": 9,
    "Zr": 9,
    "Nb": 9,
    "Mo": 9,
    "Tc": 9,
    "Ru": 9,
    "Rh": 9,
    "Pd": 9,
    "Ag": 9,
    "Cd": 9,
    "In": 4,
    "Sn": 4,
    "Sb": 4,
    "Te": 4,
    "I": 4,
    "Xe": 4,
}

_MAX_RECOMMENDED_ACTIVE_ORBITALS = 8


def _canonical_symbol(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    symbol = value.strip()
    if not symbol:
        return None
    return symbol[0].upper() + symbol[1:].lower()


def _positive_int_or_none(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value < 0:
        return None
    return value


def extract_active_space(molecule: Molecule | None) -> tuple[int | None, int | None]:
    """Return ``(n_electrons, n_orbitals)`` from a molecule active-space payload."""
    if molecule is None:
        return None, None

    active_space = getattr(molecule, "active_space", None)
    if not isinstance(active_space, dict):
        return None, None

    return (
        _positive_int_or_none(active_space.get("n_electrons")),
        _positive_int_or_none(active_space.get("n_orbitals")),
    )


def should_refresh_derived_active_space(active_space: object) -> bool:
    """Return whether derived active-space metadata should be recomputed."""
    if active_space is None:
        return True
    if not isinstance(active_space, dict):
        return True
    if active_space.get("source") is None and active_space.get("method") is None:
        return True

    total_orbitals = _positive_int_or_none(active_space.get("total_valence_orbitals"))
    n_orbitals = _positive_int_or_none(active_space.get("n_orbitals"))
    if (
        active_space.get("method") == "automatic_valence"
        and active_space.get("recommended_max_active_orbitals") is None
        and total_orbitals is not None
        and n_orbitals == total_orbitals
        and total_orbitals > _MAX_RECOMMENDED_ACTIVE_ORBITALS
    ):
        return True

    return False


def _valence_totals_from_atoms(
    atoms: Sequence[Mapping[str, Any]],
) -> tuple[int, int, list[str]] | None:
    total_valence_electrons = 0
    total_valence_orbitals = 0
    atom_symbols: list[str] = []

    for atom in atoms:
        symbol = _canonical_symbol(atom.get("symbol"))
        if symbol is None:
            return None
        valence_electrons = _VALENCE_ELECTRONS.get(symbol)
        valence_orbitals = _VALENCE_ORBITALS.get(symbol)
        if valence_electrons is None or valence_orbitals is None:
            return None
        atom_symbols.append(symbol)
        total_valence_electrons += valence_electrons
        total_valence_orbitals += valence_orbitals

    return total_valence_electrons, total_valence_orbitals, atom_symbols


def _normalize_active_electrons(
    active_electrons: int,
    active_orbitals: int,
    *,
    multiplicity: int,
) -> int | None:
    if active_electrons <= 0 or active_orbitals <= 0:
        return None

    active_electrons = min(active_electrons, 2 * active_orbitals)
    if multiplicity == 1 and active_electrons % 2 != 0:
        active_electrons -= 1

    if active_electrons <= 0:
        return None
    return active_electrons


def derive_active_space_from_atoms(
    atoms: Sequence[Mapping[str, Any]],
    *,
    charge: int = 0,
    multiplicity: int = 1,
) -> dict[str, Any] | None:
    """Derive a conservative frontier active space from atom symbols.

    This is intentionally molecule-agnostic: it uses periodic-table valence
    counts instead of per-compound lookup tables.  Small molecules keep their
    full valence space; larger imports get a bounded HOMO/LUMO-style frontier
    estimate so VQE/SQD do not accidentally request enormous Hamiltonians.
    """
    valence_totals = _valence_totals_from_atoms(atoms)
    if valence_totals is None:
        return None

    total_valence_electrons, total_valence_orbitals, atom_symbols = valence_totals
    active_electrons = _normalize_active_electrons(
        total_valence_electrons - charge,
        total_valence_orbitals,
        multiplicity=multiplicity,
    )
    if active_electrons is None:
        return None

    if total_valence_orbitals > _MAX_RECOMMENDED_ACTIVE_ORBITALS:
        active_orbitals = _MAX_RECOMMENDED_ACTIVE_ORBITALS
        occupied_frontier_orbitals = max(1, active_orbitals // 2)
        active_electrons = min(active_electrons, 2 * occupied_frontier_orbitals)
        method = "automatic_frontier_estimate"
    else:
        active_orbitals = total_valence_orbitals
        method = "automatic_valence"

    capacity = minimum_basis_active_orbital_limit(
        atoms,
        active_electrons=active_electrons,
        charge=charge,
    )
    if capacity is not None:
        active_orbitals = min(active_orbitals, capacity)
        if active_orbitals <= 0:
            return None

    active_electrons = _normalize_active_electrons(
        active_electrons,
        active_orbitals,
        multiplicity=multiplicity,
    )
    if active_electrons is None:
        return None

    return {
        "n_electrons": int(active_electrons),
        "n_orbitals": int(active_orbitals),
        "method": method,
        "source": "periodic_table_valence",
        "atom_symbols": atom_symbols,
        "total_valence_electrons": int(total_valence_electrons),
        "total_valence_orbitals": int(total_valence_orbitals),
        "recommended_max_active_orbitals": _MAX_RECOMMENDED_ACTIVE_ORBITALS,
    }
