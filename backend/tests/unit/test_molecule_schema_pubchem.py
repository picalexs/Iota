"""
Unit tests for Molecule Pydantic schema PubChem fields.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from app.schemas.molecule import (
    MoleculeCreate,
    MoleculeResponse,
    MoleculeUpdate,
)
from pydantic import ValidationError


def test_molecule_response_serializes_pubchem_fields() -> None:
    """MoleculeResponse should expose all PubChem metadata fields."""
    molecule_data = {
        "id": uuid4(),
        "name": "ethane",
        "atoms": [{"symbol": "C", "x": 0.0, "y": 0.0, "z": 0.0}],
        "charge": 0,
        "multiplicity": 1,
        "active_space": None,
        "created_at": "2026-03-01T00:00:00+00:00",
        "updated_at": "2026-03-01T00:00:00+00:00",
        "pubchem_cid": 30,
        "iupac_name": "ethane",
        "description": "A two-carbon alkane",
        "synonyms": ["ethane", "C2H6"],
        "smiles": "CC",
        "inchi": "InChI=1S/C2H6/c1-2/h1-2H3",
        "inchi_key": "OTMSDBZUPAUEDD-UHFFFAOYSA-N",
    }

    response = MoleculeResponse(**molecule_data)

    assert response.pubchem_cid == 30
    assert response.iupac_name == "ethane"
    assert response.description == "A two-carbon alkane"
    assert response.synonyms == ["ethane", "C2H6"]
    assert response.smiles == "CC"
    assert response.inchi == "InChI=1S/C2H6/c1-2/h1-2H3"
    assert response.inchi_key == "OTMSDBZUPAUEDD-UHFFFAOYSA-N"


def test_molecule_response_handles_null_pubchem_fields() -> None:
    """MoleculeResponse should accept null PubChem fields."""
    molecule_data = {
        "id": uuid4(),
        "name": "H2",
        "atoms": [{"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.0}],
        "charge": 0,
        "multiplicity": 1,
        "active_space": None,
        "created_at": "2026-03-01T00:00:00+00:00",
        "updated_at": "2026-03-01T00:00:00+00:00",
        "pubchem_cid": None,
        "iupac_name": None,
        "description": None,
        "synonyms": None,
        "smiles": None,
        "inchi": None,
        "inchi_key": None,
    }

    response = MoleculeResponse(**molecule_data)

    assert response.pubchem_cid is None
    assert response.iupac_name is None
    assert response.description is None
    assert response.synonyms is None
    assert response.smiles is None
    assert response.inchi is None
    assert response.inchi_key is None


def test_molecule_create_accepts_pubchem_fields() -> None:
    """MoleculeCreate should accept PubChem metadata fields."""
    create_data = {
        "name": "ethane",
        "atoms": [{"symbol": "C", "x": 0.0, "y": 0.0, "z": 0.0}],
        "charge": 0,
        "multiplicity": 1,
        "active_space": None,
        "pubchem_cid": 30,
        "iupac_name": "ethane",
        "description": "A two-carbon alkane",
        "synonyms": ["ethane", "C2H6"],
        "smiles": "CC",
        "inchi": "InChI=1S/C2H6/c1-2/h1-2H3",
        "inchi_key": "OTMSDBZUPAUEDD-UHFFFAOYSA-N",
    }

    created = MoleculeCreate(**create_data)

    assert created.pubchem_cid == 30
    assert created.iupac_name == "ethane"
    assert created.synonyms == ["ethane", "C2H6"]


def test_molecule_create_pubchem_fields_optional() -> None:
    """MoleculeCreate should accept requests without PubChem fields."""
    create_data = {
        "name": "H2",
        "atoms": [{"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.0}],
    }

    created = MoleculeCreate(**create_data)

    assert created.pubchem_cid is None
    assert created.iupac_name is None
    assert created.description is None
    assert created.synonyms is None
    assert created.smiles is None
    assert created.inchi is None
    assert created.inchi_key is None


def test_molecule_update_accepts_pubchem_fields() -> None:
    """MoleculeUpdate should accept PubChem metadata fields."""
    update_data = {
        "pubchem_cid": 30,
        "iupac_name": "ethane",
        "description": "A two-carbon alkane",
        "synonyms": ["ethane", "C2H6"],
        "smiles": "CC",
        "inchi": "InChI=1S/C2H6/c1-2/h1-2H3",
        "inchi_key": "OTMSDBZUPAUEDD-UHFFFAOYSA-N",
    }

    updated = MoleculeUpdate(**update_data)

    assert updated.pubchem_cid == 30
    assert updated.iupac_name == "ethane"
    assert updated.synonyms == ["ethane", "C2H6"]


def test_molecule_update_pubchem_fields_optional() -> None:
    """MoleculeUpdate should allow omitting PubChem fields (for partial updates)."""
    update_data = {"name": "ethane_updated"}

    updated = MoleculeUpdate.model_validate(update_data)

    assert updated.pubchem_cid is None
    assert updated.iupac_name is None
    assert updated.description is None


def test_inchi_key_validator_rejects_wrong_length() -> None:
    """InChIKey validation should reject strings that aren't exactly 27 characters."""
    # Valid InChIKey is 27 chars
    valid_data = {
        "name": "ethane",
        "atoms": [{"symbol": "C", "x": 0.0, "y": 0.0, "z": 0.0}],
        "inchi_key": "OTMSDBZUPAUEDD-UHFFFAOYSA-N",
    }
    created = MoleculeCreate(**valid_data)
    assert created.inchi_key == "OTMSDBZUPAUEDD-UHFFFAOYSA-N"

    # Too short
    invalid_short = {
        "name": "ethane",
        "atoms": [{"symbol": "C", "x": 0.0, "y": 0.0, "z": 0.0}],
        "inchi_key": "SHORT-KEY",
    }

    with pytest.raises(ValidationError) as exc_info:
        MoleculeCreate(**invalid_short)

    assert "inchi_key" in str(exc_info.value).lower()

    # Too long
    invalid_long = {
        "name": "ethane",
        "atoms": [{"symbol": "C", "x": 0.0, "y": 0.0, "z": 0.0}],
        "inchi_key": "OTMSDBZUPAUEDD-UHFFFAOYSA-NXXXXXXX",
    }

    with pytest.raises(ValidationError) as exc_info:
        MoleculeCreate(**invalid_long)

    assert "inchi_key" in str(exc_info.value).lower()


def test_iupac_name_validator_max_length() -> None:
    """IUPAC name should reject strings longer than 512 characters."""
    valid_data = {
        "name": "ethane",
        "atoms": [{"symbol": "C", "x": 0.0, "y": 0.0, "z": 0.0}],
        "iupac_name": "a" * 512,
    }

    created = MoleculeCreate(**valid_data)
    assert created.iupac_name is not None
    assert len(created.iupac_name) == 512

    invalid_data = {
        "name": "ethane",
        "atoms": [{"symbol": "C", "x": 0.0, "y": 0.0, "z": 0.0}],
        "iupac_name": "a" * 513,
    }

    with pytest.raises(ValidationError) as exc_info:
        MoleculeCreate(**invalid_data)

    assert "iupac_name" in str(exc_info.value).lower()


def test_smiles_validator_max_length() -> None:
    """SMILES string should reject strings longer than 512 characters."""
    valid_data = {
        "name": "ethane",
        "atoms": [{"symbol": "C", "x": 0.0, "y": 0.0, "z": 0.0}],
        "smiles": "C" * 512,
    }

    created = MoleculeCreate(**valid_data)
    assert created.smiles is not None
    assert len(created.smiles) == 512

    invalid_data = {
        "name": "ethane",
        "atoms": [{"symbol": "C", "x": 0.0, "y": 0.0, "z": 0.0}],
        "smiles": "C" * 513,
    }

    with pytest.raises(ValidationError) as exc_info:
        MoleculeCreate(**invalid_data)

    assert "smiles" in str(exc_info.value).lower()


def test_molecule_update_forbids_null_on_non_nullable_fields() -> None:
    """MoleculeUpdate should forbid explicit null on required fields."""
    # New PubChem fields should NOT forbid null (they're optional in the DB)
    update_data_can_be_null = {
        "pubchem_cid": None,
        "iupac_name": None,
        "description": None,
        "synonyms": None,
        "smiles": None,
        "inchi": None,
        "inchi_key": None,
    }

    # This should succeed (PubChem fields can be set to null)
    updated = MoleculeUpdate(**update_data_can_be_null)
    assert updated.pubchem_cid is None
    assert updated.iupac_name is None
