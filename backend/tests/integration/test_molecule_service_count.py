"""Integration tests for molecule-service count queries."""

from __future__ import annotations

from app.models.molecule import Molecule
from app.services.molecule import MoleculeService
from sqlalchemy.orm import Session


class TestMoleculeServiceCount:
    def test_list_molecules_count_uses_db_aggregation(self, test_db: Session):
        for i in range(5):
            molecule = Molecule(
                name=f"molecule_{i}",
                atoms=[
                    {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.0},
                    {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.735},
                ],
                charge=0,
                multiplicity=1,
            )
            test_db.add(molecule)
        test_db.commit()

        # The regression target is a COUNT query, not loading rows into memory.
        original_scalar = test_db.scalar
        scalar_calls = []

        def mock_scalar(statement, *args, **kwargs):
            scalar_calls.append(statement)
            return original_scalar(statement, *args, **kwargs)

        test_db.scalar = mock_scalar

        service = MoleculeService(test_db)
        result = service.list_all(q=None, charge=None, limit=10, offset=0)

        count_call_found = False
        for call in scalar_calls:
            call_str = str(call)
            if "count" in call_str.lower():
                count_call_found = True
                break

        assert count_call_found, (
            "Expected db.scalar to be called with a count query using func.count()"
        )
        assert result["total"] == 5, f"Expected total count of 5, got {result['total']}"
        assert len(result["items"]) == 5, (
            f"Expected 5 molecules returned, got {len(result['items'])}"
        )

    def test_list_molecules_count_with_search_filter(self, test_db: Session):
        for name in ["water", "methane", "ethane"]:
            molecule = Molecule(
                name=name,
                atoms=[
                    {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.0},
                ],
                charge=0,
                multiplicity=1,
            )
            test_db.add(molecule)
        test_db.commit()

        service = MoleculeService(test_db)
        result = service.list_all(q="water", charge=None, limit=10, offset=0)

        assert result["total"] == 1, f"Expected total count of 1, got {result['total']}"
        assert len(result["items"]) == 1, (
            f"Expected 1 molecule returned, got {len(result['items'])}"
        )
        assert result["items"][0].name == "water"

    def test_list_molecules_count_with_charge_filter(self, test_db: Session):
        for i, charge in enumerate([0, 1, 0]):
            molecule = Molecule(
                name=f"mol_charge_{charge}_{i}",
                atoms=[
                    {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.0},
                ],
                charge=charge,
                multiplicity=1,
            )
            test_db.add(molecule)
        test_db.commit()

        service = MoleculeService(test_db)
        result = service.list_all(q=None, charge=0, limit=10, offset=0)

        assert result["total"] == 2, f"Expected total count of 2, got {result['total']}"
        assert len(result["items"]) == 2, (
            f"Expected 2 molecules returned, got {len(result['items'])}"
        )
        assert all(m.charge == 0 for m in result["items"])

    def test_list_molecules_pagination_with_count(self, test_db: Session):
        for i in range(15):
            molecule = Molecule(
                name=f"molecule_{i}",
                atoms=[
                    {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.0},
                ],
                charge=0,
                multiplicity=1,
            )
            test_db.add(molecule)
        test_db.commit()

        service = MoleculeService(test_db)

        result_p1 = service.list_all(q=None, charge=None, limit=10, offset=0)
        assert result_p1["total"] == 15
        assert len(result_p1["items"]) == 10

        result_p2 = service.list_all(q=None, charge=None, limit=10, offset=10)
        assert result_p2["total"] == 15
        assert len(result_p2["items"]) == 5

        ids_p1 = {m.id for m in result_p1["items"]}
        ids_p2 = {m.id for m in result_p2["items"]}
        assert len(ids_p1 & ids_p2) == 0
