"""Integration tests for benchmark persistence endpoints."""

from __future__ import annotations

import pytest
from app.models.run import Run, RunStatus

from tests.conftest import ASGISyncTestClient

BENCHMARKS_API = "/api/benchmarks"
REGISTRATION_DIGEST = "a" * 64


def _benchmark_payload(name: str = "Saved H2 VQE") -> dict:
    return {
        "name": name,
        "selectedMoleculeKeys": ["h2"],
        "selectedAlgorithms": ["vqe"],
        "selectedBasis": "sto-3g",
        "selectedBackendMode": "statevector",
        "selectedBackendName": None,
        "chemicalAccuracyHa": 0.0016,
        "customMolecules": [],
        "entries": [
            {
                "id": "h2:vqe",
                "preset": {"key": "h2", "name": "Hydrogen"},
                "algorithm": "vqe",
                "status": "completed",
                "moleculeId": "11111111-1111-1111-1111-111111111111",
                "runId": "22222222-2222-2222-2222-222222222222",
                "energy": -1.137,
                "currentEnergy": -1.137,
                "converged": True,
                "errorMessage": None,
                "classicalRefs": {"hf": -1.116, "fci": -1.137},
                "elapsedSeconds": 12.5,
                "latestEventSequence": 4,
            }
        ],
    }


def _campaign_registration_payload(name: str = "Campaign H2") -> dict:
    return {
        **_benchmark_payload(name),
        "campaignId": "campaign-h2-statevector",
        "registrationDigest": REGISTRATION_DIGEST,
        "campaignMetadata": {
            "campaign_target": "statevector",
            "manifest_sha256": "b" * 64,
            "schema_version": "campaign.v1",
        },
        "entries": [
            {
                "id": "h2:vqe:balanced",
                "preset": {
                    "key": "h2",
                    "name": "Hydrogen",
                    "formula": "H2",
                    "description": "Test molecule",
                    "atoms": [{"symbol": "H", "x": 0, "y": 0, "z": 0}],
                    "charge": 0,
                    "multiplicity": 1,
                    "active_space": {"n_electrons": 2, "n_orbitals": 2},
                    "basis": "sto-3g",
                    "references": {"hf": -1.1, "fci": -1.2, "source": "fixture"},
                },
                "algorithm": "vqe",
                "status": "planned",
                "moleculeId": None,
                "runId": None,
                "energy": None,
                "currentEnergy": None,
                "converged": None,
                "errorMessage": None,
                "classicalRefs": None,
                "elapsedSeconds": None,
                "latestEventSequence": 0,
            }
        ],
    }


def test_create_list_get_update_delete_benchmark(client: ASGISyncTestClient) -> None:
    create_response = client.post(BENCHMARKS_API, json=_benchmark_payload())

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["name"] == "Saved H2 VQE"
    assert created["selectedMoleculeKeys"] == ["h2"]
    assert created["selectedAlgorithms"] == ["vqe"]
    assert created["shots"] == 1024
    assert created["chemicalAccuracyHa"] == pytest.approx(0.0016)
    assert created["entries"][0]["status"] == "completed"

    list_response = client.get(BENCHMARKS_API)
    assert list_response.status_code == 200
    listed = list_response.json()
    assert listed["total"] == 1
    assert listed["items"][0]["id"] == created["id"]

    get_response = client.get(f"/api/benchmarks/{created['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["entries"][0]["energy"] == -1.137

    update_response = client.patch(
        f"/api/benchmarks/{created['id']}",
        json={
            "name": "Updated benchmark",
            "campaignMetadata": {"status": "completed", "planned_item_count": 1},
            "entries": [{**created["entries"][0], "status": "paused"}],
        },
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["name"] == "Updated benchmark"
    assert updated["campaignMetadata"]["status"] == "completed"
    assert updated["entries"][0]["status"] == "paused"

    delete_response = client.delete(f"/api/benchmarks/{created['id']}")
    assert delete_response.status_code == 204

    missing_response = client.get(f"/api/benchmarks/{created['id']}")
    assert missing_response.status_code == 404


def test_benchmark_persists_aer_execution_settings(client: ASGISyncTestClient) -> None:
    payload = _benchmark_payload("GPU Aer benchmark")
    payload.update(
        {
            "selectedBackendMode": "aer_simulator",
            "shots": 256,
            "selectedAerMethod": "statevector",
            "selectedDevice": "GPU",
        }
    )

    response = client.post(BENCHMARKS_API, json=payload)

    assert response.status_code == 201
    created = response.json()
    assert created["shots"] == 256
    assert created["selectedAerMethod"] == "statevector"
    assert created["selectedDevice"] == "GPU"


def test_benchmark_list_is_paginated(client: ASGISyncTestClient) -> None:
    first = client.post(BENCHMARKS_API, json=_benchmark_payload("First benchmark")).json()
    second = client.post(BENCHMARKS_API, json=_benchmark_payload("Second benchmark")).json()

    response = client.get(f"{BENCHMARKS_API}?limit=1&offset=0")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] in {first["id"], second["id"]}


def test_campaign_registration_is_idempotent_and_persists_metadata(
    client: ASGISyncTestClient,
) -> None:
    payload = _campaign_registration_payload()

    first_response = client.post(f"{BENCHMARKS_API}/register", json=payload)
    assert first_response.status_code == 201
    first = first_response.json()
    assert first["campaignId"] == payload["campaignId"]
    assert first["registrationDigest"] == REGISTRATION_DIGEST
    assert first["campaignMetadata"]["schema_version"] == "campaign.v1"
    assert first["entries"][0]["status"] == "planned"

    second_response = client.post(f"{BENCHMARKS_API}/register", json=payload)
    assert second_response.status_code == 200
    assert second_response.json()["id"] == first["id"]

    changed = {**payload, "registrationDigest": "c" * 64}
    conflict_response = client.post(f"{BENCHMARKS_API}/register", json=changed)
    assert conflict_response.status_code == 409


def test_campaign_registration_rejects_unknown_run_id(
    client: ASGISyncTestClient,
) -> None:
    payload = _campaign_registration_payload()
    payload["campaignId"] = "campaign-with-unknown-run"
    payload["entries"][0]["status"] = "completed"
    payload["entries"][0]["runId"] = "44444444-4444-4444-4444-444444444444"

    response = client.post(f"{BENCHMARKS_API}/register", json=payload)

    assert response.status_code == 422
    assert "unknown run IDs" in response.json()["detail"]["message"]


def test_delete_benchmark_can_also_delete_associated_runs(
    client: ASGISyncTestClient,
    test_db,
    sample_molecule,
) -> None:
    run = Run(
        molecule_id=sample_molecule.id,
        status=RunStatus.COMPLETED,
        backend_target="statevector",
        config_json={"algorithm": "vqe", "backend_target": "statevector"},
    )
    test_db.add(run)
    test_db.commit()
    test_db.refresh(run)
    run_id = run.id

    payload = _benchmark_payload()
    payload["entries"][0]["moleculeId"] = str(sample_molecule.id)
    payload["entries"][0]["runId"] = str(run.id)
    created = client.post(BENCHMARKS_API, json=payload).json()

    delete_response = client.delete(f"/api/benchmarks/{created['id']}?delete_associated_runs=true")

    assert delete_response.status_code == 204
    test_db.expire_all()
    assert test_db.get(Run, run_id) is None
    assert client.get(f"/api/benchmarks/{created['id']}").status_code == 404


def test_delete_benchmark_skips_missing_associated_runs(
    client: ASGISyncTestClient,
) -> None:
    created = client.post(BENCHMARKS_API, json=_benchmark_payload()).json()

    delete_response = client.delete(f"/api/benchmarks/{created['id']}?delete_associated_runs=true")

    assert delete_response.status_code == 204
    assert client.get(f"/api/benchmarks/{created['id']}").status_code == 404


def test_create_benchmark_recovers_missing_selected_keys_and_custom_molecules_from_entries(
    client: ASGISyncTestClient,
) -> None:
    payload = _benchmark_payload("Recovered custom benchmark")
    payload["selectedMoleculeKeys"] = []
    payload["customMolecules"] = []
    payload["entries"][0]["id"] = "custom:33333333-3333-3333-3333-333333333333:vqe"
    payload["entries"][0]["preset"] = {
        "key": "custom:33333333-3333-3333-3333-333333333333",
        "name": "Recovered custom molecule",
        "atoms": [
            {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.0},
            {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.735},
        ],
        "basis": "sto-3g",
        "charge": 0,
        "multiplicity": 1,
        "formula": "H2",
        "description": "Recovered from persisted benchmark entries.",
        "references": {"hf": -1.116, "fci": -1.137, "source": "unknown"},
        "active_space": {"n_electrons": 2, "n_orbitals": 2},
    }
    payload["entries"][0]["moleculeId"] = "33333333-3333-3333-3333-333333333333"

    response = client.post(BENCHMARKS_API, json=payload)

    assert response.status_code == 201
    created = response.json()
    assert created["selectedMoleculeKeys"] == ["custom:33333333-3333-3333-3333-333333333333"]
    assert len(created["customMolecules"]) == 1
    assert created["customMolecules"][0]["id"] == "33333333-3333-3333-3333-333333333333"
    assert created["customMolecules"][0]["name"] == "Recovered custom molecule"
