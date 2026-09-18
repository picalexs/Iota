"""Integration tests for the run config validation endpoint."""

from __future__ import annotations

from uuid import uuid4

import pytest
from app.api.v1.endpoints import validate as validate_endpoint
from app.models.molecule import Molecule
from app.schemas.run import RunValidationRequest, RunValidationResponse
from starlette.requests import Request

from tests.conftest import ASGISyncTestClient

VALIDATE_CONFIG_API_PATH = "/api/validate/config"


def _base_payload(sample_molecule: Molecule) -> dict[str, object]:
    return {
        "molecule_id": str(sample_molecule.id),
        "run": {
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
        },
    }


def test_validate_config_happy_path_returns_estimate(
    client: ASGISyncTestClient,
    sample_molecule: Molecule,
):
    response = client.post(VALIDATE_CONFIG_API_PATH, json=_base_payload(sample_molecule))

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["errors"] == []
    assert data["warnings"] == []
    assert data["estimate"] is not None
    assert data["estimate"]["source"] in {"config_projection", "heuristic", "telemetry"}


def test_validate_config_rejects_automatic_active_space_beyond_sto3g_capacity(
    client: ASGISyncTestClient,
    test_db,
    sample_molecule: Molecule,
):
    sample_molecule.atoms = [
        {"symbol": "F", "x": -0.7, "y": 0.0, "z": 0.0},
        {"symbol": "O", "x": 0.7, "y": 0.0, "z": 0.0},
        {"symbol": "H", "x": 1.0, "y": 0.6, "z": -0.6},
    ]
    sample_molecule.active_space = {
        "n_electrons": 8,
        "n_orbitals": 8,
        "method": "automatic_frontier_estimate",
    }
    test_db.commit()

    response = client.post(VALIDATE_CONFIG_API_PATH, json=_base_payload(sample_molecule))

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    error = next(
        error
        for error in data["errors"]
        if error["field"] == "molecule.active_space.n_orbitals"
    )
    assert "maximum 6" in error["message"]


def test_validate_config_rejects_malformed_request(
    client: ASGISyncTestClient,
):
    response = client.post(
        VALIDATE_CONFIG_API_PATH,
        json={"molecule_id": "not-a-uuid", "run": {}},
    )

    assert response.status_code == 422
    data = response.json()
    assert data["detail"]["code"] == "VALIDATION_ERROR"
    assert "molecule_id" in data["detail"]["field"]


def test_validate_config_reports_missing_molecule(
    client: ASGISyncTestClient,
    sample_molecule: Molecule,
):
    payload = _base_payload(sample_molecule)
    missing_id = str(uuid4())
    payload["molecule_id"] = missing_id

    response = client.post(VALIDATE_CONFIG_API_PATH, json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert data["estimate"] is None
    assert data["errors"][0]["field"] == "molecule_id"
    assert missing_id in data["errors"][0]["message"]


def test_validate_config_backend_derived_aer_requires_local_operator_token(
    client: ASGISyncTestClient,
    sample_molecule: Molecule,
):
    payload = _base_payload(sample_molecule)
    run = payload["run"]
    assert isinstance(run, dict)
    run["backend_target"] = "aer_simulator"
    run["noise_profile"] = {
        "source": "backend_derived",
        "reference_backend": "ibm_brisbane",
    }

    response = client.post(
        VALIDATE_CONFIG_API_PATH,
        headers={"X-Local-Operator-Token": "wrong-token"},
        json=payload,
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "FORBIDDEN"


def test_validate_config_warns_large_kqd_ibm_projected_matrix_run(
    client: ASGISyncTestClient,
    monkeypatch: pytest.MonkeyPatch,
    test_db,
    sample_molecule: Molecule,
):
    sample_molecule.active_space = {"n_electrons": 2, "n_orbitals": 7}
    test_db.commit()
    payload = {
        "molecule_id": str(sample_molecule.id),
        "run": {
            "molecule_id": str(sample_molecule.id),
            "algorithm": "kqd",
            "mode": "advanced",
            "backend_target": "ibm_runtime",
            "ibm_runtime_confirmed": True,
            "backend_options": {
                "selection_policy": "manual",
                "backend_name": "ibm_brisbane",
                "credential_profile_id": str(uuid4()),
            },
            "advanced_config": {
                "algorithm": "kqd",
                "krylov_dim": 4,
                "time_step": 0.1,
                "evolution_method": "exact",
                "trotter_steps": 1,
            },
        },
    }

    monkeypatch.setattr(
        "app.services.credential_profiles.IbmCredentialProfileService.resolve_credentials",
        lambda self, credential_profile_id: {"credential_profile_id": credential_profile_id},
    )

    response = client.post(VALIDATE_CONFIG_API_PATH, json=payload)

    assert response.status_code == 200
    data = response.json()
    assert not any(
        error["field"] == "molecule.active_space.n_orbitals" for error in data["errors"]
    )
    assert any(
        "IBM Runtime KQD/QFD projected-matrix runs are limited" in warning
        and "EXCLUDED" in warning
        for warning in data["warnings"]
    )


@pytest.mark.asyncio
async def test_validate_config_runs_service_in_threadpool(
    monkeypatch: pytest.MonkeyPatch,
    test_db,
    sample_molecule: Molecule,
):
    payload = RunValidationRequest.model_validate(_base_payload(sample_molecule))
    expected = RunValidationResponse(valid=True, errors=[], warnings=[], estimate=None)
    captured: dict[str, object] = {}

    async def fake_run_in_threadpool(func, *args):
        captured["func"] = func
        captured["args"] = args
        return expected

    monkeypatch.setattr(validate_endpoint, "run_in_threadpool", fake_run_in_threadpool)

    request = Request({"type": "http", "method": "POST", "path": VALIDATE_CONFIG_API_PATH})

    response = await validate_endpoint.validate_config(payload, test_db, request)

    assert response is expected
    assert captured["func"] is validate_endpoint._validate_config_for_request
    assert captured["args"] == (test_db, payload)


def test_validate_config_allows_large_vqe_active_space_with_warning(
    client: ASGISyncTestClient,
    test_db,
    sample_molecule: Molecule,
):
    sample_molecule.active_space = {"n_electrons": 2, "n_orbitals": 15}
    test_db.commit()

    response = client.post(VALIDATE_CONFIG_API_PATH, json=_base_payload(sample_molecule))

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["errors"] == []
    assert any("above 12" in warning for warning in data["warnings"])


def test_validate_config_allows_large_kqd_statevector_active_space(
    client: ASGISyncTestClient,
    test_db,
    sample_molecule: Molecule,
):
    sample_molecule.active_space = {"n_electrons": 2, "n_orbitals": 7}
    test_db.commit()
    payload = _base_payload(sample_molecule)
    run = payload["run"]
    assert isinstance(run, dict)
    run["algorithm"] = "kqd"
    run["advanced_config"] = {
        "algorithm": "kqd",
        "krylov_dim": 4,
        "time_step": 0.1,
        "evolution_method": "exact",
        "trotter_steps": 1,
    }

    response = client.post(VALIDATE_CONFIG_API_PATH, json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["errors"] == []
    assert any("fixed-particle-sector matrix-free" in warning for warning in data["warnings"])


def test_validate_config_rejects_large_aer_kqd_projected_dimension_above_cap(
    client: ASGISyncTestClient,
    test_db,
    sample_molecule: Molecule,
):
    sample_molecule.active_space = {"n_electrons": 8, "n_orbitals": 8}
    test_db.commit()
    payload = _base_payload(sample_molecule)
    run = payload["run"]
    assert isinstance(run, dict)
    run["algorithm"] = "kqd"
    run["backend_target"] = "aer_simulator"
    run["advanced_config"] = {
        "algorithm": "kqd",
        "krylov_dim": 9,
        "time_step": 0.1,
        "evolution_method": "exact",
        "trotter_steps": 1,
    }

    response = client.post(VALIDATE_CONFIG_API_PATH, json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert any(error["field"] == "advanced_config.krylov_dim" for error in data["errors"])


def test_validate_config_allows_large_qfd_statevector_active_space(
    client: ASGISyncTestClient,
    test_db,
    sample_molecule: Molecule,
):
    sample_molecule.active_space = {"n_electrons": 8, "n_orbitals": 8}
    test_db.commit()
    payload = _base_payload(sample_molecule)
    run = payload["run"]
    assert isinstance(run, dict)
    run["algorithm"] = "qfd"
    run["advanced_config"] = {
        "algorithm": "qfd",
        "num_time_points": 8,
        "max_time": 0.4,
        "time_grid_type": "linear",
    }

    response = client.post(VALIDATE_CONFIG_API_PATH, json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["errors"] == []
    assert any("fixed-particle-sector matrix-free" in warning for warning in data["warnings"])


def test_validate_config_allows_large_qse_active_space(
    client: ASGISyncTestClient,
    test_db,
    sample_molecule: Molecule,
):
    sample_molecule.active_space = {"n_electrons": 2, "n_orbitals": 7}
    test_db.commit()
    payload = _base_payload(sample_molecule)
    run = payload["run"]
    assert isinstance(run, dict)
    run["algorithm"] = "qse"
    run["advanced_config"] = {
        "algorithm": "qse",
        "reference_method": "hf",
        "excitation_level": "singles_doubles",
        "max_subspace_dim": 8,
    }

    response = client.post(VALIDATE_CONFIG_API_PATH, json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert not any(error["field"] == "molecule.active_space.n_orbitals" for error in data["errors"])


def test_validate_config_rejects_large_qse_vqe_reference(
    client: ASGISyncTestClient,
    test_db,
    sample_molecule: Molecule,
):
    sample_molecule.active_space = {"n_electrons": 8, "n_orbitals": 8}
    test_db.commit()
    payload = _base_payload(sample_molecule)
    run = payload["run"]
    assert isinstance(run, dict)
    run["algorithm"] = "qse"
    run["advanced_config"] = {
        "algorithm": "qse",
        "reference_method": "vqe",
        "excitation_level": "singles_doubles",
        "max_subspace_dim": 8,
        "vqe_reference_max_iterations": 160,
        "vqe_reference_reps": 2,
    }

    response = client.post(VALIDATE_CONFIG_API_PATH, json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert any(error["field"] == "advanced_config.reference_method" for error in data["errors"])


def test_validate_config_allows_large_skqd_active_space(
    client: ASGISyncTestClient,
    test_db,
    sample_molecule: Molecule,
):
    sample_molecule.active_space = {"n_electrons": 2, "n_orbitals": 7}
    test_db.commit()
    payload = _base_payload(sample_molecule)
    run = payload["run"]
    assert isinstance(run, dict)
    run["algorithm"] = "skqd"
    run["advanced_config"] = {
        "algorithm": "skqd",
        "samples_per_state": 512,
        "base_sampling_options": {
            "num_elec_a": 1,
            "num_elec_b": 1,
        },
        "krylov_extension_dim": 8,
    }

    response = client.post(VALIDATE_CONFIG_API_PATH, json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert not any(error["field"] == "molecule.active_space.n_orbitals" for error in data["errors"])
