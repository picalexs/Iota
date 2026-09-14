"""Integration tests for run-service count queries."""

from __future__ import annotations

from app.models.molecule import Molecule
from app.models.run import Run, RunStatus
from app.models.run_result import RunResult
from app.services.run import RunService
from sqlalchemy import inspect
from sqlalchemy.orm import Session


class TestRunServiceCount:
    def test_list_runs_count_uses_db_aggregation(self, test_db: Session, sample_molecule: Molecule):
        for _ in range(5):
            run = Run(
                molecule_id=sample_molecule.id,
                status=RunStatus.CREATED,
                config_json={
                    "basis_set": "sto-3g",
                    "ansatz": "UCC",
                    "optimizer": "COBYLA",
                    "max_iterations": 100,
                    "backend": "aer_simulator",
                },
            )
            test_db.add(run)
        test_db.commit()

        # The regression target is a COUNT query, not loading rows into memory.
        original_scalar = test_db.scalar
        scalar_calls = []

        def mock_scalar(statement, *args, **kwargs):
            scalar_calls.append(statement)
            return original_scalar(statement, *args, **kwargs)

        test_db.scalar = mock_scalar

        service = RunService(test_db)
        runs, total = service.list(molecule_id=None, status=None, limit=10, offset=0)

        count_call_found = False
        for call in scalar_calls:
            call_str = str(call)
            if "count" in call_str.lower():
                count_call_found = True
                break

        assert count_call_found, (
            "Expected db.scalar to be called with a count query using func.count()"
        )
        assert total == 5, f"Expected total count of 5, got {total}"
        assert len(runs) == 5, f"Expected 5 runs returned, got {len(runs)}"

    def test_list_runs_count_with_filters(self, test_db: Session, sample_molecule: Molecule):
        for status in [RunStatus.CREATED, RunStatus.CREATED, RunStatus.QUEUED]:
            run = Run(
                molecule_id=sample_molecule.id,
                status=status,
                config_json={
                    "basis_set": "sto-3g",
                    "ansatz": "UCC",
                    "optimizer": "COBYLA",
                    "max_iterations": 100,
                    "backend": "aer_simulator",
                },
            )
            test_db.add(run)
        test_db.commit()

        service = RunService(test_db)
        runs, total = service.list(molecule_id=None, status=RunStatus.CREATED, limit=10, offset=0)

        assert total == 2, f"Expected total count of 2, got {total}"
        assert len(runs) == 2, f"Expected 2 runs returned, got {len(runs)}"
        assert all(r.status == RunStatus.CREATED for r in runs)

    def test_list_runs_pagination_with_count(self, test_db: Session, sample_molecule: Molecule):
        for _ in range(15):
            run = Run(
                molecule_id=sample_molecule.id,
                status=RunStatus.CREATED,
                config_json={
                    "basis_set": "sto-3g",
                    "ansatz": "UCC",
                    "optimizer": "COBYLA",
                    "max_iterations": 100,
                    "backend": "aer_simulator",
                },
            )
            test_db.add(run)
        test_db.commit()

        service = RunService(test_db)

        runs_p1, total = service.list(molecule_id=None, status=None, limit=10, offset=0)
        assert total == 15
        assert len(runs_p1) == 10

        runs_p2, total = service.list(molecule_id=None, status=None, limit=10, offset=10)
        assert total == 15
        assert len(runs_p2) == 5

        ids_p1 = {r.id for r in runs_p1}
        ids_p2 = {r.id for r in runs_p2}
        assert len(ids_p1 & ids_p2) == 0

    def test_list_runs_keeps_heavy_result_payloads_deferred(
        self, test_db: Session, sample_molecule: Molecule
    ):
        """Summary-style list queries should not eagerly hydrate large result JSON blobs."""
        run = Run(
            molecule_id=sample_molecule.id,
            status=RunStatus.COMPLETED,
            config_json={"backend_options": {"backend_name": "aer_simulator"}},
        )
        test_db.add(run)
        test_db.flush()
        test_db.add(
            RunResult(
                run_id=run.id,
                energy=-1.1,
                reference_energy=-1.101,
                signed_error=0.001,
                iterations=4,
                optimal_parameters=[0.1, -0.2],
                converged=True,
                algorithm_metrics={"history": [-1.0, -1.05, -1.1]},
                raw_result={"debug": "payload"},
            )
        )
        test_db.commit()

        service = RunService(test_db)
        runs, total = service.list(limit=10, offset=0)

        assert total == 1
        result = runs[0].result
        assert result is not None
        result_state = inspect(result)
        assert "algorithm_metrics" in result_state.unloaded
        assert "optimal_parameters" in result_state.unloaded
        assert "raw_result" in result_state.unloaded
