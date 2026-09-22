"""Tests for active-space extraction helpers."""

from __future__ import annotations

from typing import Any, cast

from app.models.molecule import Molecule
from app.schemas.molecule import AtomSchema
from app.services.active_space import (
    derive_active_space_from_atoms,
    extract_active_space,
    minimum_basis_active_orbital_limit,
    should_refresh_derived_active_space,
)


def _molecule_with_active_space(active_space: dict[str, Any] | None) -> Molecule:
    return Molecule(
        name="test",
        atoms=[],
        charge=0,
        multiplicity=1,
        active_space=active_space,
    )


def test_extract_active_space_returns_electrons_and_orbitals() -> None:
    molecule = _molecule_with_active_space({"n_electrons": 2, "n_orbitals": 4})

    assert extract_active_space(molecule) == (2, 4)


def test_extract_active_space_ignores_missing_or_invalid_values() -> None:
    molecule = _molecule_with_active_space({"n_electrons": True, "n_orbitals": "4"})

    assert extract_active_space(molecule) == (None, None)


def test_extract_active_space_handles_missing_molecule_or_payload() -> None:
    assert extract_active_space(None) == (None, None)
    assert extract_active_space(_molecule_with_active_space(None)) == (None, None)
    malformed_molecule = _molecule_with_active_space(None)
    malformed_molecule.active_space = cast(dict[str, Any], [])
    assert extract_active_space(malformed_molecule) == (None, None)


def test_derive_active_space_uses_valence_counts_without_molecule_lookup() -> None:
    active_space = derive_active_space_from_atoms(
        [
            {"symbol": "O", "x": 0.0, "y": 0.0, "z": 0.0},
            {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.9},
            {"symbol": "H", "x": 0.0, "y": 0.8, "z": -0.3},
        ]
    )

    assert active_space is not None
    assert active_space["n_electrons"] == 8
    assert active_space["n_orbitals"] == 6
    assert active_space["method"] == "automatic_valence"


def test_derive_active_space_uses_bounded_frontier_estimate_for_larger_imports() -> None:
    active_space = derive_active_space_from_atoms(
        [{"symbol": "C", "x": float(index), "y": 0.0, "z": 0.0} for index in range(6)]
        + [{"symbol": "H", "x": float(index), "y": 1.0, "z": 0.0} for index in range(6)]
    )

    assert active_space is not None
    assert active_space["n_electrons"] == 8
    assert active_space["n_orbitals"] == 8
    assert active_space["method"] == "automatic_frontier_estimate"
    assert active_space["total_valence_orbitals"] > active_space["n_orbitals"]


def test_derive_active_space_accounts_for_frozen_core_capacity() -> None:
    active_space = derive_active_space_from_atoms(
        [
            {"symbol": "F", "x": -0.7, "y": 0.0, "z": 0.0},
            {"symbol": "O", "x": 0.7, "y": 0.0, "z": 0.0},
            {"symbol": "H", "x": 1.0, "y": 0.6, "z": -0.6},
        ]
    )

    assert active_space is not None
    assert active_space["n_electrons"] == 8
    assert active_space["n_orbitals"] == 6


def test_minimum_basis_active_orbital_limit_preserves_water_capacity() -> None:
    atoms = [
        {"symbol": "O", "x": 0.0, "y": 0.0, "z": 0.0},
        {"symbol": "H", "x": 0.0, "y": 0.8, "z": -0.3},
        {"symbol": "H", "x": 0.0, "y": -0.8, "z": -0.3},
    ]

    assert minimum_basis_active_orbital_limit(atoms, active_electrons=4) == 4


def test_minimum_basis_active_orbital_limit_accepts_atom_models() -> None:
    atoms = [
        AtomSchema(symbol="O", x=0.0, y=0.0, z=0.0),
        AtomSchema(symbol="H", x=0.0, y=0.8, z=-0.3),
        AtomSchema(symbol="H", x=0.0, y=-0.8, z=-0.3),
    ]

    assert minimum_basis_active_orbital_limit(atoms, active_electrons=4) == 4


def test_should_refresh_legacy_unbounded_automatic_active_space() -> None:
    assert should_refresh_derived_active_space(
        {
            "n_electrons": 74,
            "n_orbitals": 66,
            "method": "automatic_valence",
            "source": "periodic_table_valence",
            "total_valence_orbitals": 66,
        }
    )

    assert not should_refresh_derived_active_space(
        {
            "n_electrons": 8,
            "n_orbitals": 8,
            "method": "automatic_frontier_estimate",
            "source": "periodic_table_valence",
            "total_valence_orbitals": 66,
            "recommended_max_active_orbitals": 8,
        }
    )


def test_derive_active_space_returns_none_for_unknown_symbols() -> None:
    assert derive_active_space_from_atoms([{"symbol": "Xx"}]) is None
