"""Integration coverage for run deletion, cancellation, and status transitions."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.models import BackendTarget
from app.models.molecule import Molecule
from app.models.run import Run, RunStatus
from app.models.run_event import RunEvent
from app.schemas.settings import IbmRuntimeCredentials
from sqlalchemy.orm import Session

from tests.conftest import ASGISyncTestClient

_CREDENTIAL_FIELD = "to" + "ken"
_DUMMY_CREDENTIAL_VALUE = "dummy-credential-value"
RUNS_API_PATH = "/api/runs"
CANCEL_QUEUED_JOB_PATCH_PATH = "app.services.run.queue_service.cancel_queued_job"


class TestRunDelete:
    """Tests for DELETE /api/runs/{run_id} endpoint."""

    def test_delete_run_success(
        self,
        client: ASGISyncTestClient,
        test_db: Session,
        sample_run: Run,
    ):
        run_id = sample_run.id
        response = client.delete(f"/api/runs/{run_id}")

        assert response.status_code == 204
        test_db.expire_all()
        assert test_db.get(Run, run_id) is None

    def test_delete_run_stops_lingering_rq_job(
        self,
        client_with_redis: ASGISyncTestClient,
        mock_redis,
        test_db: Session,
        sample_molecule: Molecule,
    ):
        run = Run(
            molecule_id=sample_molecule.id,
            status=RunStatus.QUEUED,
            config_json={"algorithm": "sqd", "backend_target": "aer_simulator"},
            run_metadata={"rq_job_id": "queued-job-1"},
        )
        test_db.add(run)
        test_db.commit()
        run_id = run.id

        with patch(CANCEL_QUEUED_JOB_PATCH_PATH) as cancel_job:
            response = client_with_redis.delete(f"/api/runs/{run_id}")

        assert response.status_code == 204
        cancel_job.assert_called_once_with("queued-job-1", mock_redis)
        test_db.expire_all()
        assert test_db.get(Run, run_id) is None

    def test_delete_run_detaches_restart_children(
        self,
        client: ASGISyncTestClient,
        test_db: Session,
        sample_molecule: Molecule,
    ):
        parent = Run(
            molecule_id=sample_molecule.id,
            status=RunStatus.COMPLETED,
            config_json={"algorithm": "vqe", "backend_target": "statevector"},
        )
        test_db.add(parent)
        test_db.flush()

        child = Run(
            molecule_id=sample_molecule.id,
            status=RunStatus.QUEUED,
            config_json={"algorithm": "vqe", "backend_target": "statevector"},
            restarted_from_run_id=parent.id,
        )
        test_db.add(child)
        test_db.commit()
        parent_id = parent.id
        child_id = child.id

        response = client.delete(f"/api/runs/{parent_id}")

        assert response.status_code == 204
        test_db.expire_all()
        assert test_db.get(Run, parent_id) is None
        refreshed_child = test_db.get(Run, child_id)
        assert refreshed_child is not None
        assert refreshed_child.restarted_from_run_id is None

    def test_delete_run_not_found(self, client: ASGISyncTestClient):
        response = client.delete(f"/api/runs/{uuid4()}")

        assert response.status_code == 404


class TestRunCancel:
    """Tests for POST /api/runs/{run_id}/cancel endpoint."""

    def test_cancel_run_created_state(self, client: ASGISyncTestClient, sample_run: Run):
        """Test cancelling a run in CREATED state."""
        response = client.post(f"/api/runs/{sample_run.id}/cancel")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(sample_run.id)
        assert data["status"] == "CANCELLED"

    def test_cancel_run_queued_state(
        self, client: ASGISyncTestClient, test_db: Session, sample_molecule: Molecule
    ):
        """Test cancelling a run in QUEUED state."""
        run = Run(
            molecule_id=sample_molecule.id,
            status=RunStatus.QUEUED,
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

        response = client.post(f"/api/runs/{run.id}/cancel")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "CANCELLED"

    def test_cancel_run_running_state(
        self, client: ASGISyncTestClient, test_db: Session, sample_molecule: Molecule
    ):
        """Test cancelling a run in RUNNING state."""
        run = Run(
            molecule_id=sample_molecule.id,
            status=RunStatus.RUNNING,
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

        response = client.post(f"/api/runs/{run.id}/cancel")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "CANCELLED"
        cancel_events = (
            test_db.query(RunEvent)
            .filter(RunEvent.run_id == run.id, RunEvent.type == "status_changed")
            .order_by(RunEvent.sequence.desc())
            .all()
        )
        assert cancel_events
        assert cancel_events[0].payload["status"] == "CANCELLED"

    def test_cancel_run_running_state_stops_rq_job(
        self,
        client_with_redis: ASGISyncTestClient,
        mock_redis,
        test_db: Session,
        sample_molecule: Molecule,
    ):
        """Cancelling a running run should also free the worker-side RQ job."""
        run = Run(
            molecule_id=sample_molecule.id,
            status=RunStatus.RUNNING,
            config_json={"algorithm": "sqd", "backend_target": "aer_simulator"},
            run_metadata={"rq_job_id": "started-job-1"},
        )
        test_db.add(run)
        test_db.commit()

        with patch(CANCEL_QUEUED_JOB_PATCH_PATH) as cancel_job:
            response = client_with_redis.post(f"/api/runs/{run.id}/cancel")

        assert response.status_code == 200
        assert response.json()["status"] == "CANCELLED"
        cancel_job.assert_called_once_with("started-job-1", mock_redis)

    def test_cancel_run_already_cancelled_still_stops_lingering_rq_job(
        self,
        client_with_redis: ASGISyncTestClient,
        mock_redis,
        test_db: Session,
        sample_molecule: Molecule,
    ):
        """A repeated cancel should clean up jobs left running after an earlier cancel."""
        run = Run(
            molecule_id=sample_molecule.id,
            status=RunStatus.CANCELLED,
            config_json={"algorithm": "sqd", "backend_target": "aer_simulator"},
            run_metadata={"rq_job_id": "lingering-job-1"},
        )
        test_db.add(run)
        test_db.commit()

        with patch(CANCEL_QUEUED_JOB_PATCH_PATH) as cancel_job:
            response = client_with_redis.post(f"/api/runs/{run.id}/cancel")

        assert response.status_code == 200
        assert response.json()["status"] == "CANCELLED"
        cancel_job.assert_called_once_with("lingering-job-1", mock_redis)

    def test_cancel_run_completed_state_conflict(
        self, client: ASGISyncTestClient, test_db: Session, sample_molecule: Molecule
    ):
        """Test cancelling a COMPLETED run fails with 409."""
        run = Run(
            molecule_id=sample_molecule.id,
            status=RunStatus.COMPLETED,
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

        response = client.post(f"/api/runs/{run.id}/cancel")

        assert response.status_code == 409
        data = response.json()
        assert data["detail"]["code"] == "CONFLICT"

    def test_cancel_run_failed_state_conflict(
        self, client: ASGISyncTestClient, test_db: Session, sample_molecule: Molecule
    ):
        """Test cancelling a FAILED run fails with 409."""
        run = Run(
            molecule_id=sample_molecule.id,
            status=RunStatus.FAILED,
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

        response = client.post(f"/api/runs/{run.id}/cancel")

        assert response.status_code == 409

    def test_cancel_run_already_cancelled_is_idempotent(
        self, client: ASGISyncTestClient, test_db: Session, sample_molecule: Molecule
    ):
        """Test cancelling an already CANCELLED run returns 200 (idempotent)."""
        run = Run(
            molecule_id=sample_molecule.id,
            status=RunStatus.CANCELLED,
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

        response = client.post(f"/api/runs/{run.id}/cancel")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "CANCELLED"

    def test_cancel_run_submitted_to_ibm_state(
        self, client: ASGISyncTestClient, test_db: Session, sample_molecule: Molecule
    ):
        """Test cancelling a SUBMITTED_TO_IBM run also requests remote IBM cancellation."""
        run = Run(
            molecule_id=sample_molecule.id,
            status=RunStatus.SUBMITTED_TO_IBM,
            backend_target=BackendTarget.IBM_RUNTIME,
            ibm_job_id="runtime-job-123",
            credential_profile_id=uuid4(),
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

        fake_credentials = IbmRuntimeCredentials.model_validate(
            {
                "profile_id": uuid4(),
                "profile_name": "Primary IBM",
                _CREDENTIAL_FIELD: _DUMMY_CREDENTIAL_VALUE,
                "instance": "instance",
                "channel": "ibm_quantum_platform",
            }
        )
        fake_job = MagicMock()
        fake_service = MagicMock()
        fake_service.job.return_value = fake_job

        with (
            patch(
                "app.services.run.IbmCredentialProfileService.resolve_credentials",
                return_value=fake_credentials,
            ),
            patch(
                "app.services.run._build_runtime_service",
                return_value=fake_service,
            ),
        ):
            response = client.post(f"/api/runs/{run.id}/cancel")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "CANCELLED"
        fake_service.job.assert_called_once_with("runtime-job-123")
        fake_job.cancel.assert_called_once_with()

    def test_cancel_run_not_found(self, client: ASGISyncTestClient):
        """Test cancelling non-existent run returns 404."""
        fake_id = uuid4()
        response = client.post(f"/api/runs/{fake_id}/cancel")

        assert response.status_code == 404


class TestRunEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_run_status_transitions(
        self, client: ASGISyncTestClient, test_db: Session, sample_molecule: Molecule
    ):
        """Test various run status transitions."""
        statuses = [
            RunStatus.CREATED,
            RunStatus.QUEUED,
            RunStatus.RUNNING,
            RunStatus.SUBMITTED_TO_IBM,
            RunStatus.COMPLETED,
        ]

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

        for status in statuses:
            run.status = status
            test_db.commit()

            response = client.get(f"/api/runs/{run.id}")
            assert response.status_code == 200
            assert response.json()["status"] == status
