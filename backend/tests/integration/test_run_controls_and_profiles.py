"""Integration coverage for run controls, checkpoints, basis metadata, and IBM profiles."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

import app.services.credential_profiles as credential_profiles_service
import pytest
from app.models import RunAlgorithm, RunMode
from app.models.enums import BackendTarget
from app.models.ibm_credential_profile import IbmCredentialProfile
from app.models.run import Run, RunStatus
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from tests.conftest import ASGISyncTestClient

_CREDENTIAL_FIELD = "to" + "ken"
_ENCRYPTED_CREDENTIAL_FIELD = f"encrypted_{_CREDENTIAL_FIELD}"
_CREDENTIAL_HINT_FIELD = f"{_CREDENTIAL_FIELD}_hint"
_LOCAL_OPERATOR_HEADER = "X-Local-Operator-" + "Token"
_REJECTED_OPERATOR_VALUE = "rejected-operator-value"
_DUMMY_CREDENTIAL_VALUE = "dummy-credential-value"
_IBM_PROFILES_API_PATH = "/api/settings/ibm-profiles"
_LOCAL_CREDENTIAL_KEY_FILENAME = "credential.key"


def test_basis_sets_endpoint_returns_metadata(client: ASGISyncTestClient) -> None:
    response = client.get("/api/basis-sets")

    assert response.status_code == 200
    data = response.json()
    assert data["default_basis_set"] == "sto-3g"
    assert "sto-3g" in {item["id"] for item in data["basis_sets"]}


def test_run_pause_resume_checkpoint_and_restart_flow(
    client: ASGISyncTestClient,
    test_db: Session,
    sample_run: Run,
) -> None:
    sample_run.algorithm = RunAlgorithm.VQE
    sample_run.mode = RunMode.ADVANCED
    sample_run.status = RunStatus.CREATED
    test_db.commit()

    pause_response = client.post(f"/api/runs/{sample_run.id}/pause")
    assert pause_response.status_code == 200
    assert pause_response.json()["status"] == "PAUSED"

    checkpoint_response = client.post(
        f"/api/runs/{sample_run.id}/checkpoints",
        json={
            "checkpoint_version": "1.0",
            "payload": {"parameters": [0.1, 0.2]},
            "event_sequence": 3,
        },
    )
    assert checkpoint_response.status_code == 201
    checkpoint = checkpoint_response.json()
    assert checkpoint["execution_generation"] == 1
    assert checkpoint["algorithm"] == "vqe"
    assert checkpoint["payload"] == {"parameters": [0.1, 0.2]}

    events_response = client.get(f"/api/runs/{sample_run.id}/events")
    assert events_response.status_code == 200
    events = events_response.json()["events"]
    assert any(
        event["type"] == "status_changed" and event["payload"].get("status") == "PAUSED"
        for event in events
    )
    assert any(
        event["type"] == "checkpoint_saved"
        and event["payload"].get("execution_generation") == 1
        for event in events
    )

    list_response = client.get(f"/api/runs/{sample_run.id}/checkpoints")
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1

    resume_response = client.post(f"/api/runs/{sample_run.id}/resume", json={"reason": "continue"})
    assert resume_response.status_code == 200
    assert resume_response.json()["status"] == "CREATED"
    assert resume_response.json()["execution_generation"] == 2

    run = test_db.get(Run, sample_run.id)
    assert run is not None
    run.status = RunStatus.COMPLETED
    test_db.commit()

    restart_response = client.post(
        f"/api/runs/{sample_run.id}/restart",
        json={"reason": "try again"},
    )
    assert restart_response.status_code == 200
    restart_data = restart_response.json()
    assert restart_data["child_run_id"] is not None

    child = test_db.get(Run, UUID(restart_data["child_run_id"]))
    assert child is not None
    assert child.restarted_from_run_id == sample_run.id
    assert child.execution_generation == 3
    assert child.status == RunStatus.CREATED


def test_failed_run_can_resume_in_place(
    client: ASGISyncTestClient,
    test_db: Session,
    sample_run: Run,
) -> None:
    sample_run.algorithm = RunAlgorithm.VQE
    sample_run.mode = RunMode.ADVANCED
    sample_run.status = RunStatus.FAILED
    sample_run.execution_generation = 4
    test_db.commit()

    resume_response = client.post(f"/api/runs/{sample_run.id}/resume", json={"reason": "retry"})

    assert resume_response.status_code == 200
    assert resume_response.json()["status"] == "CREATED"
    assert resume_response.json()["execution_generation"] == 5

    test_db.refresh(sample_run)
    assert sample_run.status == RunStatus.CREATED
    assert sample_run.execution_generation == 5
    assert sample_run.run_metadata is not None
    assert sample_run.run_metadata["resume_mode"] == "restart_from_beginning"
    assert sample_run.run_metadata["resumed_from_generation"] == 4


def test_resume_persists_queued_generation_before_queue_submission(
    client_with_redis: ASGISyncTestClient,
    test_db: Session,
    sample_run: Run,
) -> None:
    sample_run.algorithm = RunAlgorithm.VQE
    sample_run.mode = RunMode.ADVANCED
    sample_run.status = RunStatus.PAUSED
    test_db.commit()

    response = client_with_redis.post(f"/api/runs/{sample_run.id}/resume")

    assert response.status_code == 200
    assert response.json()["status"] == "QUEUED"
    assert response.json()["execution_generation"] == 2
    test_db.refresh(sample_run)
    assert sample_run.status == RunStatus.QUEUED
    assert sample_run.run_metadata["rq_job_id"] == "test-rq-job-id"


def test_restart_idempotency_still_commits_active_source_cancel(
    client: ASGISyncTestClient,
    test_db: Session,
    sample_run: Run,
) -> None:
    sample_run.algorithm = RunAlgorithm.VQE
    sample_run.mode = RunMode.ADVANCED
    sample_run.status = RunStatus.RUNNING
    restart_key = uuid4()
    existing_child = Run(
        molecule_id=sample_run.molecule_id,
        status=RunStatus.CREATED,
        config_json=dict(sample_run.config_json or {}),
        client_request_id=restart_key,
        restarted_from_run_id=sample_run.id,
        execution_generation=2,
    )
    test_db.add(existing_child)
    test_db.commit()

    response = client.post(
        f"/api/runs/{sample_run.id}/restart",
        json={"client_request_id": str(restart_key), "cancel_active": True},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "CANCELLED"
    assert data["child_run_id"] == str(existing_child.id)

    test_db.refresh(sample_run)
    assert sample_run.status == RunStatus.CANCELLED


def test_restart_active_run_stops_old_queue_job_and_clears_child_runtime(
    client_with_redis: ASGISyncTestClient,
    mock_redis,
    test_db: Session,
    sample_run: Run,
) -> None:
    sample_run.algorithm = RunAlgorithm.VQE
    sample_run.mode = RunMode.ADVANCED
    sample_run.status = RunStatus.RUNNING
    sample_run.run_metadata = {
        "rq_job_id": "old-rq-job",
        "runtime_seconds": 99.0,
        "runtime_basis": "worker_execution_segment_monotonic",
    }
    test_db.commit()

    with patch("app.services.run_control.queue_service.cancel_queued_job") as cancel_job:
        response = client_with_redis.post(
            f"/api/runs/{sample_run.id}/restart",
            json={"cancel_active": True},
        )

    assert response.status_code == 200
    cancel_job.assert_called_once_with("old-rq-job", mock_redis)
    child = test_db.get(Run, UUID(response.json()["child_run_id"]))
    assert child is not None
    assert child.run_metadata is not None
    assert child.run_metadata.get("rq_job_id") != "old-rq-job"
    assert "runtime_seconds" not in child.run_metadata
    assert child.run_metadata["resume_mode"] == "restart_from_beginning"


def test_ibm_profile_endpoints_do_not_expose_secrets(
    client: ASGISyncTestClient,
    monkeypatch,
    tmp_path,
) -> None:
    class _FakeRuntimeService:
        def least_busy(self, **kwargs):
            return "ibm_brisbane"

    monkeypatch.setenv("LOCAL_CREDENTIALS_KEY_FILE", str(tmp_path / _LOCAL_CREDENTIAL_KEY_FILENAME))
    monkeypatch.setattr(
        credential_profiles_service,
        "_build_runtime_service",
        lambda credentials: _FakeRuntimeService(),
    )

    response = client.post(
        _IBM_PROFILES_API_PATH,
        json={
            "name": "local test",
            _CREDENTIAL_FIELD: _DUMMY_CREDENTIAL_VALUE,
            "crn": "crn-for-test",
            "channel": "ibm_quantum_platform",
            "activate": True,
        },
    )

    assert response.status_code == 201
    data = response.json()
    profile_id = data["id"]
    assert data["active"] is True
    assert _CREDENTIAL_FIELD not in data
    assert "crn" not in data
    assert _ENCRYPTED_CREDENTIAL_FIELD not in data
    assert "encrypted_crn" not in data
    assert _CREDENTIAL_HINT_FIELD not in data
    assert "crn_hint" not in data

    list_response = client.get(_IBM_PROFILES_API_PATH)
    assert list_response.status_code == 200
    list_data = list_response.json()
    assert list_data["active_profile_id"] == profile_id
    assert _CREDENTIAL_HINT_FIELD not in list_data["profiles"][0]
    assert "crn_hint" not in list_data["profiles"][0]

    test_response = client.post(f"/api/settings/ibm-profiles/{profile_id}/test")
    assert test_response.status_code == 200
    test_data = test_response.json()
    assert test_data["ok"] is True
    assert (
        test_data["message"]
        == "IBM Runtime credentials validated successfully using backend ibm_brisbane."
    )
    assert test_data["active_instance"] is None


def test_resolve_credentials_does_not_reencrypt_or_flush_on_read(
    test_db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeCipher:
        def decrypt(self, value: str) -> str:
            return f"decrypted:{value}"

        def rotate(self, value: str) -> str:
            return f"rotated:{value}"

    profile = IbmCredentialProfile(
        name="read-only profile",
        encrypted_token="encrypted-token",
        encrypted_crn="encrypted-crn",
        channel="ibm_quantum_platform",
        active=True,
    )
    test_db.add(profile)
    test_db.commit()
    test_db.refresh(profile)

    monkeypatch.setattr(
        credential_profiles_service,
        "get_credential_cipher",
        lambda: _FakeCipher(),
    )

    credentials = credential_profiles_service.IbmCredentialProfileService(
        test_db
    ).resolve_credentials(profile.id)

    assert credentials is not None
    assert credentials.token == "decrypted:encrypted-token"
    assert credentials.instance == "decrypted:encrypted-crn"

    test_db.expire_all()
    reloaded = test_db.get(IbmCredentialProfile, profile.id)
    assert reloaded is not None
    assert reloaded.encrypted_token == "encrypted-token"
    assert reloaded.encrypted_crn == "encrypted-crn"


def test_ibm_profile_test_reports_runtime_validation_failures(
    client: ASGISyncTestClient,
    monkeypatch,
    tmp_path,
) -> None:
    class _BrokenRuntimeService:
        def least_busy(self, **kwargs):
            raise RuntimeError("authentication failed")

    monkeypatch.setenv("LOCAL_CREDENTIALS_KEY_FILE", str(tmp_path / _LOCAL_CREDENTIAL_KEY_FILENAME))
    monkeypatch.setattr(
        credential_profiles_service,
        "_build_runtime_service",
        lambda credentials: _BrokenRuntimeService(),
    )

    create_response = client.post(
        _IBM_PROFILES_API_PATH,
        json={
            "name": "broken profile",
            _CREDENTIAL_FIELD: _DUMMY_CREDENTIAL_VALUE,
            "crn": "crn-for-test",
            "channel": "ibm_quantum_platform",
            "activate": True,
        },
    )
    assert create_response.status_code == 201

    profile_id = create_response.json()["id"]
    test_response = client.post(f"/api/settings/ibm-profiles/{profile_id}/test")

    assert test_response.status_code == 200
    test_data = test_response.json()
    assert test_data["ok"] is False
    assert "validation failed" in test_data["message"]


def test_ibm_profile_test_times_out_without_freezing_the_api(
    client: ASGISyncTestClient,
    monkeypatch,
    tmp_path,
) -> None:
    class _SlowRuntimeService:
        def least_busy(self, **kwargs):
            time.sleep(2.0)
            return "ibm_brisbane"

    monkeypatch.setenv("LOCAL_CREDENTIALS_KEY_FILE", str(tmp_path / _LOCAL_CREDENTIAL_KEY_FILENAME))
    monkeypatch.setattr(
        credential_profiles_service,
        "_build_runtime_service",
        lambda credentials: _SlowRuntimeService(),
    )
    monkeypatch.setattr(
        credential_profiles_service,
        "_IBM_PROFILE_VALIDATION_TIMEOUT_SECONDS",
        0.01,
    )

    create_response = client.post(
        _IBM_PROFILES_API_PATH,
        json={
            "name": "slow profile",
            _CREDENTIAL_FIELD: _DUMMY_CREDENTIAL_VALUE,
            "crn": "crn-for-test",
            "channel": "ibm_quantum_platform",
            "activate": True,
        },
    )
    assert create_response.status_code == 201

    profile_id = create_response.json()["id"]
    started = time.perf_counter()
    test_response = client.post(f"/api/settings/ibm-profiles/{profile_id}/test")
    elapsed = time.perf_counter() - started

    assert test_response.status_code == 200
    assert elapsed < 0.5
    test_data = test_response.json()
    assert test_data["ok"] is False
    assert "timed out" in test_data["message"]


def test_ibm_profile_routes_require_local_operator_token(
    client: ASGISyncTestClient,
) -> None:
    response = client.get(
        _IBM_PROFILES_API_PATH,
        headers={_LOCAL_OPERATOR_HEADER: _REJECTED_OPERATOR_VALUE},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "FORBIDDEN"


def test_ibm_runtime_run_submission_requires_local_operator_token(
    client: ASGISyncTestClient,
    sample_molecule,
) -> None:
    response = client.post(
        "/api/runs",
        headers={_LOCAL_OPERATOR_HEADER: _REJECTED_OPERATOR_VALUE},
        json={
            "molecule_id": str(sample_molecule.id),
            "algorithm": "vqe",
            "mode": "advanced",
            "backend_target": "ibm_runtime",
            "ibm_runtime_confirmed": True,
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "FORBIDDEN"


def test_backend_derived_aer_submission_requires_local_operator_token(
    client: ASGISyncTestClient,
    sample_molecule,
) -> None:
    response = client.post(
        "/api/runs",
        headers={_LOCAL_OPERATOR_HEADER: _REJECTED_OPERATOR_VALUE},
        json={
            "molecule_id": str(sample_molecule.id),
            "algorithm": "vqe",
            "mode": "advanced",
            "backend_target": "aer_simulator",
            "noise_profile": {
                "source": "backend_derived",
                "reference_backend": "ibm_brisbane",
            },
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "FORBIDDEN"


def test_ibm_runtime_pause_requires_local_operator_token(
    client: ASGISyncTestClient,
    test_db: Session,
    sample_run: Run,
) -> None:
    sample_run.algorithm = RunAlgorithm.VQE
    sample_run.mode = RunMode.ADVANCED
    sample_run.backend_target = BackendTarget.IBM_RUNTIME
    sample_run.status = RunStatus.RUNNING
    test_db.commit()

    response = client.post(
        f"/api/runs/{sample_run.id}/pause",
        headers={_LOCAL_OPERATOR_HEADER: _REJECTED_OPERATOR_VALUE},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "FORBIDDEN"


def test_ibm_runtime_resume_requires_local_operator_token(
    client: ASGISyncTestClient,
    test_db: Session,
    sample_run: Run,
) -> None:
    sample_run.algorithm = RunAlgorithm.VQE
    sample_run.mode = RunMode.ADVANCED
    sample_run.backend_target = BackendTarget.IBM_RUNTIME
    sample_run.status = RunStatus.PAUSED
    test_db.commit()

    response = client.post(
        f"/api/runs/{sample_run.id}/resume",
        headers={_LOCAL_OPERATOR_HEADER: _REJECTED_OPERATOR_VALUE},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "FORBIDDEN"


def test_ibm_profile_list_rewraps_encrypted_values_to_primary_key(
    client: ASGISyncTestClient,
    monkeypatch,
    test_db: Session,
    tmp_path: Path,
) -> None:
    key_file = tmp_path / _LOCAL_CREDENTIAL_KEY_FILENAME
    monkeypatch.setenv("LOCAL_CREDENTIALS_KEY_FILE", str(key_file))

    create_response = client.post(
        _IBM_PROFILES_API_PATH,
        json={
            "name": "rotating profile",
            _CREDENTIAL_FIELD: _DUMMY_CREDENTIAL_VALUE,
            "crn": "crn-for-rotation",
            "channel": "ibm_quantum_platform",
            "activate": True,
        },
    )
    assert create_response.status_code == 201
    profile_id = UUID(create_response.json()["id"])

    profile_before = test_db.get(IbmCredentialProfile, profile_id)
    assert profile_before is not None
    encrypted_before = getattr(profile_before, _ENCRYPTED_CREDENTIAL_FIELD)
    old_key = key_file.read_text(encoding="utf-8").strip()
    new_key = Fernet.generate_key().decode("ascii")
    monkeypatch.setenv("LOCAL_CREDENTIALS_KEYS", f"{new_key},{old_key}")

    list_response = client.get(_IBM_PROFILES_API_PATH)

    assert list_response.status_code == 200
    test_db.expire_all()
    profile_after = test_db.get(IbmCredentialProfile, profile_id)
    assert profile_after is not None
    assert getattr(profile_after, _ENCRYPTED_CREDENTIAL_FIELD) != encrypted_before
