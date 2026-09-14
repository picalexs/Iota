"""
Unit tests for Molecule model PubChem metadata columns.
"""

from __future__ import annotations

from typing import cast

import pytest
from app.models.molecule import Molecule
from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def _inspect_session(session: Session):
    bind = cast("Engine", session.get_bind())
    return inspect(bind)


def test_molecule_has_pubchem_cid_column(test_db: Session) -> None:
    """Molecule should have a nullable pubchem_cid column."""
    inspector = _inspect_session(test_db)
    molecule_columns = {col["name"] for col in inspector.get_columns("molecules")}

    assert "pubchem_cid" in molecule_columns
    col = next(col for col in inspector.get_columns("molecules") if col["name"] == "pubchem_cid")
    assert col["nullable"] is True


def test_molecule_has_iupac_name_column(test_db: Session) -> None:
    """Molecule should have a nullable iupac_name column (String 512)."""
    inspector = _inspect_session(test_db)
    col = next(
        (col for col in inspector.get_columns("molecules") if col["name"] == "iupac_name"),
        None,
    )

    assert col is not None
    assert col["nullable"] is True


def test_molecule_has_description_column(test_db: Session) -> None:
    """Molecule should have a nullable description column."""
    inspector = _inspect_session(test_db)
    col = next(
        (col for col in inspector.get_columns("molecules") if col["name"] == "description"),
        None,
    )

    assert col is not None
    assert col["nullable"] is True


def test_molecule_has_synonyms_column(test_db: Session) -> None:
    """Molecule should have a nullable synonyms column (JSONB)."""
    inspector = _inspect_session(test_db)
    col = next(
        (col for col in inspector.get_columns("molecules") if col["name"] == "synonyms"),
        None,
    )

    assert col is not None
    assert col["nullable"] is True


def test_molecule_has_smiles_column(test_db: Session) -> None:
    """Molecule should have a nullable smiles column (String 512)."""
    inspector = _inspect_session(test_db)
    col = next(
        (col for col in inspector.get_columns("molecules") if col["name"] == "smiles"),
        None,
    )

    assert col is not None
    assert col["nullable"] is True


def test_molecule_has_inchi_column(test_db: Session) -> None:
    """Molecule should have a nullable inchi column."""
    inspector = _inspect_session(test_db)
    col = next(
        (col for col in inspector.get_columns("molecules") if col["name"] == "inchi"),
        None,
    )

    assert col is not None
    assert col["nullable"] is True


def test_molecule_has_inchi_key_column(test_db: Session) -> None:
    """Molecule should have a nullable inchi_key column."""
    inspector = _inspect_session(test_db)
    col = next(
        (col for col in inspector.get_columns("molecules") if col["name"] == "inchi_key"),
        None,
    )

    assert col is not None
    assert col["nullable"] is True


def test_molecule_pubchem_cid_unique_constraint(test_db: Session) -> None:
    """pubchem_cid should have a unique constraint (allowing multiple NULLs)."""
    inspector = _inspect_session(test_db)
    unique_constraints = inspector.get_unique_constraints("molecules")

    # Find constraint on pubchem_cid
    pubchem_cid_uq = next(
        (uc for uc in unique_constraints if uc["column_names"] == ["pubchem_cid"]),
        None,
    )

    assert pubchem_cid_uq is not None


def test_molecule_with_all_pubchem_fields(test_db: Session) -> None:
    """Can create a molecule with all PubChem metadata fields populated."""
    molecule = Molecule(
        name="ethane_pubchem",
        atoms=[
            {"symbol": "C", "x": 0.0, "y": 0.0, "z": 0.0},
            {"symbol": "C", "x": 1.54, "y": 0.0, "z": 0.0},
            {"symbol": "H", "x": -0.51, "y": 0.88, "z": 0.0},
            {"symbol": "H", "x": -0.51, "y": -0.44, "z": 0.76},
            {"symbol": "H", "x": -0.51, "y": -0.44, "z": -0.76},
            {"symbol": "H", "x": 2.05, "y": 0.88, "z": 0.0},
            {"symbol": "H", "x": 2.05, "y": -0.44, "z": 0.76},
            {"symbol": "H", "x": 2.05, "y": -0.44, "z": -0.76},
        ],
        charge=0,
        multiplicity=1,
        pubchem_cid=30,
        iupac_name="ethane",
        description="A simple two-carbon alkane hydrocarbon",
        synonyms=["ethane", "CH3CH3", "C2H6"],
        smiles="CC",
        inchi="InChI=1S/C2H6/c1-2/h1-2H3",
        inchi_key="OTMSDBZUPAUEDD-UHFFFAOYSA-N",
    )
    test_db.add(molecule)
    test_db.commit()
    test_db.refresh(molecule)

    assert molecule.pubchem_cid == 30
    assert molecule.iupac_name == "ethane"
    assert molecule.description == "A simple two-carbon alkane hydrocarbon"
    assert molecule.synonyms == ["ethane", "CH3CH3", "C2H6"]
    assert molecule.smiles == "CC"
    assert molecule.inchi == "InChI=1S/C2H6/c1-2/h1-2H3"
    assert molecule.inchi_key == "OTMSDBZUPAUEDD-UHFFFAOYSA-N"


def test_molecule_with_no_pubchem_fields(test_db: Session) -> None:
    """Can create a molecule without PubChem fields (backward compatibility)."""
    molecule = Molecule(
        name="H2_no_pubchem",
        atoms=[
            {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.0},
            {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.735},
        ],
        charge=0,
        multiplicity=1,
    )
    test_db.add(molecule)
    test_db.commit()
    test_db.refresh(molecule)

    assert molecule.pubchem_cid is None
    assert molecule.iupac_name is None
    assert molecule.description is None
    assert molecule.synonyms is None
    assert molecule.smiles is None
    assert molecule.inchi is None
    assert molecule.inchi_key is None


def test_molecule_pubchem_cid_unique_constraint_enforced(test_db: Session) -> None:
    """Creating two molecules with the same pubchem_cid should fail."""
    mol1 = Molecule(
        name="ethane_1",
        atoms=[{"symbol": "C", "x": 0.0, "y": 0.0, "z": 0.0}],
        pubchem_cid=30,
    )
    mol2 = Molecule(
        name="ethane_2",
        atoms=[{"symbol": "C", "x": 1.0, "y": 0.0, "z": 0.0}],
        pubchem_cid=30,
    )

    test_db.add(mol1)
    test_db.commit()

    test_db.add(mol2)
    with pytest.raises(IntegrityError):
        test_db.commit()

    test_db.rollback()


def test_molecule_can_have_multiple_null_pubchem_cids(test_db: Session) -> None:
    """Multiple molecules can have NULL pubchem_cid (NULL is not considered duplicate)."""
    mol1 = Molecule(
        name="mol_null_1",
        atoms=[{"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.0}],
        pubchem_cid=None,
    )
    mol2 = Molecule(
        name="mol_null_2",
        atoms=[{"symbol": "C", "x": 0.0, "y": 0.0, "z": 0.0}],
        pubchem_cid=None,
    )

    test_db.add_all([mol1, mol2])
    test_db.commit()

    assert mol1.pubchem_cid is None
    assert mol2.pubchem_cid is None


def test_molecule_to_chemistry_input_maps_core_fields() -> None:
    """Molecule.to_chemistry_input should emit the PySCF-ready base config."""
    molecule = Molecule(
        name="h2",
        atoms=[
            {"symbol": "H", "x": 0, "y": 0, "z": 0},
            {"symbol": "H", "x": 0, "y": 0, "z": 0.7414},
        ],
        charge=1,
        multiplicity=1,
    )

    chemistry_input = molecule.to_chemistry_input("sto-3g")

    assert chemistry_input == {
        "atoms": [
            {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.0},
            {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.7414},
        ],
        "basis": "sto-3g",
        "charge": 1,
        "multiplicity": 1,
    }


def test_molecule_to_chemistry_input_preserves_active_space_payload() -> None:
    """Active-space metadata should be copied through unchanged for the worker."""
    active_space = {"n_electrons": 2, "n_orbitals": 2, "method": "avas"}
    molecule = Molecule(
        name="h2_active",
        atoms=[
            {"symbol": "H", "x": 0, "y": 0, "z": 0},
            {"symbol": "H", "x": 0, "y": 0, "z": 0.7414},
        ],
        active_space=active_space,
    )

    chemistry_input = molecule.to_chemistry_input("6-31g*")

    assert chemistry_input["active_space"] == active_space
    assert chemistry_input["active_space"] is not active_space
    assert chemistry_input["basis"] == "6-31g*"
