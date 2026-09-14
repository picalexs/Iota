"""Unit tests for molecule schema validation guards."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.models.molecule import Molecule
from app.schemas.molecule import (
    MAX_ATOMS_PER_MOLECULE,
    MAX_DESCRIPTION_LENGTH,
    MAX_INCHI_LENGTH,
    MAX_SYNONYM_LENGTH,
    MAX_SYNONYMS,
    MoleculeCreate,
    MoleculeUpdate,
    validate_molecule_response,
)
from pydantic import ValidationError

BASE_CREATE_PAYLOAD = {
    "name": "H2O",
    "atoms": [
        {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.0},
        {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.74},
    ],
}


def test_molecule_create_rejects_default_name_case_insensitive() -> None:
    """Create payloads should reject placeholder names."""
    with pytest.raises(ValidationError):
        MoleculeCreate(**{**BASE_CREATE_PAYLOAD, "name": "default"})

    with pytest.raises(ValidationError):
        MoleculeCreate(**{**BASE_CREATE_PAYLOAD, "name": "DEFAULT"})


def test_molecule_update_rejects_default_name_case_insensitive() -> None:
    """Update payloads should reject placeholder names."""
    with pytest.raises(ValidationError):
        MoleculeUpdate.model_validate({"name": "default"})

    with pytest.raises(ValidationError):
        MoleculeUpdate.model_validate({"name": "DEFAULT"})


def test_molecule_create_accepts_real_name() -> None:
    """Valid non-placeholder names continue to be accepted."""
    molecule = MoleculeCreate(**BASE_CREATE_PAYLOAD)
    assert molecule.name == "H2O"


def test_molecule_create_rejects_unsupported_atom_symbol() -> None:
    """Create payloads should reject atom symbols outside the supported element table."""
    with pytest.raises(ValidationError, match="Atom symbol 'A' is not supported"):
        MoleculeCreate(
            **{
                **BASE_CREATE_PAYLOAD,
                "atoms": [{"symbol": "A", "x": 0.0, "y": 0.0, "z": 0.0}],
            }
        )


def test_validate_molecule_response_allows_legacy_unsupported_atom_symbols() -> None:
    """Response serialization should keep legacy unsupported atoms readable."""
    molecule = Molecule(
        id=uuid4(),
        name="legacy-invalid",
        atoms=[
            {"symbol": "A", "x": 0.0, "y": 0.0, "z": 0.0},
            {"symbol": "Fr", "x": 1.0, "y": 0.0, "z": 0.0},
        ],
        charge=0,
        multiplicity=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    response = validate_molecule_response(molecule)

    assert [atom.symbol for atom in response.atoms] == ["A", "Fr"]
    assert response.eligibility is not None
    assert response.eligibility.selectable is False
    assert response.eligibility.label == "Unsupported atoms"
    assert response.runnable_algorithms == []


def _atom(index: int) -> dict[str, float | str]:
    return {"symbol": "H", "x": float(index), "y": 0.0, "z": 0.0}


def test_molecule_create_accepts_atoms_at_the_cap() -> None:
    """A molecule with exactly the maximum atom count stays valid."""
    molecule = MoleculeCreate(
        **{
            **BASE_CREATE_PAYLOAD,
            "atoms": [_atom(index) for index in range(MAX_ATOMS_PER_MOLECULE)],
        }
    )

    assert len(molecule.atoms) == MAX_ATOMS_PER_MOLECULE


def test_molecule_create_rejects_atoms_above_the_cap() -> None:
    """Unbounded atom lists are a storage and CPU abuse vector."""
    with pytest.raises(ValidationError) as excinfo:
        MoleculeCreate(
            **{
                **BASE_CREATE_PAYLOAD,
                "atoms": [_atom(index) for index in range(MAX_ATOMS_PER_MOLECULE + 1)],
            }
        )

    assert "atoms" in str(excinfo.value)


def test_molecule_update_rejects_atoms_above_the_cap() -> None:
    """PATCH payloads must enforce the same atom ceiling as create."""
    with pytest.raises(ValidationError):
        MoleculeUpdate.model_validate(
            {"atoms": [_atom(index) for index in range(MAX_ATOMS_PER_MOLECULE + 1)]}
        )


def test_molecule_create_rejects_oversized_description() -> None:
    """Free-text description is stored verbatim, so it needs a ceiling."""
    with pytest.raises(ValidationError):
        MoleculeCreate(
            **{**BASE_CREATE_PAYLOAD, "description": "x" * (MAX_DESCRIPTION_LENGTH + 1)}
        )


def test_molecule_create_accepts_description_at_the_cap() -> None:
    """Descriptions at the limit remain valid."""
    molecule = MoleculeCreate(
        **{**BASE_CREATE_PAYLOAD, "description": "x" * MAX_DESCRIPTION_LENGTH}
    )

    assert molecule.description is not None


def test_molecule_create_rejects_oversized_inchi() -> None:
    """InChI strings are bounded in practice and must be bounded in the schema."""
    with pytest.raises(ValidationError):
        MoleculeCreate(**{**BASE_CREATE_PAYLOAD, "inchi": "I" * (MAX_INCHI_LENGTH + 1)})


def test_molecule_create_rejects_too_many_synonyms() -> None:
    """The synonym list is JSONB; an unbounded list bloats storage."""
    with pytest.raises(ValidationError):
        MoleculeCreate(
            **{
                **BASE_CREATE_PAYLOAD,
                "synonyms": [f"name-{index}" for index in range(MAX_SYNONYMS + 1)],
            }
        )


def test_molecule_create_rejects_oversized_single_synonym() -> None:
    """A short list of enormous strings must be rejected too."""
    with pytest.raises(ValidationError):
        MoleculeCreate(
            **{**BASE_CREATE_PAYLOAD, "synonyms": ["s" * (MAX_SYNONYM_LENGTH + 1)]}
        )


def test_molecule_create_accepts_synonyms_within_limits() -> None:
    """Typical PubChem synonym lists (up to ten entries) stay valid."""
    molecule = MoleculeCreate(
        **{**BASE_CREATE_PAYLOAD, "synonyms": [f"name-{index}" for index in range(10)]}
    )

    assert molecule.synonyms is not None
    assert len(molecule.synonyms) == 10
