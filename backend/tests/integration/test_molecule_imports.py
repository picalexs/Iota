"""Integration tests for PubChem and XYZ molecule acquisition."""

from __future__ import annotations

from unittest.mock import AsyncMock

from app.models.molecule import Molecule
from app.schemas.molecule import MAX_ATOMS_PER_MOLECULE
from sqlalchemy.orm import Session

from tests.conftest import ASGISyncTestClient

PUBCHEM_FETCH_PATH = "app.services.pubchem_sync.fetch_molecule_from_pubchem"
XYZ_PREVIEW_PATH = "/api/molecules/xyz/preview"


class TestMoleculePubChemImport:
    """Tests for on-demand PubChem import behavior."""

    def test_preview_pubchem_import_returns_preview_without_insert(
        self,
        client: ASGISyncTestClient,
        test_db: Session,
        monkeypatch,
    ):
        """PubChem preview fetches geometry and metadata without storing a row."""

        fake_fetch = AsyncMock(
            return_value={
                "name": "water",
                "charge": 0,
                "multiplicity": 1,
                "atoms": [
                    {"symbol": "O", "x": 0.0, "y": 0.0, "z": 0.0},
                    {"symbol": "H", "x": 0.757, "y": 0.586, "z": 0.0},
                    {"symbol": "H", "x": -0.757, "y": 0.586, "z": 0.0},
                ],
                "active_space": {"n_electrons": 8, "n_orbitals": 6},
                "pubchem_cid": 962,
                "iupac_name": "oxidane",
                "description": "Water",
                "synonyms": ["water"],
                "smiles": "O",
                "inchi": "InChI=1S/H2O/h1H2",
                "inchi_key": "XLYOFNOQVPJJNP-UHFFFAOYSA-N",
            }
        )

        monkeypatch.setattr(PUBCHEM_FETCH_PATH, fake_fetch)

        response = client.post(
            "/api/molecules/pubchem/preview",
            json={"name": "water", "display_name": "Water"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "pubchem"
        assert data["name"] == "Water"
        assert data["formula"] == "H2O"
        assert data["atom_count"] == 3
        assert data["commit_action"] == "create"
        assert data["eligibility"]["label"] == "Ready"

        assert test_db.query(Molecule).count() == 0

    def test_import_existing_pubchem_cid_returns_existing_molecule(
        self,
        client: ASGISyncTestClient,
        test_db: Session,
        monkeypatch,
    ):
        """Import should be idempotent and return existing molecule when CID already exists."""
        existing = Molecule(
            name="H2O",
            atoms=[
                {"symbol": "O", "x": 0.0, "y": 0.0, "z": 0.0},
                {"symbol": "H", "x": 0.757, "y": 0.586, "z": 0.0},
                {"symbol": "H", "x": -0.757, "y": 0.586, "z": 0.0},
            ],
            charge=0,
            multiplicity=1,
            pubchem_cid=962,
            iupac_name="oxidane",
            synonyms=["water"],
        )
        test_db.add(existing)
        test_db.commit()
        test_db.refresh(existing)

        fake_fetch = AsyncMock(
            return_value={
                "name": "water",
                "charge": 0,
                "multiplicity": 1,
                "atoms": [
                    {"symbol": "O", "x": 0.0, "y": 0.0, "z": 0.0},
                    {"symbol": "H", "x": 0.757, "y": 0.586, "z": 0.0},
                    {"symbol": "H", "x": -0.757, "y": 0.586, "z": 0.0},
                ],
                "active_space": None,
                "pubchem_cid": 962,
                "iupac_name": "oxidane",
                "description": None,
                "synonyms": ["water"],
                "smiles": "O",
                "inchi": None,
                "inchi_key": None,
            }
        )

        monkeypatch.setattr(PUBCHEM_FETCH_PATH, fake_fetch)

        response = client.post(
            "/api/molecules/pubchem/import",
            json={"name": "water", "display_name": "Water"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(existing.id)
        assert data["name"] == "H2O"

        # Ensure no duplicate molecule row was inserted.
        assert test_db.query(Molecule).count() == 1

    def test_import_pubchem_rejects_unsupported_atoms(
        self, client: ASGISyncTestClient, monkeypatch
    ):
        """PubChem import should fail before persisting unsupported element symbols."""
        fake_fetch = AsyncMock(
            return_value={
                "name": "legacy-invalid",
                "charge": 0,
                "multiplicity": 1,
                "atoms": [
                    {"symbol": "A", "x": 0.0, "y": 0.0, "z": 0.0},
                    {"symbol": "Fr", "x": 1.0, "y": 0.0, "z": 0.0},
                ],
                "active_space": None,
                "pubchem_cid": 123456,
                "iupac_name": None,
                "description": None,
                "synonyms": None,
                "smiles": None,
                "inchi": None,
                "inchi_key": None,
            }
        )

        monkeypatch.setattr(PUBCHEM_FETCH_PATH, fake_fetch)

        response = client.post(
            "/api/molecules/pubchem/import",
            json={"name": "legacy-invalid", "display_name": "Legacy Invalid"},
        )

        assert response.status_code == 422
        assert "Molecule atom data is invalid" in response.text

    def test_preview_existing_pubchem_cid_marks_reuse(
        self,
        client: ASGISyncTestClient,
        test_db: Session,
        monkeypatch,
    ):
        """PubChem preview reports when commit will reuse an existing CID."""
        existing = Molecule(
            name="H2O",
            atoms=[
                {"symbol": "O", "x": 0.0, "y": 0.0, "z": 0.0},
                {"symbol": "H", "x": 0.757, "y": 0.586, "z": 0.0},
                {"symbol": "H", "x": -0.757, "y": 0.586, "z": 0.0},
            ],
            charge=0,
            multiplicity=1,
            pubchem_cid=962,
        )
        test_db.add(existing)
        test_db.commit()
        test_db.refresh(existing)

        fake_fetch = AsyncMock(
            return_value={
                "name": "water",
                "charge": 0,
                "multiplicity": 1,
                "atoms": existing.atoms,
                "active_space": {"n_electrons": 8, "n_orbitals": 6},
                "pubchem_cid": 962,
                "iupac_name": "oxidane",
                "description": None,
                "synonyms": ["water"],
                "smiles": "O",
                "inchi": None,
                "inchi_key": None,
            }
        )

        monkeypatch.setattr(PUBCHEM_FETCH_PATH, fake_fetch)

        response = client.post(
            "/api/molecules/pubchem/preview",
            json={"name": "water", "display_name": "Water"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["commit_action"] == "reuse"
        assert data["existing_molecule_id"] == str(existing.id)
        assert data["existing_molecule_name"] == "H2O"


class TestMoleculeXYZImport:
    """Tests for standard XYZ preview and import behavior."""

    def test_preview_xyz_returns_geometry_formula_and_active_space(
        self, client: ASGISyncTestClient, test_db: Session
    ):
        """XYZ preview parses coordinates and derives active-space metadata."""
        payload = {
            "name": "Water XYZ",
            "xyz": "3\nwater comment\nO 0 0 0\nH 0.757 0.586 0\nH -0.757 0.586 0\n",
        }

        response = client.post(XYZ_PREVIEW_PATH, json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "xyz"
        assert data["name"] == "Water XYZ"
        assert data["formula"] == "H2O"
        assert data["atom_count"] == 3
        assert data["commit_action"] == "create"
        assert data["active_space"]["n_electrons"] == 8
        assert data["active_space"]["n_orbitals"] == 6
        assert data["eligibility"]["label"] == "Ready"

        assert test_db.query(Molecule).count() == 0

    def test_import_xyz_persists_molecule(self, client: ASGISyncTestClient, test_db: Session):
        """XYZ import stores parsed coordinates as a molecule."""
        payload = {
            "name": "Imported Water",
            "xyz": "3\nwater\nO 0 0 0\nH 0.757 0.586 0\nH -0.757 0.586 0\n",
        }

        response = client.post("/api/molecules/xyz/import", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Imported Water"
        assert data["atoms"][0]["symbol"] == "O"
        assert data["active_space"]["n_electrons"] == 8
        assert data["eligibility"]["label"] == "Ready"

        assert test_db.query(Molecule).count() == 1

    def test_preview_xyz_duplicate_name_marks_name_conflict(
        self, client: ASGISyncTestClient, sample_molecule: Molecule
    ):
        """XYZ preview reports name collisions before commit."""
        payload = {
            "name": sample_molecule.name,
            "xyz": "2\nhydrogen\nH 0 0 0\nH 0 0 0.735\n",
        }

        response = client.post(XYZ_PREVIEW_PATH, json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["commit_action"] == "name_conflict"
        assert data["existing_molecule_id"] == str(sample_molecule.id)

    def test_preview_xyz_rejects_bad_atom_count(self, client: ASGISyncTestClient):
        """XYZ preview returns fielded validation errors for malformed text."""
        response = client.post(
            XYZ_PREVIEW_PATH,
            json={"name": "Bad XYZ", "xyz": "3\nbad\nH 0 0 0\nH 0 0 1\n"},
        )

        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "VALIDATION_ERROR"
        assert response.json()["detail"]["field"] == "xyz"

    def test_preview_xyz_rejects_atom_count_above_ceiling(self, client: ASGISyncTestClient):
        """A declared atom count beyond the ceiling is rejected before parsing lines."""
        declared = MAX_ATOMS_PER_MOLECULE + 1
        response = client.post(
            XYZ_PREVIEW_PATH,
            json={"name": "Huge XYZ", "xyz": f"{declared}\ncomment\nH 0 0 0\n"},
        )

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail["code"] == "VALIDATION_ERROR"
        assert detail["field"] == "xyz"
        assert str(MAX_ATOMS_PER_MOLECULE) in detail["message"]

    def test_preview_xyz_accepts_small_geometry_unchanged(self, client: ASGISyncTestClient):
        """The ceiling must not disturb ordinary small geometries."""
        response = client.post(
            XYZ_PREVIEW_PATH,
            json={"name": "Tiny XYZ", "xyz": "2\ncomment\nH 0 0 0\nH 0 0 0.74\n"},
        )

        assert response.status_code == 200
        assert response.json()["atom_count"] == 2
