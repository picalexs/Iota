"""
Integration tests for molecule endpoints.

Tests all molecule CRUD operations and validation.
"""

from __future__ import annotations

from uuid import uuid4

from app.api.v1.endpoints import molecules as molecules_endpoint
from app.models.molecule import Molecule
from app.schemas.molecule import MoleculeListParams
from sqlalchemy.orm import Session

from tests.conftest import ASGISyncTestClient

MOLECULES_API_PATH = "/api/molecules"


class TestMoleculeCreate:
    """Tests for POST /api/molecules endpoint."""

    def test_create_molecule_success_minimal(self, client: ASGISyncTestClient):
        """Test successful molecule creation with defaults."""
        payload = {
            "name": "H2",
            "atoms": [
                {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.0},
                {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.735},
            ],
        }

        response = client.post(MOLECULES_API_PATH, json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "H2"
        assert len(data["atoms"]) == 2
        assert data["charge"] == 0
        assert data["multiplicity"] == 1
        assert data["active_space"] is None
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_molecule_with_active_space(self, client: ASGISyncTestClient):
        """Test molecule creation with active_space (extensible fields)."""
        payload = {
            "name": "LiH",
            "atoms": [
                {"symbol": "Li", "x": 0.0, "y": 0.0, "z": 0.0},
                {"symbol": "H", "x": 0.0, "y": 0.0, "z": 1.6},
            ],
            "active_space": {
                "n_electrons": 2,
                "n_orbitals": 2,
                "method": "avas",
            },
        }

        response = client.post(MOLECULES_API_PATH, json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["active_space"]["n_electrons"] == 2
        assert data["active_space"]["n_orbitals"] == 2
        assert data["active_space"]["method"] == "avas"

    def test_create_molecule_duplicate_name_conflict(
        self, client: ASGISyncTestClient, sample_molecule: Molecule
    ):
        """Test that creating molecule with duplicate name fails."""
        payload = {
            "name": sample_molecule.name,
            "atoms": [{"symbol": "He", "x": 0.0, "y": 0.0, "z": 0.0}],
        }

        response = client.post(MOLECULES_API_PATH, json=payload)

        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "CONFLICT"

    def test_create_molecule_duplicate_name_case_insensitive_conflict(
        self, client: ASGISyncTestClient, sample_molecule: Molecule
    ):
        """Test that creating molecule with name differing only by case fails."""
        payload = {
            "name": sample_molecule.name.swapcase(),
            "atoms": [{"symbol": "He", "x": 0.0, "y": 0.0, "z": 0.0}],
        }

        response = client.post(MOLECULES_API_PATH, json=payload)

        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "CONFLICT"

    def test_create_molecule_missing_name(self, client: ASGISyncTestClient):
        """Test molecule creation fails without name."""
        payload = {
            "atoms": [{"symbol": "He", "x": 0.0, "y": 0.0, "z": 0.0}],
        }

        response = client.post(MOLECULES_API_PATH, json=payload)
        assert response.status_code == 422

    def test_create_molecule_empty_name(self, client: ASGISyncTestClient):
        """Test molecule creation fails with blank name."""
        payload = {
            "name": "   ",
            "atoms": [{"symbol": "He", "x": 0.0, "y": 0.0, "z": 0.0}],
        }

        response = client.post(MOLECULES_API_PATH, json=payload)
        assert response.status_code == 422

    def test_create_molecule_invalid_atom_symbol(self, client: ASGISyncTestClient):
        """Test molecule creation fails fast for unsupported element symbols."""
        payload = {
            "name": "bad-molecule",
            "atoms": [{"symbol": "A", "x": 0.0, "y": 0.0, "z": 0.0}],
        }

        response = client.post(MOLECULES_API_PATH, json=payload)

        assert response.status_code == 422
        assert "Atom symbol 'A' is not supported" in response.text

    def test_create_molecule_empty_atoms(self, client: ASGISyncTestClient):
        """Test molecule creation fails with empty atoms list."""
        payload = {
            "name": "EmptyAtoms",
            "atoms": [],
        }

        response = client.post(MOLECULES_API_PATH, json=payload)
        assert response.status_code == 422

    def test_create_molecule_atom_missing_symbol(self, client: ASGISyncTestClient):
        """Test molecule creation fails when atom symbol is missing."""
        payload = {
            "name": "BadAtom",
            "atoms": [{"x": 0.0, "y": 0.0, "z": 0.0}],
        }

        response = client.post(MOLECULES_API_PATH, json=payload)
        assert response.status_code == 422

    def test_create_molecule_atom_invalid_coordinate_type(self, client: ASGISyncTestClient):
        """Test molecule creation fails with invalid coordinate type."""
        payload = {
            "name": "BadCoord",
            "atoms": [{"symbol": "H", "x": "NaN?", "y": 0.0, "z": 0.0}],
        }

        response = client.post(MOLECULES_API_PATH, json=payload)
        assert response.status_code == 422

    def test_create_molecule_invalid_multiplicity(self, client: ASGISyncTestClient):
        """Test molecule creation fails when multiplicity < 1."""
        payload = {
            "name": "InvalidMultiplicity",
            "atoms": [{"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.0}],
            "multiplicity": 0,
        }

        response = client.post(MOLECULES_API_PATH, json=payload)
        assert response.status_code == 422


class TestMoleculeList:
    """Tests for GET /api/molecules endpoint."""

    def test_list_molecules_uses_synchronous_handler(self, test_db: Session) -> None:
        params = MoleculeListParams.model_validate({"limit": 25, "offset": 0})

        response = molecules_endpoint.list_molecules(params, test_db)

        assert response.total == 0

    def test_list_molecules_empty(self, client: ASGISyncTestClient):
        """Test listing molecules when none exist."""
        response = client.get(MOLECULES_API_PATH)

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_molecules_single(self, client: ASGISyncTestClient, sample_molecule: Molecule):
        """Test listing molecules with one molecule."""
        response = client.get(MOLECULES_API_PATH)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == str(sample_molecule.id)
        assert data["items"][0]["name"] == sample_molecule.name

    def test_list_molecules_refreshes_legacy_unbounded_automatic_active_space(
        self, client: ASGISyncTestClient, test_db: Session
    ):
        """Listing molecules migrates old all-valence automatic active spaces."""
        molecule = Molecule(
            name="Caffeine",
            atoms=[
                *[{"symbol": "C", "x": float(index), "y": 0.0, "z": 0.0} for index in range(8)],
                *[{"symbol": "H", "x": float(index), "y": 1.0, "z": 0.0} for index in range(10)],
                *[{"symbol": "N", "x": float(index), "y": 2.0, "z": 0.0} for index in range(4)],
                *[{"symbol": "O", "x": float(index), "y": 3.0, "z": 0.0} for index in range(2)],
            ],
            charge=0,
            multiplicity=1,
            active_space={
                "n_electrons": 74,
                "n_orbitals": 66,
                "method": "automatic_valence",
                "source": "periodic_table_valence",
                "total_valence_orbitals": 66,
            },
        )
        test_db.add(molecule)
        test_db.commit()

        response = client.get(MOLECULES_API_PATH)

        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["active_space"]["method"] == "automatic_frontier_estimate"
        assert item["active_space"]["n_electrons"] == 8
        assert item["active_space"]["n_orbitals"] == 8

    def test_list_molecules_multiple(self, client: ASGISyncTestClient, test_db: Session):
        """Test listing multiple molecules."""
        for i in range(3):
            molecule = Molecule(
                name=f"Molecule_{i}",
                atoms=[{"symbol": "H", "x": float(i), "y": 0.0, "z": 0.0}],
                charge=0,
                multiplicity=1,
            )
            test_db.add(molecule)
        test_db.commit()

        response = client.get(MOLECULES_API_PATH)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    def test_list_molecules_ordered_by_creation_newest_first(
        self, client: ASGISyncTestClient, test_db: Session
    ):
        """Test that molecules are ordered by creation date (newest first)."""
        for i in range(3):
            molecule = Molecule(
                name=f"Molecule_{i}",
                atoms=[{"symbol": "H", "x": float(i), "y": 0.0, "z": 0.0}],
                charge=0,
                multiplicity=1,
            )
            test_db.add(molecule)
            test_db.commit()

        response = client.get(MOLECULES_API_PATH)

        assert response.status_code == 200
        molecules = response.json()["items"]
        assert molecules[0]["name"] == "Molecule_2"
        assert molecules[1]["name"] == "Molecule_1"
        assert molecules[2]["name"] == "Molecule_0"

    def test_list_molecules_filter_by_name(self, client: ASGISyncTestClient, test_db: Session):
        """Test filtering molecules by name substring."""
        for name in ["H2O", "H2S", "CO2"]:
            test_db.add(
                Molecule(
                    name=name,
                    atoms=[{"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.0}],
                    charge=0,
                    multiplicity=1,
                )
            )
        test_db.commit()

        response = client.get("/api/molecules?q=H2")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        names = {m["name"] for m in data["items"]}
        assert names == {"H2O", "H2S"}

    def test_list_molecules_filter_by_pubchem_metadata(
        self, client: ASGISyncTestClient, test_db: Session
    ):
        """Test filtering by iupac_name and synonyms metadata."""
        water = Molecule(
            name="H2O",
            atoms=[
                {"symbol": "O", "x": 0.0, "y": 0.0, "z": 0.0},
                {"symbol": "H", "x": 0.757, "y": 0.586, "z": 0.0},
                {"symbol": "H", "x": -0.757, "y": 0.586, "z": 0.0},
            ],
            charge=0,
            multiplicity=1,
            iupac_name="oxidane",
            synonyms=["water", "dihydrogen monoxide"],
        )
        methane = Molecule(
            name="CH4",
            atoms=[
                {"symbol": "C", "x": 0.0, "y": 0.0, "z": 0.0},
                {"symbol": "H", "x": 0.6, "y": 0.6, "z": 0.6},
                {"symbol": "H", "x": -0.6, "y": -0.6, "z": 0.6},
                {"symbol": "H", "x": -0.6, "y": 0.6, "z": -0.6},
                {"symbol": "H", "x": 0.6, "y": -0.6, "z": -0.6},
            ],
            charge=0,
            multiplicity=1,
            iupac_name="methane",
            synonyms=["marsh gas"],
        )
        test_db.add_all([water, methane])
        test_db.commit()

        response = client.get("/api/molecules?q=water")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "H2O"

    def test_list_molecules_with_legacy_unsupported_atoms_stays_readable(
        self, client: ASGISyncTestClient, test_db: Session
    ):
        """Legacy persisted molecules with unsupported atoms should not crash the list view."""
        molecule = Molecule(
            name="legacy-invalid",
            atoms=[
                {"symbol": "A", "x": 0.0, "y": 0.0, "z": 0.0},
                {"symbol": "Fr", "x": 1.0, "y": 0.0, "z": 0.0},
                {"symbol": "O", "x": 0.0, "y": 1.0, "z": 0.0},
            ],
            charge=0,
            multiplicity=1,
        )
        test_db.add(molecule)
        test_db.commit()

        response = client.get(MOLECULES_API_PATH)

        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["name"] == "legacy-invalid"
        assert [atom["symbol"] for atom in item["atoms"]] == ["A", "Fr", "O"]
        assert item["eligibility"]["selectable"] is False
        assert item["eligibility"]["label"] == "Unsupported atoms"
        assert "A, Fr" in item["eligibility"]["reason"]
        assert item["blocking_reasons"] == [item["eligibility"]["reason"]]
        assert item["runnable_algorithms"] == []

    def test_list_molecules_pagination(self, client: ASGISyncTestClient, test_db: Session):
        """Test limit and offset pagination."""
        for i in range(5):
            test_db.add(
                Molecule(
                    name=f"M{i}",
                    atoms=[{"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.0}],
                    charge=0,
                    multiplicity=1,
                )
            )
        test_db.commit()

        response = client.get("/api/molecules?limit=2&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2

    def test_list_molecule_summaries_returns_compact_formula_and_atom_count(
        self, client: ASGISyncTestClient, test_db: Session
    ):
        """GET /api/molecules/summaries returns compact list items for the library table."""
        molecule = Molecule(
            name="Ethanol",
            atoms=[
                {"symbol": "C", "x": 0.0, "y": 0.0, "z": 0.0},
                {"symbol": "C", "x": 1.5, "y": 0.0, "z": 0.0},
                {"symbol": "O", "x": 2.1, "y": 1.1, "z": 0.0},
                {"symbol": "H", "x": -0.5, "y": 0.9, "z": 0.0},
                {"symbol": "H", "x": -0.5, "y": -0.9, "z": 0.0},
                {"symbol": "H", "x": 1.8, "y": -0.9, "z": 0.0},
                {"symbol": "H", "x": 1.8, "y": 0.9, "z": 0.0},
                {"symbol": "H", "x": 2.6, "y": 1.1, "z": 0.9},
                {"symbol": "H", "x": 2.6, "y": 1.1, "z": -0.9},
            ],
            charge=0,
            multiplicity=1,
            iupac_name="ethanol",
        )
        test_db.add(molecule)
        test_db.commit()

        response = client.get("/api/molecules/summaries")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        item = data["items"][0]
        assert item["id"] == str(molecule.id)
        assert item["name"] == "Ethanol"
        assert item["charge"] == 0
        assert item["atom_count"] == 9
        assert item["formula"] == "C2H6O"
        assert item["iupac_name"] == "ethanol"
        assert item["eligibility"]["selectable"] is True
        assert item["eligibility"]["label"] == "Large active space"
        assert "SQD" in item["eligibility"]["capability_labels"]


class TestMoleculeGet:
    """Tests for GET /api/molecules/{molecule_id} endpoint."""

    def test_get_molecule_success(self, client: ASGISyncTestClient, sample_molecule: Molecule):
        """Test successfully retrieving a molecule."""
        response = client.get(f"/api/molecules/{sample_molecule.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(sample_molecule.id)
        assert data["name"] == sample_molecule.name

    def test_get_molecule_with_legacy_unsupported_atoms_stays_readable(
        self, client: ASGISyncTestClient, test_db: Session
    ):
        """GET by id should surface legacy unsupported atoms instead of returning 500."""
        molecule = Molecule(
            name="legacy-invalid",
            atoms=[
                {"symbol": "A", "x": 0.0, "y": 0.0, "z": 0.0},
                {"symbol": "Fr", "x": 1.0, "y": 0.0, "z": 0.0},
            ],
            charge=0,
            multiplicity=1,
        )
        test_db.add(molecule)
        test_db.commit()
        test_db.refresh(molecule)

        response = client.get(f"/api/molecules/{molecule.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(molecule.id)
        assert [atom["symbol"] for atom in data["atoms"]] == ["A", "Fr"]
        assert data["eligibility"]["selectable"] is False
        assert data["eligibility"]["label"] == "Unsupported atoms"
        assert data["charge"] == molecule.charge
        assert data["multiplicity"] == molecule.multiplicity
        assert data["atoms"] == molecule.atoms
        assert data["active_space"] == molecule.active_space

    def test_get_molecule_not_found(self, client: ASGISyncTestClient):
        """Test retrieving non-existent molecule returns 404."""
        fake_id = uuid4()
        response = client.get(f"/api/molecules/{fake_id}")

        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "NOT_FOUND"

    def test_get_molecule_invalid_uuid(self, client: ASGISyncTestClient):
        """Test retrieving molecule with invalid UUID format."""
        response = client.get("/api/molecules/not-a-uuid")
        assert response.status_code == 422


class TestMoleculeUpdate:
    """Tests for PATCH /api/molecules/{molecule_id} endpoint."""

    def test_update_molecule_name(self, client: ASGISyncTestClient, sample_molecule: Molecule):
        """Test updating molecule name."""
        response = client.patch(
            f"/api/molecules/{sample_molecule.id}",
            json={"name": "H2_updated"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "H2_updated"
        assert data["id"] == str(sample_molecule.id)

    def test_update_molecule_atoms(self, client: ASGISyncTestClient, sample_molecule: Molecule):
        """Test updating molecule atoms."""
        new_atoms = [
            {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.0},
            {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.8},
        ]
        response = client.patch(
            f"/api/molecules/{sample_molecule.id}",
            json={"atoms": new_atoms},
        )

        assert response.status_code == 200
        assert response.json()["atoms"] == new_atoms

    def test_update_molecule_multiple_fields(
        self, client: ASGISyncTestClient, sample_molecule: Molecule
    ):
        """Test updating multiple fields at once."""
        payload = {
            "name": "H2_multi_updated",
            "charge": -1,
            "multiplicity": 2,
            "active_space": {"n_electrons": 2, "n_orbitals": 2, "method": "avas"},
        }
        response = client.patch(f"/api/molecules/{sample_molecule.id}", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "H2_multi_updated"
        assert data["charge"] == -1
        assert data["multiplicity"] == 2
        assert data["active_space"]["method"] == "avas"

    def test_update_molecule_duplicate_name_conflict(
        self, client: ASGISyncTestClient, sample_molecule: Molecule, test_db: Session
    ):
        """Test updating to a name that already exists fails."""
        other = Molecule(
            name="Other_molecule",
            atoms=[{"symbol": "He", "x": 0.0, "y": 0.0, "z": 0.0}],
            charge=0,
            multiplicity=1,
        )
        test_db.add(other)
        test_db.commit()

        response = client.patch(
            f"/api/molecules/{sample_molecule.id}",
            json={"name": other.name},
        )

        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "CONFLICT"

    def test_update_molecule_not_found(self, client: ASGISyncTestClient):
        """Test updating non-existent molecule returns 404."""
        fake_id = uuid4()
        response = client.patch(f"/api/molecules/{fake_id}", json={"name": "Updated"})

        assert response.status_code == 404

    def test_update_molecule_partial_update_preserves_fields(
        self, client: ASGISyncTestClient, sample_molecule: Molecule
    ):
        """Test that partial updates preserve existing fields."""
        original_atoms = sample_molecule.atoms

        response = client.patch(
            f"/api/molecules/{sample_molecule.id}",
            json={"name": "Updated_name"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated_name"
        assert data["atoms"] == original_atoms

    def test_update_molecule_active_space_to_null(
        self, client: ASGISyncTestClient, sample_molecule: Molecule
    ):
        """Test clearing active_space with explicit null."""
        response = client.patch(
            f"/api/molecules/{sample_molecule.id}",
            json={"active_space": None},
        )

        assert response.status_code == 200
        assert response.json()["active_space"] is None

    def test_update_molecule_null_name_returns_422(
        self, client: ASGISyncTestClient, sample_molecule: Molecule
    ):
        """Test that explicit null for name returns 422 validation error."""
        response = client.patch(
            f"/api/molecules/{sample_molecule.id}",
            json={"name": None},
        )
        assert response.status_code == 422

    def test_update_molecule_null_atoms_returns_422(
        self, client: ASGISyncTestClient, sample_molecule: Molecule
    ):
        """Test that explicit null for atoms returns 422 validation error."""
        response = client.patch(
            f"/api/molecules/{sample_molecule.id}",
            json={"atoms": None},
        )
        assert response.status_code == 422

    def test_update_molecule_null_charge_returns_422(
        self, client: ASGISyncTestClient, sample_molecule: Molecule
    ):
        """Test that explicit null for charge returns 422 validation error."""
        response = client.patch(
            f"/api/molecules/{sample_molecule.id}",
            json={"charge": None},
        )
        assert response.status_code == 422

    def test_update_molecule_null_multiplicity_returns_422(
        self, client: ASGISyncTestClient, sample_molecule: Molecule
    ):
        """Test that explicit null for multiplicity returns 422 validation error."""
        response = client.patch(
            f"/api/molecules/{sample_molecule.id}",
            json={"multiplicity": None},
        )
        assert response.status_code == 422


class TestMoleculeDelete:
    """Tests for DELETE /api/molecules/{molecule_id} endpoint."""

    def test_delete_molecule_success(self, client: ASGISyncTestClient, sample_molecule: Molecule):
        """Test successfully deleting a molecule."""
        response = client.delete(f"/api/molecules/{sample_molecule.id}")

        assert response.status_code == 204
        assert response.content == b""

        get_response = client.get(f"/api/molecules/{sample_molecule.id}")
        assert get_response.status_code == 404

    def test_delete_molecule_not_found(self, client: ASGISyncTestClient):
        """Test deleting non-existent molecule returns 404."""
        fake_id = uuid4()
        response = client.delete(f"/api/molecules/{fake_id}")

        assert response.status_code == 404

    def test_delete_molecule_with_runs_conflict(
        self, client: ASGISyncTestClient, sample_molecule: Molecule, sample_run
    ):
        """Test that deleting molecule with associated runs fails."""
        response = client.delete(f"/api/molecules/{sample_molecule.id}")

        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "CONFLICT"

        get_response = client.get(f"/api/molecules/{sample_molecule.id}")
        assert get_response.status_code == 200

    def test_delete_molecule_can_also_delete_associated_runs(
        self, client: ASGISyncTestClient, sample_molecule: Molecule, sample_run
    ):
        """Test deleting a molecule together with its associated runs."""
        response = client.delete(f"/api/molecules/{sample_molecule.id}?delete_associated_runs=true")

        assert response.status_code == 204
        assert response.content == b""

        get_response = client.get(f"/api/molecules/{sample_molecule.id}")
        assert get_response.status_code == 404

        run_response = client.get(f"/api/runs/{sample_run.id}")
        assert run_response.status_code == 404


class TestMoleculeEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_molecule_name_max_length(self, client: ASGISyncTestClient):
        """Test creating molecule with maximum-length name."""
        payload = {
            "name": "A" * 255,
            "atoms": [{"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.0}],
        }

        response = client.post(MOLECULES_API_PATH, json=payload)
        assert response.status_code == 201

    def test_molecule_name_exceeds_max_length(self, client: ASGISyncTestClient):
        """Test creating molecule with name exceeding maximum length."""
        payload = {
            "name": "A" * 256,
            "atoms": [{"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.0}],
        }

        response = client.post(MOLECULES_API_PATH, json=payload)
        assert response.status_code == 422

    def test_molecule_negative_charge(self, client: ASGISyncTestClient):
        """Test creating molecule with negative charge."""
        payload = {
            "name": "Anion",
            "atoms": [
                {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.0},
                {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.735},
            ],
            "charge": -1,
            "multiplicity": 2,
        }

        response = client.post(MOLECULES_API_PATH, json=payload)

        assert response.status_code == 201
        assert response.json()["charge"] == -1

    def test_molecule_positive_charge(self, client: ASGISyncTestClient):
        """Test creating molecule with positive charge."""
        payload = {
            "name": "Cation",
            "atoms": [{"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.0}],
            "charge": 1,
            "multiplicity": 2,
        }

        response = client.post(MOLECULES_API_PATH, json=payload)

        assert response.status_code == 201
        assert response.json()["charge"] == 1

    def test_molecule_multiplicity_triplet(self, client: ASGISyncTestClient):
        """Test creating molecule with triplet multiplicity."""
        payload = {
            "name": "Triplet",
            "atoms": [{"symbol": "O", "x": 0.0, "y": 0.0, "z": 0.0}],
            "charge": 0,
            "multiplicity": 3,
        }

        response = client.post(MOLECULES_API_PATH, json=payload)

        assert response.status_code == 201
        assert response.json()["multiplicity"] == 3


class TestMoleculeRunSeparation:
    """Tests verifying that basis_set lives on runs, not on molecules.

    Migration 20260227_0003 moved basis_set from the molecules table to the
    runs table. These tests enforce that contract at the API level.
    """

    def test_molecule_response_has_no_basis_set(self, client: ASGISyncTestClient):
        """MoleculeResponse must not include basis_set — it lives on runs."""
        payload = {
            "name": "H2_sep_test",
            "atoms": [
                {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.0},
                {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.735},
            ],
        }
        response = client.post(MOLECULES_API_PATH, json=payload)

        assert response.status_code == 201
        assert "basis_set" not in response.json()

    def test_create_molecule_rejects_basis_set_field(self, client: ASGISyncTestClient):
        """POST /api/molecules rejects basis_set as an extra forbidden field."""
        payload = {
            "name": "H2_extra_basis",
            "atoms": [{"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.0}],
            "basis_set": "sto-3g",
        }
        response = client.post(MOLECULES_API_PATH, json=payload)

        assert response.status_code == 422

    def test_list_molecules_response_has_no_basis_set(
        self, client: ASGISyncTestClient, sample_molecule: Molecule
    ):
        """GET /api/molecules items must not contain basis_set."""
        response = client.get(MOLECULES_API_PATH)

        assert response.status_code == 200
        for item in response.json()["items"]:
            assert "basis_set" not in item

    def test_same_molecule_reusable_across_different_basis_sets(
        self, client: ASGISyncTestClient, sample_molecule: Molecule
    ):
        """The same molecule can be used in runs with different basis sets.

        basis_set is a run-level computational parameter, not an intrinsic
        property of molecular geometry — the same geometry can be simulated
        at any level of theory.
        """
        base_run_payload = {
            "algorithm": "vqe",
            "mode": "advanced",
            "backend_target": "statevector",
            "advanced_config": {
                "algorithm": "vqe",
                "ansatz_name": "UCC",
                "optimizer_name": "COBYLA",
                "max_iterations": 10,
            },
        }
        basis_sets = ["sto-3g", "6-31g"]
        run_ids: set[str] = set()

        for basis in basis_sets:
            response = client.post(
                "/api/runs",
                json={
                    "molecule_id": str(sample_molecule.id),
                    **base_run_payload,
                    "basis_set_override": basis,
                },
            )
            assert response.status_code == 201
            data = response.json()
            run_ids.add(data["id"])
            assert data["config_json"]["basis_set_override"] == basis

        # Two distinct runs were created for the same molecule
        assert len(run_ids) == 2

    def test_run_config_basis_set_not_on_molecule(
        self, client: ASGISyncTestClient, sample_molecule: Molecule
    ):
        """Creating a run stores basis_set in config_json; the molecule is unchanged."""
        response = client.post(
            "/api/runs",
            json={
                "molecule_id": str(sample_molecule.id),
                "algorithm": "vqe",
                "mode": "advanced",
                "backend_target": "statevector",
                "basis_set_override": "6-31g",
                "advanced_config": {
                    "algorithm": "vqe",
                    "ansatz_name": "UCC",
                    "optimizer_name": "COBYLA",
                    "max_iterations": 10,
                },
            },
        )
        assert response.status_code == 201
        assert response.json()["config_json"]["basis_set_override"] == "6-31g"

        # The molecule itself must still have no basis_set
        mol_response = client.get(f"/api/molecules/{sample_molecule.id}")
        assert mol_response.status_code == 200
        assert "basis_set" not in mol_response.json()
