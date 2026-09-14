"""Integration coverage for run listing, retrieval, results, events, and export."""

from __future__ import annotations

from uuid import uuid4

from app.models import BackendTarget, RunAlgorithm, RunMode
from app.models.molecule import Molecule
from app.models.run import Run, RunStatus
from app.models.run_event import RunEvent
from app.models.run_result import RunResult
from sqlalchemy.orm import Session

from tests.conftest import ASGISyncTestClient

RUNS_API_PATH = "/api/runs"


class TestRunList:
    """Tests for GET /api/runs endpoint."""

    def test_list_runs_empty(self, client: ASGISyncTestClient):
        """Test listing runs when none exist."""
        response = client.get(RUNS_API_PATH)

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["limit"] == 50
        assert data["offset"] == 0

    def test_list_runs_single(self, client: ASGISyncTestClient, sample_run: Run):
        """Test listing runs with one run."""
        response = client.get(RUNS_API_PATH)

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == str(sample_run.id)
        assert data["items"][0]["status"] == "CREATED"
        assert data["total"] == 1

    def test_list_runs_multiple(
        self, client: ASGISyncTestClient, test_db: Session, sample_molecule: Molecule
    ):
        """Test listing multiple runs."""
        for i in range(3):
            run = Run(
                molecule_id=sample_molecule.id,
                status=RunStatus.CREATED,
                config_json={
                    "basis_set": "sto-3g",
                    "ansatz": "UCC",
                    "optimizer": "COBYLA",
                    "max_iterations": 100 + i,
                    "backend": "aer_simulator",
                },
            )
            test_db.add(run)
        test_db.commit()

        response = client.get(RUNS_API_PATH)

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3
        assert data["total"] == 3

    def test_list_runs_pagination(
        self, client: ASGISyncTestClient, test_db: Session, sample_molecule: Molecule
    ):
        """Test pagination with limit and offset."""
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

        response = client.get("/api/runs?limit=2&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5
        assert data["limit"] == 2
        assert data["offset"] == 0

        response = client.get("/api/runs?limit=2&offset=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["offset"] == 2

    def test_list_runs_filter_by_molecule(
        self, client: ASGISyncTestClient, test_db: Session, sample_molecule: Molecule
    ):
        """Test filtering runs by molecule_id."""
        other_molecule = Molecule(
            name="Other_molecule",
            atoms=[{"symbol": "He", "x": 0.0, "y": 0.0, "z": 0.0}],
            charge=0,
            multiplicity=1,
        )
        test_db.add(other_molecule)
        test_db.commit()

        for _ in range(2):
            run1 = Run(
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
            run2 = Run(
                molecule_id=other_molecule.id,
                status=RunStatus.CREATED,
                config_json={
                    "basis_set": "sto-3g",
                    "ansatz": "UCC",
                    "optimizer": "COBYLA",
                    "max_iterations": 100,
                    "backend": "aer_simulator",
                },
            )
            test_db.add_all([run1, run2])
        test_db.commit()

        # Filter by first molecule
        response = client.get(f"/api/runs?molecule_id={sample_molecule.id}")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert all(str(item["molecule_id"]) == str(sample_molecule.id) for item in data["items"])

    def test_list_runs_filter_by_status(
        self, client: ASGISyncTestClient, test_db: Session, sample_molecule: Molecule
    ):
        """Test filtering runs by status."""
        for status in [RunStatus.CREATED, RunStatus.QUEUED, RunStatus.RUNNING, RunStatus.CREATED]:
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

        response = client.get("/api/runs?status=CREATED")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert all(item["status"] == "CREATED" for item in data["items"])

    def test_list_runs_filter_by_backend_target(
        self, client: ASGISyncTestClient, test_db: Session, sample_molecule: Molecule
    ):
        """Test filtering runs by backend_target."""
        for backend_target in [
            BackendTarget.STATEVECTOR,
            BackendTarget.IBM_RUNTIME,
            BackendTarget.IBM_RUNTIME,
            BackendTarget.AER_SIMULATOR,
        ]:
            run = Run(
                molecule_id=sample_molecule.id,
                status=RunStatus.CREATED,
                algorithm=RunAlgorithm.VQE,
                backend_target=backend_target,
                config_json={"backend_options": {}},
            )
            test_db.add(run)
        test_db.commit()

        response = client.get("/api/runs?backend_target=ibm_runtime")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert all(item["backend_target"] == "ibm_runtime" for item in data["items"])

    def test_list_runs_filter_by_invalid_status_returns_422(self, client: ASGISyncTestClient):
        """Test that invalid status filter values are rejected."""
        response = client.get("/api/runs?status=NOT_A_STATUS")
        assert response.status_code == 422

    def test_list_runs_filter_by_submitted_to_ibm_status(
        self,
        client: ASGISyncTestClient,
        test_db: Session,
        sample_molecule: Molecule,
    ):
        """Test filtering runs by SUBMITTED_TO_IBM status."""
        for status in [
            RunStatus.CREATED,
            RunStatus.SUBMITTED_TO_IBM,
            RunStatus.SUBMITTED_TO_IBM,
            RunStatus.RUNNING,
        ]:
            run = Run(
                molecule_id=sample_molecule.id,
                status=status,
                config_json={
                    "basis_set": "sto-3g",
                    "ansatz": "UCC",
                    "optimizer": "COBYLA",
                    "max_iterations": 100,
                    "backend": "ibm_brisbane",
                },
            )
            test_db.add(run)
        test_db.commit()

        response = client.get("/api/runs?status=SUBMITTED_TO_IBM")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert all(item["status"] == "SUBMITTED_TO_IBM" for item in data["items"])

    def test_list_runs_ordered_by_creation_newest_first(
        self, client: ASGISyncTestClient, test_db: Session, sample_molecule: Molecule
    ):
        """Test that runs are ordered by creation date (newest first)."""
        run_ids = []
        for _ in range(3):
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
            run_ids.append(run.id)

        response = client.get(RUNS_API_PATH)

        assert response.status_code == 200
        data = response.json()
        # Should be in reverse order (newest first)
        assert str(data["items"][0]["id"]) == str(run_ids[2])
        assert str(data["items"][1]["id"]) == str(run_ids[1])
        assert str(data["items"][2]["id"]) == str(run_ids[0])

    def test_list_run_summaries_return_compact_rows(
        self, client: ASGISyncTestClient, test_db: Session, sample_molecule: Molecule
    ):
        """GET /api/runs/summaries returns list-optimized rows without full config payloads."""
        run = Run(
            molecule_id=sample_molecule.id,
            status=RunStatus.RUNNING,
            algorithm=RunAlgorithm.VQE,
            backend_target=BackendTarget.IBM_RUNTIME,
            config_json={
                "backend_options": {
                    "backend_name": "ibm_brisbane",
                    "selection_policy": "manual",
                }
            },
            latest_estimate={
                "source": "telemetry",
                "algorithm": "vqe",
                "estimated_total_iterations": 50,
                "estimated_remaining_iterations": 17,
                "estimated_total_seconds": 600.0,
                "estimated_remaining_seconds": 180.0,
                "estimated_primary_iterations": None,
                "estimated_reference_iterations": None,
                "estimated_total_work_units": None,
                "work_unit_policy": None,
                "reference_workload": None,
                "confidence": 0.8,
                "updated_at": "2026-05-18T10:00:00Z",
            },
            run_metadata={
                "run_started_at": "2026-05-18T09:55:00Z",
            },
        )
        test_db.add(run)
        test_db.commit()

        response = client.get("/api/runs/summaries")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["limit"] == 50
        assert data["offset"] == 0
        assert data["items"] == [
            {
                "id": str(run.id),
                "molecule_id": str(sample_molecule.id),
                "molecule_name": sample_molecule.name,
                "status": "RUNNING",
                "algorithm": "vqe",
                "backend_target": "ibm_runtime",
                "backend_name": "ibm_brisbane",
                "converged": None,
                "chemical_accurate": None,
                "execution_generation": 1,
                "restarted_from_run_id": None,
                "credential_profile_id": None,
                "credential_profile_name": None,
                "basis_set": "sto-3g",
                "metadata": {
                    "run_started_at": "2026-05-18T09:55:00Z",
                },
                "latest_estimate": {
                    "source": "telemetry",
                    "algorithm": "vqe",
                    "estimated_total_iterations": 50,
                    "estimated_remaining_iterations": 17,
                    "estimated_total_seconds": 600.0,
                    "estimated_remaining_seconds": 180.0,
                    "estimated_primary_iterations": None,
                    "estimated_reference_iterations": None,
                    "estimated_total_work_units": None,
                    "work_unit_policy": None,
                    "reference_workload": None,
                    "confidence": 0.8,
                    "updated_at": "2026-05-18T10:00:00Z",
                },
                "created_at": run.created_at.isoformat().replace("+00:00", "Z"),
                "updated_at": run.updated_at.isoformat().replace("+00:00", "Z"),
            }
        ]

    def test_list_run_summaries_include_result_convergence(
        self, client: ASGISyncTestClient, test_db: Session, sample_molecule: Molecule
    ):
        """GET /api/runs/summaries exposes the persisted convergence flag when available."""
        run = Run(
            molecule_id=sample_molecule.id,
            status=RunStatus.COMPLETED,
            algorithm=RunAlgorithm.VQE,
            backend_target=BackendTarget.STATEVECTOR,
            config_json={"backend_options": {}},
        )
        test_db.add(run)
        test_db.flush()
        test_db.add(
            RunResult(
                run_id=run.id,
                energy=-1.1,
                iterations=12,
                optimal_parameters=[],
                converged=False,
            )
        )
        test_db.commit()

        response = client.get("/api/runs/summaries")

        assert response.status_code == 200
        data = response.json()
        assert data["items"][0]["id"] == str(run.id)
        assert data["items"][0]["converged"] is False
        assert data["items"][0]["chemical_accurate"] is None

    def test_list_run_summaries_filter_by_backend_target_and_chemical_accuracy(
        self, client: ASGISyncTestClient, test_db: Session, sample_molecule: Molecule
    ):
        """GET /api/runs/summaries filters by backend target and chemical-accuracy verdict."""
        matching_run = Run(
            molecule_id=sample_molecule.id,
            status=RunStatus.COMPLETED,
            algorithm=RunAlgorithm.VQE,
            backend_target=BackendTarget.IBM_RUNTIME,
            config_json={
                "backend_options": {"backend_name": "ibm_brisbane"},
                "chemical_accuracy_target_ha": 0.0016,
            },
        )
        excluded_backend_run = Run(
            molecule_id=sample_molecule.id,
            status=RunStatus.COMPLETED,
            algorithm=RunAlgorithm.VQE,
            backend_target=BackendTarget.STATEVECTOR,
            config_json={"backend_options": {}},
        )
        excluded_convergence_run = Run(
            molecule_id=sample_molecule.id,
            status=RunStatus.COMPLETED,
            algorithm=RunAlgorithm.VQE,
            backend_target=BackendTarget.IBM_RUNTIME,
            config_json={
                "backend_options": {"backend_name": "ibm_kyiv"},
                "chemical_accuracy_target_ha": 0.0016,
            },
        )
        test_db.add_all([matching_run, excluded_backend_run, excluded_convergence_run])
        test_db.flush()
        test_db.add_all(
            [
                RunResult(
                    run_id=matching_run.id,
                    energy=-1.2,
                    reference_energy=-1.201,
                    signed_error=0.001,
                    iterations=8,
                    optimal_parameters=[],
                    converged=False,
                ),
                RunResult(
                    run_id=excluded_backend_run.id,
                    energy=-1.15,
                    reference_energy=-1.1505,
                    signed_error=0.0005,
                    iterations=10,
                    optimal_parameters=[],
                    converged=False,
                ),
                RunResult(
                    run_id=excluded_convergence_run.id,
                    energy=-1.18,
                    reference_energy=-1.185,
                    signed_error=0.005,
                    iterations=11,
                    optimal_parameters=[],
                    converged=True,
                ),
            ]
        )
        test_db.commit()

        response = client.get(
            "/api/runs/summaries?backend_target=ibm_runtime&chemical_accurate=true"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert [item["id"] for item in data["items"]] == [str(matching_run.id)]
        assert data["items"][0]["backend_target"] == "ibm_runtime"
        assert data["items"][0]["converged"] is False
        assert data["items"][0]["chemical_accurate"] is True


class TestRunGet:
    """Tests for GET /api/runs/{run_id} endpoint."""

    def test_get_run_success(self, client: ASGISyncTestClient, sample_run: Run):
        """Test successfully retrieving a run."""
        response = client.get(f"/api/runs/{sample_run.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(sample_run.id)
        assert data["status"] == sample_run.status
        assert data["molecule_id"] == str(sample_run.molecule_id)

    def test_get_run_not_found(self, client: ASGISyncTestClient):
        """Test retrieving non-existent run returns 404."""
        fake_id = uuid4()
        response = client.get(f"/api/runs/{fake_id}")

        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["code"] == "NOT_FOUND"


class TestRunGetResult:
    """Tests for GET /api/runs/{run_id}/result endpoint."""

    def test_get_run_result_success(
        self, client: ASGISyncTestClient, test_db: Session, sample_run: Run
    ):
        """Test successfully retrieving run result."""
        # Create a run result
        result = RunResult(
            run_id=sample_run.id,
            energy=-1.1372,
            iterations=42,
            optimal_parameters=[0.1587, -0.2201],
            converged=True,
        )
        test_db.add(result)
        test_db.commit()

        response = client.get(f"/api/runs/{sample_run.id}/result")

        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == str(sample_run.id)
        assert data["energy"] == -1.1372
        assert data["iterations"] == 42
        assert data["converged"] is True

    def test_get_run_result_not_found_no_result(self, client: ASGISyncTestClient, sample_run: Run):
        """Test retrieving result for run without result returns 404."""
        response = client.get(f"/api/runs/{sample_run.id}/result")

        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["code"] == "NOT_FOUND"

    def test_get_run_result_not_found_invalid_run(self, client: ASGISyncTestClient):
        """Test retrieving result for non-existent run returns 404."""
        fake_id = uuid4()
        response = client.get(f"/api/runs/{fake_id}/result")

        assert response.status_code == 404


class TestRunGetEvents:
    """Tests for GET /api/runs/{run_id}/events endpoint."""

    def test_get_run_events_empty(self, client: ASGISyncTestClient, sample_run: Run):
        """Test retrieving events for run with no events."""
        response = client.get(f"/api/runs/{sample_run.id}/events")

        assert response.status_code == 200
        data = response.json()
        assert data["events"] == []
        assert data["last_sequence"] == 0

    def test_get_run_events_single(
        self, client: ASGISyncTestClient, test_db: Session, sample_run: Run
    ):
        """Test retrieving single event."""
        event = RunEvent(
            run_id=sample_run.id,
            sequence=1,
            type="status_changed",
            payload={"status": "RUNNING"},
        )
        test_db.add(event)
        test_db.commit()

        response = client.get(f"/api/runs/{sample_run.id}/events")

        assert response.status_code == 200
        data = response.json()
        assert len(data["events"]) == 1
        assert data["events"][0]["sequence"] == 1
        assert data["events"][0]["type"] == "status_changed"
        assert data["last_sequence"] == 1

    def test_get_run_events_multiple(
        self, client: ASGISyncTestClient, test_db: Session, sample_run: Run
    ):
        """Test retrieving multiple events."""
        events_data = [
            {"type": "status_changed", "payload": {"status": "RUNNING"}},
            {"type": "iteration_update", "payload": {"iteration": 1, "energy": -1.042}},
            {"type": "iteration_update", "payload": {"iteration": 2, "energy": -1.105}},
        ]

        for i, event_data in enumerate(events_data, 1):
            event = RunEvent(
                run_id=sample_run.id,
                sequence=i,
                type=event_data["type"],
                payload=event_data["payload"],
            )
            test_db.add(event)
        test_db.commit()

        response = client.get(f"/api/runs/{sample_run.id}/events")

        assert response.status_code == 200
        data = response.json()
        assert len(data["events"]) == 3
        assert data["last_sequence"] == 3

    def test_get_run_events_after_sequence(
        self, client: ASGISyncTestClient, test_db: Session, sample_run: Run
    ):
        """Test retrieving events after specific sequence."""
        for i in range(1, 6):
            event = RunEvent(
                run_id=sample_run.id,
                sequence=i,
                type="iteration_update",
                payload={"iteration": i},
            )
            test_db.add(event)
        test_db.commit()

        response = client.get(f"/api/runs/{sample_run.id}/events?after_sequence=2")

        assert response.status_code == 200
        data = response.json()
        assert len(data["events"]) == 3  # Events 3, 4, 5
        assert data["events"][0]["sequence"] == 3
        assert data["events"][-1]["sequence"] == 5
        assert data["last_sequence"] == 5

    def test_get_run_events_not_found(self, client: ASGISyncTestClient):
        """Test retrieving events for non-existent run returns 404."""
        fake_id = uuid4()
        response = client.get(f"/api/runs/{fake_id}/events")

        assert response.status_code == 404


class TestRunExport:
    """Tests for GET /api/runs/{run_id}/export endpoint."""

    def test_export_run_created(
        self, client: ASGISyncTestClient, sample_run: Run, sample_molecule: Molecule
    ):
        """Test export for a CREATED run returns a partial bundle (no result)."""
        response = client.get(f"/api/runs/{sample_run.id}/export")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        assert "attachment" in response.headers.get("content-disposition", "")

        data = response.json()
        assert data["export_version"] == "1.0"
        assert "exported_at" in data
        assert data["molecule"]["id"] == str(sample_molecule.id)
        assert data["run"]["id"] == str(sample_run.id)
        assert data["events"] == []
        assert data["result"] is None

    def test_export_run_with_result(
        self, client: ASGISyncTestClient, test_db: Session, sample_run: Run
    ):
        """Test export for a COMPLETED run includes the result."""
        from app.models.run_result import RunResult

        sample_run.algorithm = RunAlgorithm.VQE
        sample_run.mode = RunMode.EASY
        sample_run.backend_target = BackendTarget.STATEVECTOR
        sample_run.initial_estimate = {
            "source": "heuristic",
            "algorithm": "vqe",
            "estimated_total_iterations": 100,
            "estimated_remaining_iterations": 100,
            "estimated_total_seconds": 100.0,
            "estimated_remaining_seconds": 100.0,
            "confidence": 0.3,
            "updated_at": "2026-04-09T12:00:00+00:00",
        }
        sample_run.latest_estimate = {
            "source": "telemetry",
            "algorithm": "vqe",
            "estimated_total_iterations": 100,
            "estimated_remaining_iterations": 12,
            "estimated_total_seconds": 100.0,
            "estimated_remaining_seconds": 12.0,
            "confidence": 0.6,
            "updated_at": "2026-04-09T12:10:00+00:00",
        }
        result = RunResult(
            run_id=sample_run.id,
            energy=-1.1372,
            iterations=42,
            optimal_parameters=[0.1587, -0.2201],
            converged=True,
        )
        sample_run.status = RunStatus.COMPLETED
        test_db.add(result)
        test_db.commit()

        response = client.get(f"/api/runs/{sample_run.id}/export")

        assert response.status_code == 200
        data = response.json()
        assert data["result"]["energy"] == -1.1372
        assert data["result"]["converged"] is True
        assert data["result"]["algorithm_metrics"] is None
        assert data["run"]["status"] == "COMPLETED"
        assert data["run"]["algorithm"] == "vqe"
        assert data["run"]["mode"] == "easy"
        assert data["run"]["backend_target"] == "statevector"
        assert data["run"]["initial_estimate"]["source"] == "heuristic"
        assert data["run"]["latest_estimate"]["source"] == "telemetry"

    def test_export_run_not_found(self, client: ASGISyncTestClient):
        """Test export for non-existent run returns 404."""
        fake_id = uuid4()
        response = client.get(f"/api/runs/{fake_id}/export")

        assert response.status_code == 404
