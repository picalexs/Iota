"""Molecule construction helpers."""

from __future__ import annotations

import math
from typing import Any

from worker.chemistry.types import ChemistryInput, PreparedMolecule


def _as_finite_float(value: Any, *, field: str) -> float:
    """Convert numeric input to a finite float with clear validation errors."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite numeric value")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{field} must be a finite numeric value")
    return converted


def _from_atom_records(
    atoms: list[str | dict[str, Any]],
) -> list[tuple[str, tuple[float, float, float]]]:
    """Build PySCF atom tuples from backend-style atom dictionaries."""
    atom_spec: list[tuple[str, tuple[float, float, float]]] = []
    for index, atom in enumerate(atoms):
        if not isinstance(atom, dict):
            raise ValueError(f"atoms[{index}] must be an object with symbol/x/y/z")

        for required_key in ("symbol", "x", "y", "z"):
            if required_key not in atom:
                raise ValueError(f"atoms[{index}] missing required key '{required_key}'")

        symbol = str(atom["symbol"]).strip()
        if not symbol:
            raise ValueError(f"atoms[{index}].symbol must be a non-empty string")

        x = _as_finite_float(atom["x"], field=f"atoms[{index}].x")
        y = _as_finite_float(atom["y"], field=f"atoms[{index}].y")
        z = _as_finite_float(atom["z"], field=f"atoms[{index}].z")
        atom_spec.append((symbol, (x, y, z)))

    return atom_spec


def _from_symbols_and_coordinates(
    atoms: list[str | dict[str, Any]],
    coordinates: list[list[float]] | None,
) -> list[tuple[str, tuple[float, float, float]]]:
    """Build PySCF atom tuples from symbols + coordinate matrix input."""
    if coordinates is None:
        raise ValueError("coordinates are required when atoms are provided as symbols")
    if len(atoms) != len(coordinates):
        raise ValueError("atoms and coordinates must have the same length")

    atom_spec: list[tuple[str, tuple[float, float, float]]] = []
    for index, (symbol_value, xyz) in enumerate(zip(atoms, coordinates, strict=True)):
        if not isinstance(symbol_value, str) or not symbol_value.strip():
            raise ValueError(f"atoms[{index}] must be a non-empty symbol string")
        if not isinstance(xyz, list) or len(xyz) != 3:
            raise ValueError(f"coordinates[{index}] must be a three-element list")

        x = _as_finite_float(xyz[0], field=f"coordinates[{index}][0]")
        y = _as_finite_float(xyz[1], field=f"coordinates[{index}][1]")
        z = _as_finite_float(xyz[2], field=f"coordinates[{index}][2]")
        atom_spec.append((symbol_value.strip(), (x, y, z)))

    return atom_spec


def _validate_active_space(active_space: tuple[int, int] | None) -> tuple[int, int] | None:
    """Validate active-space tuple for closed-shell rollout constraints."""
    if active_space is None:
        return None

    n_electrons, n_orbitals = active_space
    if isinstance(n_electrons, bool) or isinstance(n_orbitals, bool):
        raise ValueError("active_space values must be integers")
    if n_electrons <= 0 or n_orbitals <= 0:
        raise ValueError("active_space values must be positive")
    if n_electrons % 2 != 0:
        raise ValueError("active_space.n_electrons must be even for RHF reference")
    if n_electrons > 2 * n_orbitals:
        raise ValueError("active_space.n_electrons cannot exceed 2 * n_orbitals")
    return int(n_electrons), int(n_orbitals)


def build_molecule(chemistry_input: ChemistryInput) -> PreparedMolecule:
    """Normalize chemistry input into a validated PySCF-ready molecule payload."""
    if not chemistry_input.atoms:
        raise ValueError("atoms must be a non-empty list")

    basis = chemistry_input.basis.strip()
    if not basis:
        raise ValueError("basis must be a non-empty string")

    if isinstance(chemistry_input.charge, bool) or not isinstance(chemistry_input.charge, int):
        raise ValueError("charge must be an integer")
    if isinstance(chemistry_input.multiplicity, bool) or not isinstance(
        chemistry_input.multiplicity, int
    ):
        raise ValueError("multiplicity must be an integer")
    if chemistry_input.multiplicity < 1:
        raise ValueError("multiplicity must be >= 1")

    first_atom = chemistry_input.atoms[0]
    if isinstance(first_atom, dict):
        atom_spec = _from_atom_records(chemistry_input.atoms)
    else:
        atom_spec = _from_symbols_and_coordinates(
            chemistry_input.atoms, chemistry_input.coordinates
        )

    return PreparedMolecule(
        atom_spec=atom_spec,
        basis=basis,
        charge=int(chemistry_input.charge),
        multiplicity=int(chemistry_input.multiplicity),
        active_space=_validate_active_space(chemistry_input.active_space),
    )
