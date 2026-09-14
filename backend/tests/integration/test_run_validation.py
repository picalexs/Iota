"""Integration coverage for run request validation rules."""

from __future__ import annotations

from app.models.molecule import Molecule
from sqlalchemy.orm import Session

from tests.conftest import ASGISyncTestClient

VALIDATE_CONFIG_API_PATH = "/api/validate/config"


class TestValidateRunRequest:
    """Tests for algorithm-aware validation using request.run payloads."""

    def test_validate_run_request_sqd_requires_paired_electron_counts(
        self, client: ASGISyncTestClient, sample_molecule: Molecule
    ):
        payload = {
            "molecule_id": str(sample_molecule.id),
            "run": {
                "molecule_id": str(sample_molecule.id),
                "algorithm": "sqd",
                "mode": "advanced",
                "backend_target": "statevector",
                "advanced_config": {
                    "algorithm": "sqd",
                    "samples_per_batch": 64,
                    "num_batches": 2,
                    "max_iterations": 10,
                    "num_elec_a": 1,
                },
            },
        }

        response = client.post(VALIDATE_CONFIG_API_PATH, json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any(
            err["field"] == "advanced_config.num_elec_a|num_elec_b"
            and err["code"] == "missing_required"
            for err in data["errors"]
        )

    def test_validate_run_request_sqd_rejects_active_space_mismatch(
        self, client: ASGISyncTestClient, sample_molecule: Molecule
    ):
        payload = {
            "molecule_id": str(sample_molecule.id),
            "run": {
                "molecule_id": str(sample_molecule.id),
                "algorithm": "sqd",
                "mode": "advanced",
                "backend_target": "statevector",
                "advanced_config": {
                    "algorithm": "sqd",
                    "samples_per_batch": 64,
                    "num_batches": 2,
                    "max_iterations": 10,
                    "num_elec_a": 2,
                    "num_elec_b": 1,
                },
            },
        }

        response = client.post(VALIDATE_CONFIG_API_PATH, json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any(
            err["field"] == "advanced_config.num_elec_a|num_elec_b"
            and err["code"] == "incompatible_backend"
            for err in data["errors"]
        )

    def test_validate_run_request_kqd_exact_warns_about_trotter_steps(
        self, client: ASGISyncTestClient, sample_molecule: Molecule
    ):
        payload = {
            "molecule_id": str(sample_molecule.id),
            "run": {
                "molecule_id": str(sample_molecule.id),
                "algorithm": "kqd",
                "mode": "advanced",
                "backend_target": "statevector",
                "advanced_config": {
                    "algorithm": "kqd",
                    "krylov_dim": 3,
                    "time_step": 0.1,
                    "evolution_method": "exact",
                    "trotter_steps": 4,
                },
            },
        }

        response = client.post(VALIDATE_CONFIG_API_PATH, json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert any("trotter_steps is ignored" in warning for warning in data["warnings"])

    def test_validate_run_request_warns_for_midrange_active_space(
        self, client: ASGISyncTestClient, test_db: Session, sample_molecule: Molecule
    ):
        sample_molecule.active_space = {"n_electrons": 2, "n_orbitals": 10}
        test_db.commit()
        payload = {
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

        response = client.post(VALIDATE_CONFIG_API_PATH, json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert any(
            "sector and sampler paths may be slower" in warning for warning in data["warnings"]
        )

    def test_validate_run_request_rejects_non_singlet_multiplicity(
        self, client: ASGISyncTestClient, test_db: Session, sample_molecule: Molecule
    ):
        sample_molecule.multiplicity = 2
        test_db.commit()

        payload = {
            "molecule_id": str(sample_molecule.id),
            "run": {
                "molecule_id": str(sample_molecule.id),
                "algorithm": "kqd",
                "mode": "advanced",
                "backend_target": "statevector",
                "advanced_config": {
                    "algorithm": "kqd",
                    "krylov_dim": 3,
                    "time_step": 0.1,
                    "evolution_method": "exact",
                    "trotter_steps": 1,
                },
            },
        }

        response = client.post(VALIDATE_CONFIG_API_PATH, json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any(
            err["field"] == "molecule.multiplicity" and err["code"] == "incompatible_backend"
            for err in data["errors"]
        )

    def test_validate_run_request_rejects_odd_active_space_electrons(
        self, client: ASGISyncTestClient, test_db: Session, sample_molecule: Molecule
    ):
        sample_molecule.active_space = {"n_electrons": 3, "n_orbitals": 2}
        test_db.commit()

        payload = {
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

        response = client.post(VALIDATE_CONFIG_API_PATH, json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any(
            err["field"] == "molecule.active_space.n_electrons"
            and err["code"] == "incompatible_backend"
            for err in data["errors"]
        )

    def test_validate_run_request_allows_large_vqe_active_space_with_warning(
        self, client: ASGISyncTestClient, test_db: Session, sample_molecule: Molecule
    ):
        sample_molecule.active_space = {"n_electrons": 2, "n_orbitals": 15}
        test_db.commit()
        payload = {
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

        response = client.post(VALIDATE_CONFIG_API_PATH, json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["errors"] == []
        assert any("above 12" in warning for warning in data["warnings"])

    def test_validate_run_request_allows_large_kqd_statevector_active_space(
        self, client: ASGISyncTestClient, test_db: Session, sample_molecule: Molecule
    ):
        sample_molecule.active_space = {"n_electrons": 2, "n_orbitals": 7}
        test_db.commit()
        payload = {
            "molecule_id": str(sample_molecule.id),
            "run": {
                "molecule_id": str(sample_molecule.id),
                "algorithm": "kqd",
                "mode": "advanced",
                "backend_target": "statevector",
                "advanced_config": {
                    "algorithm": "kqd",
                    "krylov_dim": 3,
                    "time_step": 0.1,
                    "evolution_method": "exact",
                    "trotter_steps": 1,
                },
            },
        }

        response = client.post(VALIDATE_CONFIG_API_PATH, json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["errors"] == []
        assert any("fixed-particle-sector matrix-free" in warning for warning in data["warnings"])

    def test_validate_run_request_allows_large_qse_active_space(
        self, client: ASGISyncTestClient, test_db: Session, sample_molecule: Molecule
    ):
        sample_molecule.active_space = {"n_electrons": 2, "n_orbitals": 7}
        test_db.commit()
        payload = {
            "molecule_id": str(sample_molecule.id),
            "run": {
                "molecule_id": str(sample_molecule.id),
                "algorithm": "qse",
                "mode": "advanced",
                "backend_target": "statevector",
                "advanced_config": {
                    "algorithm": "qse",
                    "reference_method": "hf",
                    "excitation_level": "singles_doubles",
                    "max_subspace_dim": 8,
                },
            },
        }

        response = client.post(VALIDATE_CONFIG_API_PATH, json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert not any(err["field"] == "molecule.active_space.n_orbitals" for err in data["errors"])

    def test_validate_run_request_allows_large_skqd_active_space(
        self, client: ASGISyncTestClient, test_db: Session, sample_molecule: Molecule
    ):
        sample_molecule.active_space = {"n_electrons": 2, "n_orbitals": 7}
        test_db.commit()
        payload = {
            "molecule_id": str(sample_molecule.id),
            "run": {
                "molecule_id": str(sample_molecule.id),
                "algorithm": "skqd",
                "mode": "advanced",
                "backend_target": "statevector",
                "advanced_config": {
                    "algorithm": "skqd",
                    "samples_per_state": 128,
                    "base_sampling_options": {
                    },
                    "krylov_extension_dim": 8,
                },
            },
        }

        response = client.post(VALIDATE_CONFIG_API_PATH, json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert not any(err["field"] == "molecule.active_space.n_orbitals" for err in data["errors"])

    def test_validate_run_request_kqd_rejects_excessive_krylov_dim(
        self, client: ASGISyncTestClient, sample_molecule: Molecule
    ):
        payload = {
            "molecule_id": str(sample_molecule.id),
            "run": {
                "molecule_id": str(sample_molecule.id),
                "algorithm": "kqd",
                "mode": "advanced",
                "backend_target": "statevector",
                "advanced_config": {
                    "algorithm": "kqd",
                    "krylov_dim": 200,
                    "time_step": 0.1,
                    "evolution_method": "trotter",
                    "trotter_steps": 1,
                },
            },
        }

        response = client.post(VALIDATE_CONFIG_API_PATH, json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any(
            err["field"] == "advanced_config.krylov_dim" and err["code"] == "invalid_range"
            for err in data["errors"]
        )

    def test_validate_run_request_qfd_rejects_excessive_time_points(
        self, client: ASGISyncTestClient, sample_molecule: Molecule
    ):
        payload = {
            "molecule_id": str(sample_molecule.id),
            "run": {
                "molecule_id": str(sample_molecule.id),
                "algorithm": "qfd",
                "mode": "advanced",
                "backend_target": "statevector",
                "advanced_config": {
                    "algorithm": "qfd",
                    "num_time_points": 300,
                    "max_time": 1.0,
                    "time_grid_type": "linear",
                },
            },
        }

        response = client.post(VALIDATE_CONFIG_API_PATH, json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any(
            err["field"] == "advanced_config.num_time_points" and err["code"] == "invalid_range"
            for err in data["errors"]
        )

    def test_validate_run_request_qse_rejects_excessive_subspace_dim(
        self, client: ASGISyncTestClient, sample_molecule: Molecule
    ):
        payload = {
            "molecule_id": str(sample_molecule.id),
            "run": {
                "molecule_id": str(sample_molecule.id),
                "algorithm": "qse",
                "mode": "advanced",
                "backend_target": "statevector",
                "advanced_config": {
                    "algorithm": "qse",
                    "reference_method": "vqe",
                    "excitation_level": "singles",
                    "max_subspace_dim": 200,
                    "regularization": 1e-6,
                },
            },
        }

        response = client.post(VALIDATE_CONFIG_API_PATH, json=payload)

        assert response.status_code == 422
        data = response.json()
        assert data["detail"]["code"] == "VALIDATION_ERROR"
        assert data["detail"]["field"] == "body.run.advanced_config.qse.max_subspace_dim"

    def test_validate_run_request_skqd_requires_paired_base_electron_counts(
        self, client: ASGISyncTestClient, sample_molecule: Molecule
    ):
        payload = {
            "molecule_id": str(sample_molecule.id),
            "run": {
                "molecule_id": str(sample_molecule.id),
                "algorithm": "skqd",
                "mode": "advanced",
                "backend_target": "statevector",
                "advanced_config": {
                    "algorithm": "skqd",
                    "samples_per_state": 64,
                    "base_sampling_options": {
                        "num_elec_a": 1,
                    },
                    "krylov_extension_dim": 3,
                },
            },
        }

        response = client.post(VALIDATE_CONFIG_API_PATH, json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any(
            err["field"] == "advanced_config.base_sampling_options.num_elec_a|num_elec_b"
            and err["code"] == "missing_required"
            for err in data["errors"]
        )

    def test_validate_run_request_skqd_rejects_active_space_mismatch(
        self, client: ASGISyncTestClient, sample_molecule: Molecule
    ):
        payload = {
            "molecule_id": str(sample_molecule.id),
            "run": {
                "molecule_id": str(sample_molecule.id),
                "algorithm": "skqd",
                "mode": "advanced",
                "backend_target": "statevector",
                "advanced_config": {
                    "algorithm": "skqd",
                    "samples_per_state": 64,
                    "base_sampling_options": {
                        "num_elec_a": 2,
                        "num_elec_b": 1,
                    },
                    "krylov_extension_dim": 3,
                },
            },
        }

        response = client.post(VALIDATE_CONFIG_API_PATH, json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any(
            err["field"] == "advanced_config.base_sampling_options.num_elec_a|num_elec_b"
            and err["code"] == "incompatible_backend"
            for err in data["errors"]
        )

    def test_validate_run_request_sqd_accepts_supported_tuning_fields(
        self, client: ASGISyncTestClient, sample_molecule: Molecule
    ):
        payload = {
            "molecule_id": str(sample_molecule.id),
            "run": {
                "molecule_id": str(sample_molecule.id),
                "algorithm": "sqd",
                "mode": "advanced",
                "backend_target": "statevector",
                "advanced_config": {
                    "algorithm": "sqd",
                    "samples_per_batch": 64,
                    "num_batches": 2,
                    "max_iterations": 10,
                    "carryover_threshold": 0.2,
                    "max_dim": 32,
                    "sci_solver_options": {"max_cycle": 100},
                    "symmetrize_spin": True,
                },
            },
        }

        response = client.post(VALIDATE_CONFIG_API_PATH, json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert not any("carryover_threshold" in warning for warning in data["warnings"])
        assert not any("symmetrize_spin" in warning for warning in data["warnings"])
        assert not any("max_dim" in warning for warning in data["warnings"])
        assert not any("sci_solver_options" in warning for warning in data["warnings"])

    def test_validate_run_request_skqd_accepts_supported_base_tuning_fields(
        self, client: ASGISyncTestClient, sample_molecule: Molecule
    ):
        payload = {
            "molecule_id": str(sample_molecule.id),
            "run": {
                "molecule_id": str(sample_molecule.id),
                "algorithm": "skqd",
                "mode": "advanced",
                "backend_target": "statevector",
                "advanced_config": {
                    "algorithm": "skqd",
                    "samples_per_state": 64,
                    "base_sampling_options": {
                        "max_dim": 32,
                        "sci_solver_options": {"max_cycle": 100},
                        "symmetrize_spin": False,
                    },
                    "krylov_extension_dim": 3,
                },
            },
        }

        response = client.post(VALIDATE_CONFIG_API_PATH, json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert not any("carryover_threshold" in warning for warning in data["warnings"])
        assert not any("symmetrize_spin" in warning for warning in data["warnings"])
        assert not any("max_dim" in warning for warning in data["warnings"])
        assert not any("sci_solver_options" in warning for warning in data["warnings"])

    def test_validate_run_request_sqd_rejects_incompatible_spin_symmetrization(
        self, client: ASGISyncTestClient, sample_molecule: Molecule
    ):
        payload = {
            "molecule_id": str(sample_molecule.id),
            "run": {
                "molecule_id": str(sample_molecule.id),
                "algorithm": "sqd",
                "mode": "advanced",
                "backend_target": "statevector",
                "advanced_config": {
                    "algorithm": "sqd",
                    "samples_per_batch": 64,
                    "num_batches": 2,
                    "max_iterations": 10,
                    "num_elec_a": 2,
                    "num_elec_b": 0,
                    "symmetrize_spin": True,
                },
            },
        }

        response = client.post(VALIDATE_CONFIG_API_PATH, json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any(
            err["field"] == "advanced_config.symmetrize_spin"
            and "equal alpha and beta electron counts" in err["message"]
            for err in data["errors"]
        )

    def test_validate_run_request_skqd_rejects_spin_resolved_symmetrize_mismatch(
        self, client: ASGISyncTestClient, sample_molecule: Molecule
    ):
        payload = {
            "molecule_id": str(sample_molecule.id),
            "run": {
                "molecule_id": str(sample_molecule.id),
                "algorithm": "skqd",
                "mode": "advanced",
                "backend_target": "statevector",
                "advanced_config": {
                    "algorithm": "skqd",
                    "samples_per_state": 64,
                    "base_sampling_options": {
                        "symmetrize_spin": True,
                        "max_dim": [16, 32],
                    },
                    "krylov_extension_dim": 3,
                },
            },
        }

        response = client.post(VALIDATE_CONFIG_API_PATH, json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any(
            err["field"] == "advanced_config.base_sampling_options.max_dim"
            and "identical alpha and beta max_dim" in err["message"]
            for err in data["errors"]
        )
