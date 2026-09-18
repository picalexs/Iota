"""Integration coverage for run creation, enqueueing, and configuration metadata."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from app.api.v1.endpoints import runs as runs_endpoint
from app.models import BackendTarget, RunAlgorithm
from app.models.molecule import Molecule
from app.models.run import Run
from app.schemas.backend import BackendResolveResponse, BackendSummary
from app.schemas.run import BackendSelectionPolicy, RunCreate
from app.schemas.settings import IbmRuntimeCredentials
from app.services.run import RunService
from fastapi import BackgroundTasks
from sqlalchemy.orm import Session
from starlette.requests import Request

from tests.conftest import ASGISyncTestClient

_CREDENTIAL_FIELD = "to" + "ken"
_DUMMY_CREDENTIAL_VALUE = "dummy-credential-value"
RUNS_API_PATH = "/api/runs"


class TestRunCreate:
    """Tests for POST /api/runs endpoint."""

    @pytest.mark.asyncio
    async def test_create_run_uses_threadpool(
        self,
        monkeypatch: pytest.MonkeyPatch,
        test_db: Session,
        sample_molecule: Molecule,
    ) -> None:
        payload = RunCreate.model_validate(
            {
                "molecule_id": str(sample_molecule.id),
                "algorithm": "vqe",
                "mode": "advanced",
                "backend_target": "statevector",
                "advanced_config": {
                    "algorithm": "vqe",
                    "ansatz_name": "EfficientSU2",
                    "optimizer_name": "COBYLA",
                    "max_iterations": 50,
                },
            }
        )
        captured: dict[str, object] = {}

        async def fake_run_in_threadpool(func, *args):
            captured["func"] = func
            captured["args"] = args
            return func(*args)

        monkeypatch.setattr(runs_endpoint, "run_in_threadpool", fake_run_in_threadpool)

        request = Request({"type": "http", "method": "POST", "path": RUNS_API_PATH})
        request.scope["app"] = MagicMock()
        request.app.state.session_factory = None
        background_tasks = BackgroundTasks()

        response = await runs_endpoint.create_run(payload, test_db, None, background_tasks, request)

        assert response.status_code == 201
        assert captured["func"] is runs_endpoint._create_run_for_request
        assert captured["args"] == (test_db, payload, None)

    def test_get_run_uses_sync_service_boundary(
        self,
        test_db: Session,
        sample_run: Run,
    ) -> None:
        response = runs_endpoint.get_run(sample_run.id, test_db)

        assert response.id == sample_run.id

    @pytest.mark.asyncio
    async def test_create_run_returns_immediately_and_schedules_async_estimate_seed(
        self,
        monkeypatch: pytest.MonkeyPatch,
        sample_molecule: Molecule,
        test_db: Session,
    ) -> None:
        payload = RunCreate.model_validate(
            {
                "molecule_id": str(sample_molecule.id),
                "algorithm": "kqd",
                "mode": "easy",
                "backend_target": "aer_simulator",
                "backend_options": {
                    "selection_policy": "manual",
                    "backend_name": "aer_simulator",
                    "shots": 4096,
                    "optimization_level": 1,
                    "aer_method": "automatic",
                },
                "easy_options": {
                    "goal": "balanced",
                },
            }
        )
        request = Request({"type": "http", "method": "POST", "path": RUNS_API_PATH})
        request.scope["app"] = MagicMock()
        request.app.state.session_factory = object()
        background_tasks = BackgroundTasks()
        mock_redis = MagicMock()

        async def fake_run_in_threadpool(func, *args):
            return func(*args)

        monkeypatch.setattr(runs_endpoint, "run_in_threadpool", fake_run_in_threadpool)

        with patch("app.services.run.queue_service.enqueue_run", return_value="test-rq-job-id"):
            response = await runs_endpoint.create_run(
                payload,
                test_db,
                mock_redis,
                background_tasks,
                request,
            )

        assert response.status_code == 201
        data = json.loads(bytes(response.body))
        assert data["initial_estimate"] is None
        assert data["latest_estimate"] is None
        assert len(background_tasks.tasks) == 1
        task = background_tasks.tasks[0]
        assert task.func is runs_endpoint._seed_post_create_estimate
        assert task.args == (request.app.state.session_factory, UUID(data["id"]))

    def test_create_run_preserves_chemical_accuracy_target_snapshot(
        self,
        client: ASGISyncTestClient,
        sample_molecule: Molecule,
    ):
        payload = {
            "molecule_id": str(sample_molecule.id),
            "algorithm": "vqe",
            "mode": "advanced",
            "backend_target": "statevector",
            "chemical_accuracy_target_ha": 0.0016,
            "advanced_config": {
                "algorithm": "vqe",
                "ansatz_name": "EfficientSU2",
                "optimizer_name": "COBYLA",
                "max_iterations": 50,
            },
        }

        response = client.post(RUNS_API_PATH, json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["config_json"]["chemical_accuracy_target_ha"] == pytest.approx(0.0016)

    def test_create_new_contract_rejects_non_singlet_molecule(
        self,
        client: ASGISyncTestClient,
        test_db: Session,
        sample_molecule: Molecule,
    ):
        sample_molecule.multiplicity = 2
        test_db.commit()

        payload = {
            "molecule_id": str(sample_molecule.id),
            "algorithm": "kqd",
            "mode": "advanced",
            "backend_target": "statevector",
            "advanced_config": {
                "algorithm": "kqd",
                "krylov_dim": 3,
                "time_step": 0.1,
                "evolution_method": "exact",
            },
        }

        response = client.post(RUNS_API_PATH, json=payload)

        assert response.status_code == 422
        data = response.json()
        assert data["detail"]["code"] == "VALIDATION_ERROR"
        assert data["detail"]["field"] == "molecule.multiplicity"

    def test_create_new_contract_rejects_odd_active_space_electrons(
        self,
        client: ASGISyncTestClient,
        test_db: Session,
        sample_molecule: Molecule,
    ):
        sample_molecule.active_space = {"n_electrons": 3, "n_orbitals": 2}
        test_db.commit()

        payload = {
            "molecule_id": str(sample_molecule.id),
            "algorithm": "vqe",
            "mode": "advanced",
            "backend_target": "statevector",
            "advanced_config": {
                "algorithm": "vqe",
                "ansatz_name": "EfficientSU2",
                "optimizer_name": "COBYLA",
                "max_iterations": 50,
            },
        }

        response = client.post(RUNS_API_PATH, json=payload)

        assert response.status_code == 422
        data = response.json()
        assert data["detail"]["code"] == "VALIDATION_ERROR"
        assert data["detail"]["field"] == "molecule.active_space.n_electrons"

    def test_create_run_freezes_resolved_ibm_backend_for_least_error_selection(
        self,
        client: ASGISyncTestClient,
        sample_molecule: Molecule,
    ) -> None:
        credentials = IbmRuntimeCredentials.model_validate(
            {
                "profile_id": uuid4(),
                "profile_name": "Primary IBM",
                _CREDENTIAL_FIELD: _DUMMY_CREDENTIAL_VALUE,
                "instance": "hub/group/project",
                "channel": "ibm_quantum_platform",
            }
        )
        resolved_backend = BackendResolveResponse(
            target=BackendTarget.IBM_RUNTIME,
            selection_policy=BackendSelectionPolicy.LEAST_ERROR,
            resolved=True,
            backend_name="ibm_miami",
            backend=BackendSummary(
                target=BackendTarget.IBM_RUNTIME,
                name="ibm_miami",
                display_name="IBM Miami",
                available=True,
                simulator=False,
                supports_noise_profile=False,
                supports_transpile_preview=True,
            ),
            warnings=[],
        )

        with (
            patch(
                "app.services.run.IbmCredentialProfileService.resolve_credentials",
                return_value=credentials,
            ),
            patch(
                "app.services.run.resolve_backend", return_value=resolved_backend
            ) as resolve_mock,
        ):
            response = client.post(
                RUNS_API_PATH,
                json={
                    "molecule_id": str(sample_molecule.id),
                    "algorithm": "vqe",
                    "mode": "advanced",
                    "backend_target": "ibm_runtime",
                    "ibm_runtime_confirmed": True,
                    "backend_options": {
                        "selection_policy": "least_error",
                        "shots": 4096,
                        "optimization_level": 1,
                    },
                    "advanced_config": {
                        "algorithm": "vqe",
                        "ansatz_name": "EfficientSU2",
                        "optimizer_name": "COBYLA",
                        "max_iterations": 50,
                    },
                },
            )

        assert response.status_code == 201
        data = response.json()
        assert data["backend_target"] == "ibm_runtime"
        assert data["credential_profile_id"] == str(credentials.profile_id)
        assert data["credential_profile_name"] == credentials.profile_name
        assert data["config_json"]["backend_options"]["selection_policy"] == "least_error"
        assert data["config_json"]["backend_options"]["backend_name"] == "ibm_miami"
        assert data["config_json"]["backend_options"]["credential_profile_id"] == str(
            credentials.profile_id
        )

        request = resolve_mock.call_args.args[0]
        assert request.target == BackendTarget.IBM_RUNTIME
        assert request.algorithm == RunAlgorithm.VQE
        assert request.required_qubits == 4


class TestRunEnqueue:
    """Tests for the QUEUED path through POST /api/runs."""

    def test_create_new_contract_run_preserves_metadata_when_enqueued(
        self, client_with_redis: ASGISyncTestClient, sample_molecule: Molecule
    ):
        """Algorithm metadata must remain present after rq_job_id is added."""
        payload = {
            "molecule_id": str(sample_molecule.id),
            "algorithm": "vqe",
            "mode": "easy",
            "backend_target": "statevector",
            "easy_options": {"goal": "balanced"},
        }

        response = client_with_redis.post(RUNS_API_PATH, json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "QUEUED"
        assert data["algorithm"] == "vqe"
        assert data["mode"] == "easy"
        assert data["backend_target"] == "statevector"
        assert data["metadata"] is not None
        assert data["metadata"]["algorithm"] == "vqe"
        assert data["metadata"]["mode"] == "easy"
        assert data["metadata"]["backend_target"] == "statevector"
        assert data["metadata"]["rq_job_id"] == "test-rq-job-id"

    def test_create_easy_mode_run_expands_deterministically(
        self,
        test_db: Session,
        sample_molecule: Molecule,
        mock_redis: MagicMock,
    ):
        """Easy-mode runs should expand to the same advanced snapshot every time."""
        payload = RunCreate.model_validate(
            {
                "molecule_id": str(sample_molecule.id),
                "algorithm": "skqd",
                "mode": "easy",
                "backend_target": "statevector",
                "easy_options": {"goal": "balanced"},
            }
        )

        with patch("app.services.queue_service.enqueue_run", return_value="test-rq-job-id"):
            first_run, first_is_new = RunService(test_db).create(payload, redis_client=mock_redis)
            second_run, second_is_new = RunService(test_db).create(payload, redis_client=mock_redis)

        assert first_is_new is True
        assert second_is_new is True

        first_data = runs_endpoint.RunResponse.model_validate(first_run).model_dump(mode="json")
        second_data = runs_endpoint.RunResponse.model_validate(second_run).model_dump(mode="json")

        assert first_data["config_json"] == second_data["config_json"]
        assert first_data["metadata"] == second_data["metadata"]

        easy_mode_metadata = first_data["metadata"]["easy_mode"]
        assert easy_mode_metadata["catalog_version"] == "2026-09-16-v22"
        assert easy_mode_metadata["goal"] == "balanced"

        expanded = easy_mode_metadata["expanded_advanced_config"]
        assert expanded["algorithm"] == "skqd"
        assert expanded["krylov_extension_dim"] == 4
        assert expanded["samples_per_state"] == 1024
        assert expanded["residual_tolerance"] == pytest.approx(1e-6)
        assert expanded["base_sampling_options"]["max_dim"] == 32
        assert expanded["base_sampling_options"]["min_selected_configurations"] == 2
        assert expanded["base_sampling_options"]["num_elec_a"] == 1
        assert expanded["base_sampling_options"]["num_elec_b"] == 1

    def test_create_kqd_run_enqueues_when_redis_available(
        self, client_with_redis: ASGISyncTestClient, sample_molecule: Molecule
    ):
        """KQD advanced payload is accepted and queued with rq_job_id metadata."""
        payload = {
            "molecule_id": str(sample_molecule.id),
            "algorithm": "kqd",
            "mode": "advanced",
            "backend_target": "statevector",
            "advanced_config": {
                "algorithm": "kqd",
                "krylov_dim": 4,
                "time_step": 0.1,
                "evolution_method": "trotter",
                "trotter_steps": 2,
            },
        }

        response = client_with_redis.post(RUNS_API_PATH, json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "QUEUED"
        assert data["algorithm"] == "kqd"
        assert data["mode"] == "advanced"
        assert data["backend_target"] == "statevector"
        assert data["metadata"]["rq_job_id"] == "test-rq-job-id"

    def test_create_qfd_run_enqueues_when_redis_available(
        self, client_with_redis: ASGISyncTestClient, sample_molecule: Molecule
    ):
        """QFD advanced payload is accepted and queued with rq_job_id metadata."""
        payload = {
            "molecule_id": str(sample_molecule.id),
            "algorithm": "qfd",
            "mode": "advanced",
            "backend_target": "statevector",
            "advanced_config": {
                "algorithm": "qfd",
                "num_time_points": 8,
                "max_time": 2.0,
                "time_grid_type": "linear",
            },
        }

        response = client_with_redis.post(RUNS_API_PATH, json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "QUEUED"
        assert data["algorithm"] == "qfd"
        assert data["mode"] == "advanced"
        assert data["backend_target"] == "statevector"
        assert data["metadata"]["rq_job_id"] == "test-rq-job-id"

    def test_create_qse_run_enqueues_when_redis_available(
        self, client_with_redis: ASGISyncTestClient, sample_molecule: Molecule
    ):
        """QSE advanced payload is accepted and queued with rq_job_id metadata."""
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

        response = client_with_redis.post(RUNS_API_PATH, json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "QUEUED"
        assert data["algorithm"] == "qse"
        assert data["mode"] == "advanced"
        assert data["backend_target"] == "statevector"
        assert data["metadata"]["rq_job_id"] == "test-rq-job-id"

    def test_create_skqd_run_enqueues_when_redis_available(
        self, client_with_redis: ASGISyncTestClient, sample_molecule: Molecule
    ):
        """SKQD advanced payload is accepted and queued with rq_job_id metadata."""
        payload = {
            "molecule_id": str(sample_molecule.id),
            "algorithm": "skqd",
            "mode": "advanced",
            "backend_target": "statevector",
            "advanced_config": {
                "algorithm": "skqd",
                "samples_per_state": 64,
                "base_sampling_options": {
                    "num_elec_a": 1,
                    "num_elec_b": 1,
                },
                "krylov_extension_dim": 3,
                "time_step": 0.2,
            },
        }

        response = client_with_redis.post(RUNS_API_PATH, json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "QUEUED"
        assert data["algorithm"] == "skqd"
        assert data["mode"] == "advanced"
        assert data["backend_target"] == "statevector"
        assert data["metadata"]["rq_job_id"] == "test-rq-job-id"
        assert data["config_json"]["advanced_config"]["time_step"] == pytest.approx(0.2)


class TestRunConfigMetadata:
    """Tests for GET /api/runs/config-metadata."""

    def test_get_run_config_metadata_returns_registry_choices(
        self,
        client: ASGISyncTestClient,
    ):
        response = client.get("/api/runs/config-metadata")

        assert response.status_code == 200
        data = response.json()
        assert data["catalog_version"]
        assert data["algorithms"] == ["vqe", "qse", "kqd", "qfd", "sqd", "skqd"]
        assert data["backend_targets"] == ["statevector", "aer_simulator", "ibm_runtime"]
        assert data["easy_goals"] == ["fastest", "balanced", "best_accuracy"]
        assert data["easy_goal_presets"] == [
            {"goal": "fastest", "label": "5.0 mHa", "chemical_accuracy_target_ha": 0.005},
            {"goal": "balanced", "label": "1.6 mHa", "chemical_accuracy_target_ha": 0.0016},
            {
                "goal": "best_accuracy",
                "label": "0.5 mHa",
                "chemical_accuracy_target_ha": 0.0005,
            },
        ]
        assert data["limits"]["advanced_config.max_iterations"]["maximum"] == 5000
        assert data["defaults"]["ansatz_name"] == "NumberPreserving"
        assert {item["id"] for item in data["ansatzes"]} == {
            "EfficientSU2",
            "NumberPreserving",
            "RealAmplitudes",
            "TwoLocal",
        }
        optimizers = {item["id"]: item for item in data["optimizers"]}
        assert set(optimizers) == {"COBYLA", "SPSA", "SLSQP", "L_BFGS_B"}
        assert optimizers["L_BFGS_B"]["metadata"]["supports_max_function_evaluations"] is True
        assert "maxfun" in optimizers["L_BFGS_B"]["metadata"]["allowed_options"]
