"""Integration tests for the queued-to-completed run lifecycle."""

from __future__ import annotations

from uuid import UUID

import pytest
from app.models.molecule import Molecule
from app.models.run import Run, RunStatus
from app.models.run_event import RunEvent
from app.models.run_result import RunResult
from sqlalchemy.orm import Session

from tests.conftest import ASGISyncTestClient

RUNS_API_PATH = "/api/runs"


class TestRunLifecycle:
    """Integration checks for create -> queued -> completed lifecycle."""

    def test_vqe_run_lifecycle_queued_to_completed(
        self,
        client_with_redis: ASGISyncTestClient,
        test_db: Session,
        sample_molecule: Molecule,
    ):
        """VQE payload transitions from QUEUED to COMPLETED with persisted result metrics."""
        payload = {
            "molecule_id": str(sample_molecule.id),
            "algorithm": "vqe",
            "mode": "advanced",
            "backend_target": "statevector",
            "advanced_config": {
                "algorithm": "vqe",
                "ansatz_name": "EfficientSU2",
                "optimizer_name": "COBYLA",
                "max_iterations": 30,
            },
        }

        create_response = client_with_redis.post(RUNS_API_PATH, json=payload)

        assert create_response.status_code == 201
        created = create_response.json()
        assert created["status"] == "QUEUED"
        assert created["metadata"]["rq_job_id"] == "test-rq-job-id"
        assert created["algorithm"] == "vqe"

        run_id = UUID(created["id"])
        run = test_db.get(Run, run_id)
        assert run is not None

        run.status = RunStatus.COMPLETED
        test_db.add(
            RunEvent(
                run_id=run_id,
                sequence=1,
                type="status_changed",
                payload={"old_status": "QUEUED", "new_status": "RUNNING"},
            )
        )
        test_db.add(
            RunEvent(
                run_id=run_id,
                sequence=2,
                type="result",
                payload={"algorithm": "vqe", "energy": -1.1372, "iterations": 30},
            )
        )
        test_db.add(
            RunResult(
                run_id=run_id,
                energy=-1.1372,
                iterations=30,
                optimal_parameters=[0.1, -0.2],
                converged=True,
                algorithm_metrics={"history": [-1.05, -1.11, -1.1372]},
            )
        )
        test_db.commit()

        run_response = client_with_redis.get(f"/api/runs/{run_id}")
        assert run_response.status_code == 200
        run_data = run_response.json()
        assert run_data["status"] == "COMPLETED"
        assert run_data["algorithm"] == "vqe"

        result_response = client_with_redis.get(f"/api/runs/{run_id}/result")
        assert result_response.status_code == 200
        result_data = result_response.json()
        assert result_data["energy"] == -1.1372
        assert result_data["iterations"] == 30
        assert result_data["algorithm_metrics"] == {"history": [-1.05, -1.11, -1.1372]}

        events_response = client_with_redis.get(f"/api/runs/{run_id}/events")
        assert events_response.status_code == 200
        events_data = events_response.json()
        assert events_data["last_sequence"] == 2
        assert [event["type"] for event in events_data["events"]] == [
            "status_changed",
            "result",
        ]

    def test_sqd_run_lifecycle_queued_to_completed(
        self,
        client_with_redis: ASGISyncTestClient,
        test_db: Session,
        sample_molecule: Molecule,
    ):
        """SQD payload transitions from QUEUED to COMPLETED with SQD diagnostics."""
        payload = {
            "molecule_id": str(sample_molecule.id),
            "algorithm": "sqd",
            "mode": "advanced",
            "backend_target": "statevector",
            "advanced_config": {
                "algorithm": "sqd",
                "samples_per_batch": 128,
                "num_batches": 4,
                "max_iterations": 5,
                "num_elec_a": 1,
                "num_elec_b": 1,
            },
        }

        create_response = client_with_redis.post(RUNS_API_PATH, json=payload)

        assert create_response.status_code == 201
        created = create_response.json()
        assert created["status"] == "QUEUED"
        assert created["metadata"]["rq_job_id"] == "test-rq-job-id"
        assert created["algorithm"] == "sqd"

        run_id = UUID(created["id"])
        run = test_db.get(Run, run_id)
        assert run is not None

        run.status = RunStatus.COMPLETED
        test_db.add(
            RunEvent(
                run_id=run_id,
                sequence=1,
                type="status_changed",
                payload={"old_status": "QUEUED", "new_status": "RUNNING"},
            )
        )
        test_db.add(
            RunEvent(
                run_id=run_id,
                sequence=2,
                type="result",
                payload={"algorithm": "sqd", "energy": -1.333, "iterations": 5},
            )
        )
        test_db.add(
            RunResult(
                run_id=run_id,
                energy=-1.333,
                iterations=5,
                optimal_parameters=[],
                converged=True,
                algorithm_metrics={
                    "postselection_summary": {"selected_fraction": 0.67},
                    "subsampling_summary": {"num_batches": 4},
                    "sci_result_package": {"final_energy": -1.333},
                },
            )
        )
        test_db.commit()

        run_response = client_with_redis.get(f"/api/runs/{run_id}")
        assert run_response.status_code == 200
        run_data = run_response.json()
        assert run_data["status"] == "COMPLETED"
        assert run_data["algorithm"] == "sqd"

        result_response = client_with_redis.get(f"/api/runs/{run_id}/result")
        assert result_response.status_code == 200
        result_data = result_response.json()
        assert result_data["energy"] == pytest.approx(-1.333)
        assert result_data["iterations"] == 5
        assert result_data["algorithm_metrics"]["postselection_summary"][
            "selected_fraction"
        ] == pytest.approx(0.67)
        assert result_data["algorithm_metrics"]["subsampling_summary"]["num_batches"] == 4
        assert result_data["algorithm_metrics"]["sci_result_package"][
            "final_energy"
        ] == pytest.approx(-1.333)

        events_response = client_with_redis.get(f"/api/runs/{run_id}/events")
        assert events_response.status_code == 200
        events_data = events_response.json()
        assert events_data["last_sequence"] == 2
        assert [event["type"] for event in events_data["events"]] == [
            "status_changed",
            "result",
        ]

    def test_qse_run_lifecycle_queued_to_completed(
        self,
        client_with_redis: ASGISyncTestClient,
        test_db: Session,
        sample_molecule: Molecule,
    ):
        """QSE payload transitions from QUEUED to COMPLETED with eigenvalue metrics."""
        payload = {
            "molecule_id": str(sample_molecule.id),
            "algorithm": "qse",
            "mode": "advanced",
            "backend_target": "statevector",
            "advanced_config": {
                "algorithm": "qse",
                "reference_method": "vqe",
                "excitation_level": "singles",
                "max_subspace_dim": 4,
            },
        }

        create_response = client_with_redis.post(RUNS_API_PATH, json=payload)

        assert create_response.status_code == 201
        created = create_response.json()
        assert created["status"] == "QUEUED"
        assert created["metadata"]["rq_job_id"] == "test-rq-job-id"
        assert created["algorithm"] == "qse"

        run_id = UUID(created["id"])
        run = test_db.get(Run, run_id)
        assert run is not None

        run.status = RunStatus.COMPLETED
        test_db.add(
            RunEvent(
                run_id=run_id,
                sequence=1,
                type="status_changed",
                payload={"old_status": "QUEUED", "new_status": "RUNNING"},
            )
        )
        test_db.add(
            RunEvent(
                run_id=run_id,
                sequence=2,
                type="result",
                payload={"algorithm": "qse", "energy": -1.101, "iterations": 4},
            )
        )
        test_db.add(
            RunResult(
                run_id=run_id,
                energy=-1.101,
                iterations=4,
                optimal_parameters=[],
                converged=True,
                algorithm_metrics={
                    "eigenvalues": [-1.125, -1.101],
                    "overlap_condition": 1.2,
                    "reference_state_energy": -1.09,
                },
            )
        )
        test_db.commit()

        run_response = client_with_redis.get(f"/api/runs/{run_id}")
        assert run_response.status_code == 200
        run_data = run_response.json()
        assert run_data["status"] == "COMPLETED"
        assert run_data["algorithm"] == "qse"

        result_response = client_with_redis.get(f"/api/runs/{run_id}/result")
        assert result_response.status_code == 200
        result_data = result_response.json()
        assert result_data["energy"] == -1.101
        assert result_data["iterations"] == 4
        assert result_data["algorithm_metrics"]["eigenvalues"] == [-1.125, -1.101]
        assert result_data["algorithm_metrics"]["reference_state_energy"] == -1.09

        events_response = client_with_redis.get(f"/api/runs/{run_id}/events")
        assert events_response.status_code == 200
        events_data = events_response.json()
        assert events_data["last_sequence"] == 2
        assert [event["type"] for event in events_data["events"]] == [
            "status_changed",
            "result",
        ]

    def test_skqd_run_lifecycle_queued_to_completed(
        self,
        client_with_redis: ASGISyncTestClient,
        test_db: Session,
        sample_molecule: Molecule,
    ):
        """SKQD payload transitions from QUEUED to COMPLETED with nested metrics."""
        payload = {
            "molecule_id": str(sample_molecule.id),
            "algorithm": "skqd",
            "mode": "advanced",
            "backend_target": "statevector",
            "advanced_config": {
                "algorithm": "skqd",
                "samples_per_state": 128,
                "base_sampling_options": {
                    "num_elec_a": 1,
                    "num_elec_b": 1,
                },
                "krylov_extension_dim": 3,
            },
        }

        create_response = client_with_redis.post(RUNS_API_PATH, json=payload)

        assert create_response.status_code == 201
        created = create_response.json()
        assert created["status"] == "QUEUED"
        assert created["metadata"]["rq_job_id"] == "test-rq-job-id"
        assert created["algorithm"] == "skqd"

        run_id = UUID(created["id"])
        run = test_db.get(Run, run_id)
        assert run is not None

        run.status = RunStatus.COMPLETED
        test_db.add(
            RunEvent(
                run_id=run_id,
                sequence=1,
                type="status_changed",
                payload={"old_status": "QUEUED", "new_status": "RUNNING"},
            )
        )
        test_db.add(
            RunEvent(
                run_id=run_id,
                sequence=2,
                type="result",
                payload={"algorithm": "skqd", "energy": -1.202, "iterations": 6},
            )
        )
        test_db.add(
            RunResult(
                run_id=run_id,
                energy=-1.202,
                iterations=6,
                optimal_parameters=[],
                converged=True,
                algorithm_metrics={
                    "sqd_core": {
                        "algorithm": "sqd",
                        "primary_energy": -1.205,
                        "primary_iterations": 3,
                        "sci_result_package": {"final_energy": -1.205},
                    },
                    "krylov_extension_diagnostics": {
                        "krylov_extension_dim": 3.0,
                        "ritz_values": [-1.21, -1.205, -1.202],
                    },
                },
            )
        )
        test_db.commit()

        run_response = client_with_redis.get(f"/api/runs/{run_id}")
        assert run_response.status_code == 200
        run_data = run_response.json()
        assert run_data["status"] == "COMPLETED"
        assert run_data["algorithm"] == "skqd"

        result_response = client_with_redis.get(f"/api/runs/{run_id}/result")
        assert result_response.status_code == 200
        result_data = result_response.json()
        assert result_data["energy"] == -1.202
        assert result_data["iterations"] == 6
        assert result_data["algorithm_metrics"]["sqd_core"]["algorithm"] == "sqd"
        assert result_data["algorithm_metrics"]["krylov_extension_diagnostics"]["ritz_values"] == [
            -1.21,
            -1.205,
            -1.202,
        ]

        events_response = client_with_redis.get(f"/api/runs/{run_id}/events")
        assert events_response.status_code == 200
        events_data = events_response.json()
        assert events_data["last_sequence"] == 2
        assert [event["type"] for event in events_data["events"]] == [
            "status_changed",
            "result",
        ]
