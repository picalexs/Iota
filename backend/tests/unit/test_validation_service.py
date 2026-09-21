"""Unit tests for algorithm-aware validation service behavior."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from app.models.enums import BackendTarget, RunAlgorithm, RunMode
from app.schemas.run import (
    BackendSelectionPolicy,
    CustomNoisePreset,
    KQDAdvancedConfig,
    NoiseModelSource,
    QFDAdvancedConfig,
    QSEAdvancedConfig,
    RunCreate,
    RunValidationRequest,
    SKQDAdvancedConfig,
    SKQDSamplingParams,
    ValidationErrorCode,
)
from app.services.validation import algorithm_policies
from app.services.validation_service import validate_run_request, validate_run_validation_request
from pydantic import ValidationError
from sqlalchemy.orm import Session

KRYLOV_DIM_FIELD = "advanced_config.krylov_dim"


def _make_sqd_run_create(**overrides: object) -> RunCreate:
    payload: dict[str, Any] = {
        "molecule_id": uuid4(),
        "algorithm": RunAlgorithm.SQD,
        "mode": RunMode.ADVANCED,
        "backend_target": BackendTarget.STATEVECTOR,
        "advanced_config": {
            "algorithm": RunAlgorithm.SQD,
            "samples_per_batch": 128,
            "num_batches": 4,
            "max_iterations": 25,
        },
    }
    payload.update(overrides)
    return RunCreate.model_validate(payload)


def _make_kqd_run_create(**overrides: object) -> RunCreate:
    payload: dict[str, Any] = {
        "molecule_id": uuid4(),
        "algorithm": RunAlgorithm.KQD,
        "mode": RunMode.ADVANCED,
        "backend_target": BackendTarget.STATEVECTOR,
        "advanced_config": {
            "algorithm": RunAlgorithm.KQD,
            "krylov_dim": 4,
            "time_step": 0.2,
            "evolution_method": "exact",
            "trotter_steps": 3,
        },
    }
    payload.update(overrides)
    return RunCreate.model_validate(payload)


def test_run_create_new_contract_detects_basis_set_override_shape() -> None:
    with pytest.raises(ValidationError):
        RunCreate.model_validate({"molecule_id": uuid4(), "basis_set_override": "6-31g*"})


def test_run_create_backend_options_defaults_are_stable() -> None:
    run = _make_kqd_run_create()

    assert run.backend_options.selection_policy == BackendSelectionPolicy.MANUAL
    assert run.backend_options.backend_name is None
    assert run.backend_options.shots == 4096
    assert run.backend_options.optimization_level == 1
    assert run.backend_options.seed_simulator is None
    assert run.backend_options.seed_transpiler is None
    assert run.backend_options.aer_method == "automatic"
    assert run.noise_profile is None


def test_validate_run_request_accepts_gpu_aer_with_explicit_statevector() -> None:
    run = _make_kqd_run_create(
        backend_target=BackendTarget.AER_SIMULATOR,
        backend_options={"device": "GPU", "aer_method": "statevector"},
    )

    response = validate_run_request(run)

    assert not any(error.field == "backend_options.aer_method" for error in response.errors)


def test_validate_run_request_rejects_gpu_aer_automatic_method() -> None:
    run = _make_kqd_run_create(
        backend_target=BackendTarget.AER_SIMULATOR,
        backend_options={"device": "GPU"},
    )

    response = validate_run_request(run)

    assert response.valid is False
    assert any(error.field == "backend_options.aer_method" for error in response.errors)


def test_validate_run_request_rejects_gpu_shot_batching_without_gpu() -> None:
    run = _make_kqd_run_create(
        backend_target=BackendTarget.AER_SIMULATOR,
        backend_options={
            "aer_method": "statevector",
            "batched_shots_gpu": True,
        },
    )

    response = validate_run_request(run)

    assert response.valid is False
    assert any(error.field == "backend_options.batched_shots_gpu" for error in response.errors)


def test_validate_run_request_rejects_incompatible_aer_parallel_options() -> None:
    run = _make_kqd_run_create(
        backend_target=BackendTarget.AER_SIMULATOR,
        backend_options={
            "aer_method": "statevector",
            "max_parallel_experiments": 2,
            "max_parallel_shots": 2,
        },
    )

    response = validate_run_request(run)

    assert response.valid is False
    assert any(error.field == "backend_options.max_parallel_shots" for error in response.errors)


def test_validate_run_request_rejects_gpu_batching_with_custatevec() -> None:
    run = _make_kqd_run_create(
        backend_target=BackendTarget.AER_SIMULATOR,
        backend_options={
            "device": "GPU",
            "aer_method": "statevector",
            "batched_shots_gpu": True,
            "cuStateVec_enable": True,
        },
    )

    response = validate_run_request(run)

    assert response.valid is False
    assert any(error.field == "backend_options.cuStateVec_enable" for error in response.errors)


def test_validate_run_request_rejects_shot_branching_with_automatic_method() -> None:
    run = _make_kqd_run_create(
        backend_target=BackendTarget.AER_SIMULATOR,
        backend_options={"shot_branching_enable": True},
    )

    response = validate_run_request(run)

    assert response.valid is False
    assert any(error.field == "backend_options.shot_branching_enable" for error in response.errors)


def test_validate_run_request_rejects_blocking_with_mps_method() -> None:
    run = _make_kqd_run_create(
        backend_target=BackendTarget.AER_SIMULATOR,
        backend_options={
            "aer_method": "matrix_product_state",
            "blocking_enable": True,
        },
    )

    response = validate_run_request(run)

    assert response.valid is False
    assert any(error.field == "backend_options.blocking_enable" for error in response.errors)


def test_validate_run_request_rejects_aer_device_options_for_ibm_target() -> None:
    run = _make_kqd_run_create(
        backend_target=BackendTarget.IBM_RUNTIME,
        backend_options={"device": "GPU", "backend_name": "ibm_brisbane"},
        advanced_config={
            "algorithm": RunAlgorithm.KQD,
            "krylov_dim": 4,
            "time_step": 0.2,
            "evolution_method": "trotter",
            "trotter_steps": 2,
        },
        ibm_runtime_confirmed=True,
    )

    response = validate_run_request(run, ibm_credentials_available=True)

    assert any(error.field == "backend_options.device" for error in response.errors)


def test_validate_run_request_accepts_kqd_aer_without_noise_profile() -> None:
    run = _make_kqd_run_create(
        backend_target=BackendTarget.AER_SIMULATOR,
    )

    response = validate_run_request(run)

    assert response.valid is True
    assert response.errors == []
    assert any("AerSimulator" in warning for warning in response.warnings)
    assert any("local exact matrix evolution" in warning for warning in response.warnings)
    assert any("trotter_steps is ignored" in warning for warning in response.warnings)
    assert not any("synthesizes Pauli-evolution circuits" in warning for warning in response.warnings)


def test_validate_run_request_allows_large_kqd_ideal_aer_sector_path() -> None:
    run = _make_kqd_run_create(
        backend_target=BackendTarget.AER_SIMULATOR,
    )

    response = validate_run_request(run, molecule_active_space_n_orbitals=7)

    assert response.valid is True
    assert not response.errors
    assert any("fixed-particle-sector matrix-free path" in warning for warning in response.warnings)


def test_validate_run_request_accepts_kqd_aer_noise_profile() -> None:
    run = _make_kqd_run_create(
        backend_target=BackendTarget.AER_SIMULATOR,
        advanced_config={
            "algorithm": RunAlgorithm.KQD,
            "krylov_dim": 4,
            "time_step": 0.2,
            "evolution_method": "trotter",
            "trotter_steps": 4,
        },
        noise_profile={
            "source": NoiseModelSource.CUSTOM_PRESET,
            "preset": CustomNoisePreset.DEPOLARIZING_CX,
            "strength": 0.01,
        },
    )

    response = validate_run_request(run)

    assert response.valid is True
    assert any("noisy Aer execution measures projected" in warning for warning in response.warnings)


def test_validate_run_request_rejects_exact_kqd_for_noisy_aer() -> None:
    run = _make_kqd_run_create(
        backend_target=BackendTarget.AER_SIMULATOR,
        noise_profile={
            "source": NoiseModelSource.CUSTOM_PRESET,
            "preset": CustomNoisePreset.DEPOLARIZING_CX,
            "strength": 0.01,
        },
    )

    response = validate_run_request(run)

    assert response.valid is False
    assert any(
        error.field == "advanced_config.evolution_method"
        and error.code == ValidationErrorCode.UNSUPPORTED_OPTION
        for error in response.errors
    )


def test_validate_run_request_allows_qse_for_noisy_aer_measured_path() -> None:
    run = RunCreate.model_validate(
        {
            "molecule_id": uuid4(),
            "algorithm": RunAlgorithm.QSE,
            "mode": RunMode.ADVANCED,
            "backend_target": BackendTarget.AER_SIMULATOR,
            "advanced_config": {
                "algorithm": RunAlgorithm.QSE,
                "reference_method": "hf",
                "excitation_level": "singles",
                "max_subspace_dim": 4,
            },
            "noise_profile": {
                "source": NoiseModelSource.CUSTOM_PRESET,
                "preset": CustomNoisePreset.DEPOLARIZING_CX,
                "strength": 0.01,
            },
        }
    )

    response = validate_run_request(
        run,
        molecule_active_space_n_electrons=2,
        molecule_active_space_n_orbitals=2,
    )

    assert response.valid is True
    assert not any(
        error.code == ValidationErrorCode.UNSUPPORTED_OPTION
        and "Noisy QSE measured matrix elements are not implemented" in error.message
        for error in response.errors
    )
    assert any("measured QSE" in warning for warning in response.warnings)


def test_validate_run_request_warns_large_kqd_noisy_aer_projected_matrix_path() -> None:
    run = _make_kqd_run_create(
        backend_target=BackendTarget.AER_SIMULATOR,
        noise_profile={
            "source": NoiseModelSource.CUSTOM_PRESET,
            "preset": CustomNoisePreset.DEPOLARIZING_CX,
            "strength": 0.01,
        },
    )

    response = validate_run_request(run, molecule_active_space_n_orbitals=7)

    assert not any(
        error.field == "molecule.active_space.n_orbitals" for error in response.errors
    )
    assert any(
        "Noisy Aer KQD/QFD projected-matrix runs are limited" in warning
        and "EXCLUDED" in warning
        for warning in response.warnings
    )


def test_validate_run_request_rejects_large_kqd_aer_noise_profile_over_cap() -> None:
    run = _make_kqd_run_create(
        backend_target=BackendTarget.AER_SIMULATOR,
        advanced_config={
            "algorithm": RunAlgorithm.KQD,
            "krylov_dim": 9,
            "time_step": 0.2,
            "evolution_method": "exact",
            "trotter_steps": 1,
        },
        noise_profile={
            "source": NoiseModelSource.CUSTOM_PRESET,
            "preset": CustomNoisePreset.DEPOLARIZING_CX,
            "strength": 0.01,
        },
    )

    response = validate_run_request(run)

    assert response.valid is False
    assert any(error.field == KRYLOV_DIM_FIELD for error in response.errors)


def test_validate_run_request_warns_large_kqd_ibm_projected_matrix_path() -> None:
    run = _make_kqd_run_create(
        backend_target=BackendTarget.IBM_RUNTIME,
        backend_options={"backend_name": "ibm_brisbane"},
        ibm_runtime_confirmed=True,
    )

    response = validate_run_request(
        run,
        molecule_active_space_n_orbitals=7,
        ibm_credentials_available=True,
    )

    assert not any(
        error.field == "molecule.active_space.n_orbitals" for error in response.errors
    )
    assert any(
        "IBM Runtime KQD/QFD projected-matrix runs are limited" in warning
        and "EXCLUDED" in warning
        for warning in response.warnings
    )


def test_validate_run_request_rejects_kqd_aer_density_matrix_method() -> None:
    run = _make_kqd_run_create(
        backend_target=BackendTarget.AER_SIMULATOR,
        backend_options={"aer_method": "density_matrix"},
    )

    response = validate_run_request(run)

    assert response.valid is False
    assert any(error.field == "backend_options.aer_method" for error in response.errors)


def test_validate_run_request_accepts_kqd_ibm_matrix_elements() -> None:
    run = _make_kqd_run_create(
        backend_target=BackendTarget.IBM_RUNTIME,
        backend_options={"backend_name": "ibm_brisbane"},
        advanced_config={
            "algorithm": RunAlgorithm.KQD,
            "krylov_dim": 4,
            "time_step": 0.2,
            "evolution_method": "trotter",
            "trotter_steps": 2,
        },
        ibm_runtime_confirmed=True,
    )

    response = validate_run_request(
        run,
        require_ibm_confirmation=True,
        ibm_credentials_available=True,
    )

    assert response.valid is True
    assert any("matrix elements" in warning for warning in response.warnings)


def test_validate_run_request_rejects_large_kqd_ibm_matrix_elements() -> None:
    run = _make_kqd_run_create(
        backend_target=BackendTarget.IBM_RUNTIME,
        backend_options={"backend_name": "ibm_brisbane"},
        advanced_config={
            "algorithm": RunAlgorithm.KQD,
            "krylov_dim": 9,
            "time_step": 0.2,
            "evolution_method": "trotter",
            "trotter_steps": 1,
        },
        ibm_runtime_confirmed=True,
    )

    response = validate_run_request(
        run,
        require_ibm_confirmation=True,
        ibm_credentials_available=True,
    )

    assert response.valid is False
    assert any(error.field == KRYLOV_DIM_FIELD for error in response.errors)


def test_validate_run_request_allows_balanced_easy_kqd_ibm_matrix_elements() -> None:
    run = RunCreate.model_validate(
        {
            "molecule_id": uuid4(),
            "algorithm": RunAlgorithm.KQD,
            "mode": RunMode.EASY,
            "backend_target": BackendTarget.IBM_RUNTIME,
            "backend_options": {"backend_name": "ibm_brisbane"},
            "easy_options": {"goal": "balanced"},
            "ibm_runtime_confirmed": True,
        }
    )

    response = validate_run_request(
        run,
        require_ibm_confirmation=True,
        ibm_credentials_available=True,
    )

    assert response.valid is True
    assert response.errors == []
    assert any("branch-state Estimator circuits" in warning for warning in response.warnings)


def test_validate_run_request_requires_paired_sqd_electron_counts() -> None:
    run = _make_sqd_run_create(
        advanced_config={
            "algorithm": RunAlgorithm.SQD,
            "samples_per_batch": 128,
            "num_batches": 4,
            "max_iterations": 25,
            "num_elec_a": 2,
        }
    )

    response = validate_run_request(run, molecule_active_space_n_electrons=4)

    assert response.valid is False
    assert any(
        error.field == "advanced_config.num_elec_a|num_elec_b"
        and error.code == ValidationErrorCode.MISSING_REQUIRED
        for error in response.errors
    )


def test_validate_run_request_rejects_sqd_active_space_electron_mismatch() -> None:
    run = _make_sqd_run_create(
        advanced_config={
            "algorithm": RunAlgorithm.SQD,
            "samples_per_batch": 128,
            "num_batches": 4,
            "max_iterations": 25,
            "num_elec_a": 1,
            "num_elec_b": 1,
        }
    )

    response = validate_run_request(run, molecule_active_space_n_electrons=6)

    assert response.valid is False
    assert any(
        error.field == "advanced_config.num_elec_a|num_elec_b"
        and error.code == ValidationErrorCode.INCOMPATIBLE_BACKEND
        for error in response.errors
    )


def test_validate_run_request_warns_for_kqd_exact_with_extra_trotter_steps() -> None:
    run = _make_kqd_run_create()

    response = validate_run_request(run)

    assert response.valid is True
    assert any("trotter_steps is ignored" in warning for warning in response.warnings)


@pytest.mark.parametrize(
    ("advanced_config", "expected_algorithm"),
    [
        (
            KQDAdvancedConfig(
                algorithm=RunAlgorithm.KQD,
                krylov_dim=4,
                time_step=0.2,
                evolution_method="exact",
                trotter_steps=1,
                residual_tolerance=1e-5,
            ),
            RunAlgorithm.KQD,
        ),
        (
            QFDAdvancedConfig(
                algorithm=RunAlgorithm.QFD,
                num_time_points=4,
                max_time=1.0,
                time_grid_type="linear",
                trotter_steps=1,
                residual_tolerance=1e-5,
            ),
            RunAlgorithm.QFD,
        ),
        (
            QSEAdvancedConfig(
                algorithm=RunAlgorithm.QSE,
                reference_method="vqe",
                provided_state_vector=None,
                provided_sector_amplitudes=None,
                excitation_level="singles",
                max_subspace_dim=4,
                vqe_reference_ansatz_name=None,
                vqe_reference_optimizer_name=None,
                vqe_reference_max_iterations=None,
                vqe_reference_reps=None,
                regularization=None,
                overlap_threshold=None,
                residual_tolerance=1e-5,
            ),
            RunAlgorithm.QSE,
        ),
        (
            SKQDAdvancedConfig(
                algorithm=RunAlgorithm.SKQD,
                samples_per_state=128,
                base_sampling_options=SKQDSamplingParams(
                    num_elec_a=None,
                    num_elec_b=None,
                    min_selected_configurations=None,
                    seed=None,
                    symmetrize_spin=None,
                    max_dim=None,
                    spin_sq_target=None,
                    sci_solver_options=None,
                ),
                krylov_extension_dim=2,
                time_step=0.1,
                residual_tolerance=1e-5,
            ),
            RunAlgorithm.SKQD,
        ),
    ],
)
def test_run_create_preserves_residual_tolerance_for_projected_algorithms(
    advanced_config, expected_algorithm
) -> None:
    run = RunCreate.model_validate(
        {
            "molecule_id": uuid4(),
            "algorithm": expected_algorithm,
            "mode": RunMode.ADVANCED,
            "backend_target": BackendTarget.STATEVECTOR,
            "advanced_config": advanced_config.model_dump(mode="python"),
        }
    )

    assert run.advanced_config is not None
    assert run.advanced_config.algorithm == expected_algorithm
    assert getattr(run.advanced_config, "residual_tolerance") == pytest.approx(1e-5)


def test_validate_run_request_warns_for_large_vqe_active_space() -> None:
    run = RunCreate.model_validate(
        {
            "molecule_id": uuid4(),
            "algorithm": RunAlgorithm.VQE,
            "mode": RunMode.ADVANCED,
            "backend_target": BackendTarget.STATEVECTOR,
            "advanced_config": {
                "algorithm": RunAlgorithm.VQE,
                "ansatz_name": "EfficientSU2",
                "optimizer_name": "COBYLA",
                "max_iterations": 50,
            },
        }
    )

    response = validate_run_request(run, molecule_active_space_n_orbitals=10)

    assert response.valid is True
    assert any("9-12 range" in warning for warning in response.warnings)


def test_validate_run_validation_request_uses_molecule_context(
    test_db: Session,
    sample_molecule,
) -> None:
    sample_molecule.active_space = {"n_electrons": 3, "n_orbitals": 2}
    test_db.commit()
    run = _make_kqd_run_create(molecule_id=sample_molecule.id)

    response = validate_run_validation_request(
        test_db,
        RunValidationRequest(molecule_id=sample_molecule.id, run=run),
    )

    assert response.valid is False
    assert response.estimate is not None
    assert any(error.field == "molecule.active_space.n_electrons" for error in response.errors)


def test_validate_run_request_allows_large_vqe_active_space_with_warning() -> None:
    run = RunCreate.model_validate(
        {
            "molecule_id": uuid4(),
            "algorithm": RunAlgorithm.VQE,
            "mode": RunMode.ADVANCED,
            "backend_target": BackendTarget.STATEVECTOR,
            "advanced_config": {
                "algorithm": RunAlgorithm.VQE,
                "ansatz_name": "EfficientSU2",
                "optimizer_name": "COBYLA",
                "max_iterations": 50,
            },
        }
    )

    response = validate_run_request(run, molecule_active_space_n_orbitals=15)

    assert response.valid is True
    assert any("above 12" in warning for warning in response.warnings)


def test_validate_run_request_rejects_vqe_initial_parameter_length_mismatch() -> None:
    run = RunCreate.model_validate(
        {
            "molecule_id": uuid4(),
            "algorithm": RunAlgorithm.VQE,
            "mode": RunMode.ADVANCED,
            "backend_target": BackendTarget.STATEVECTOR,
            "advanced_config": {
                "algorithm": RunAlgorithm.VQE,
                "ansatz_name": "EfficientSU2",
                "optimizer_name": "COBYLA",
                "max_iterations": 50,
                "reps": 1,
                "initial_parameters": [0.0],
            },
        }
    )

    response = validate_run_request(run, molecule_active_space_n_orbitals=2)

    assert response.valid is False
    assert any(error.field == "advanced_config.initial_parameters" for error in response.errors)


def test_validate_run_request_rejects_vqe_parameter_bounds_length_mismatch() -> None:
    run = RunCreate.model_validate(
        {
            "molecule_id": uuid4(),
            "algorithm": RunAlgorithm.VQE,
            "mode": RunMode.ADVANCED,
            "backend_target": BackendTarget.STATEVECTOR,
            "advanced_config": {
                "algorithm": RunAlgorithm.VQE,
                "ansatz_name": "EfficientSU2",
                "optimizer_name": "COBYLA",
                "max_iterations": 50,
                "reps": 1,
                "parameter_bounds": [[-0.1, 0.1]],
            },
        }
    )

    response = validate_run_request(run, molecule_active_space_n_orbitals=2)

    assert response.valid is False
    assert any(error.field == "advanced_config.parameter_bounds" for error in response.errors)


def test_validate_run_request_rejects_vqe_reversed_parameter_bounds() -> None:
    parameter_bounds = [[-0.1, 0.1] for _ in range(16)]
    parameter_bounds[0] = [0.1, -0.1]
    run = RunCreate.model_validate(
        {
            "molecule_id": uuid4(),
            "algorithm": RunAlgorithm.VQE,
            "mode": RunMode.ADVANCED,
            "backend_target": BackendTarget.STATEVECTOR,
            "advanced_config": {
                "algorithm": RunAlgorithm.VQE,
                "ansatz_name": "EfficientSU2",
                "optimizer_name": "COBYLA",
                "max_iterations": 50,
                "reps": 1,
                "parameter_bounds": parameter_bounds,
            },
        }
    )

    response = validate_run_request(run, molecule_active_space_n_orbitals=2)

    assert response.valid is False
    assert any(error.field == "advanced_config.parameter_bounds.0" for error in response.errors)


@pytest.mark.parametrize("error", [TypeError("invalid ansatz"), ValueError("invalid ansatz")])
def test_vqe_parameter_count_skips_expected_builder_errors(
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
) -> None:
    run = RunCreate.model_validate(
        {
            "molecule_id": uuid4(),
            "algorithm": RunAlgorithm.VQE,
            "mode": RunMode.ADVANCED,
            "backend_target": BackendTarget.STATEVECTOR,
            "advanced_config": {
                "algorithm": RunAlgorithm.VQE,
                "ansatz_name": "EfficientSU2",
                "optimizer_name": "COBYLA",
                "max_iterations": 50,
            },
        }
    )
    monkeypatch.setattr(
        algorithm_policies,
        "_build_vqe_validation_ansatz",
        lambda **_kwargs: (_ for _ in ()).throw(error),
    )

    assert (
        algorithm_policies._resolve_vqe_parameter_count(
            run,
            molecule_active_space_n_orbitals=2,
        )
        is None
    )


def test_vqe_parameter_count_does_not_hide_unexpected_builder_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = RunCreate.model_validate(
        {
            "molecule_id": uuid4(),
            "algorithm": RunAlgorithm.VQE,
            "mode": RunMode.ADVANCED,
            "backend_target": BackendTarget.STATEVECTOR,
            "advanced_config": {
                "algorithm": RunAlgorithm.VQE,
                "ansatz_name": "EfficientSU2",
                "optimizer_name": "COBYLA",
                "max_iterations": 50,
            },
        }
    )
    monkeypatch.setattr(
        algorithm_policies,
        "_build_vqe_validation_ansatz",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("unexpected failure")),
    )

    with pytest.raises(RuntimeError, match="unexpected failure"):
        algorithm_policies._resolve_vqe_parameter_count(
            run,
            molecule_active_space_n_orbitals=2,
        )


def test_validate_run_request_allows_kqd_large_statevector_sector_path() -> None:
    run = _make_kqd_run_create()

    response = validate_run_request(run, molecule_active_space_n_orbitals=7)

    assert response.valid is True
    assert any("fixed-particle-sector matrix-free path" in warning for warning in response.warnings)


def test_validate_run_request_blocks_vqe_iteration_limit() -> None:
    with pytest.raises(ValidationError):
        RunCreate.model_validate(
            {
                "molecule_id": uuid4(),
                "algorithm": RunAlgorithm.VQE,
                "mode": RunMode.ADVANCED,
                "backend_target": BackendTarget.STATEVECTOR,
                "advanced_config": {
                    "algorithm": RunAlgorithm.VQE,
                    "ansatz_name": "EfficientSU2",
                    "optimizer_name": "COBYLA",
                    "max_iterations": 5001,
                },
            }
        )


def test_validate_run_request_blocks_sqd_sampling_limits() -> None:
    run = _make_sqd_run_create(
        advanced_config={
            "algorithm": RunAlgorithm.SQD,
            "samples_per_batch": 2001,
            "num_batches": 129,
            "max_iterations": 25,
        }
    )

    response = validate_run_request(run)

    assert response.valid is False
    assert any(
        error.field == "advanced_config.samples_per_batch"
        and error.code == ValidationErrorCode.INVALID_RANGE
        for error in response.errors
    )
    assert any(
        error.field == "advanced_config.num_batches"
        and error.code == ValidationErrorCode.INVALID_RANGE
        for error in response.errors
    )


def test_validate_run_request_rejects_non_singlet_multiplicity() -> None:
    run = _make_kqd_run_create()

    response = validate_run_request(run, molecule_multiplicity=3)

    assert response.valid is False
    assert any(
        error.field == "molecule.multiplicity"
        and error.code == ValidationErrorCode.INCOMPATIBLE_BACKEND
        for error in response.errors
    )


def test_validate_run_request_rejects_odd_active_space_electrons() -> None:
    run = _make_kqd_run_create()

    response = validate_run_request(
        run,
        molecule_multiplicity=1,
        molecule_active_space_n_electrons=3,
    )

    assert response.valid is False
    assert any(
        error.field == "molecule.active_space.n_electrons"
        and error.code == ValidationErrorCode.INCOMPATIBLE_BACKEND
        for error in response.errors
    )


def test_validate_run_request_blocks_kqd_krylov_limit() -> None:
    run = _make_kqd_run_create(
        advanced_config={
            "algorithm": RunAlgorithm.KQD,
            "krylov_dim": 65,
            "time_step": 0.2,
            "evolution_method": "exact",
            "trotter_steps": 3,
        }
    )

    response = validate_run_request(run)

    assert response.valid is False
    assert any(
        error.field == KRYLOV_DIM_FIELD and error.code == ValidationErrorCode.INVALID_RANGE
        for error in response.errors
    )


def test_validate_run_request_blocks_qfd_time_point_limit() -> None:
    run = RunCreate.model_validate(
        {
            "molecule_id": uuid4(),
            "algorithm": RunAlgorithm.QFD,
            "mode": RunMode.ADVANCED,
            "backend_target": BackendTarget.STATEVECTOR,
            "advanced_config": {
                "algorithm": RunAlgorithm.QFD,
                "num_time_points": 129,
                "max_time": 2.0,
            },
        }
    )

    response = validate_run_request(run)

    assert response.valid is False
    assert any(
        error.field == "advanced_config.num_time_points"
        and error.code == ValidationErrorCode.INVALID_RANGE
        for error in response.errors
    )


def test_validate_run_request_rejects_ibm_without_credentials() -> None:
    run = RunCreate.model_validate(
        {
            "molecule_id": uuid4(),
            "algorithm": RunAlgorithm.VQE,
            "mode": RunMode.ADVANCED,
            "backend_target": BackendTarget.IBM_RUNTIME,
            "backend_options": {
                "selection_policy": BackendSelectionPolicy.MANUAL,
                "backend_name": "ibm_brisbane",
            },
            "advanced_config": {
                "algorithm": RunAlgorithm.VQE,
                "ansatz_name": "EfficientSU2",
                "optimizer_name": "COBYLA",
                "max_iterations": 50,
            },
        }
    )

    response = validate_run_request(run)

    assert response.valid is False
    assert any(error.field == "ibm_runtime_credentials" for error in response.errors)


def test_validate_run_request_rejects_backend_derived_aer_without_credentials() -> None:
    run = RunCreate.model_validate(
        {
            "molecule_id": uuid4(),
            "algorithm": RunAlgorithm.VQE,
            "mode": RunMode.ADVANCED,
            "backend_target": BackendTarget.AER_SIMULATOR,
            "backend_options": {
                "selection_policy": BackendSelectionPolicy.MANUAL,
                "backend_name": "aer_simulator",
            },
            "noise_profile": {
                "source": NoiseModelSource.BACKEND_DERIVED,
                "reference_backend": "ibm_brisbane",
            },
            "advanced_config": {
                "algorithm": RunAlgorithm.VQE,
                "ansatz_name": "EfficientSU2",
                "optimizer_name": "COBYLA",
                "max_iterations": 50,
            },
        }
    )

    response = validate_run_request(run)

    assert response.valid is False
    assert any(error.field == "noise_profile" for error in response.errors)


def test_validate_run_request_requires_manual_ibm_backend_name() -> None:
    run = RunCreate.model_validate(
        {
            "molecule_id": uuid4(),
            "algorithm": RunAlgorithm.VQE,
            "mode": RunMode.ADVANCED,
            "backend_target": BackendTarget.IBM_RUNTIME,
            "advanced_config": {
                "algorithm": RunAlgorithm.VQE,
                "ansatz_name": "EfficientSU2",
                "optimizer_name": "COBYLA",
                "max_iterations": 50,
            },
        }
    )

    response = validate_run_request(run, ibm_credentials_available=True)

    assert response.valid is False
    assert any(error.field == "backend_options.backend_name" for error in response.errors)


def test_validate_run_request_allows_kqd_ibm_least_busy_matrix_elements() -> None:
    run = _make_kqd_run_create(
        backend_target=BackendTarget.IBM_RUNTIME,
        backend_options={
            "selection_policy": BackendSelectionPolicy.LEAST_BUSY,
        },
        advanced_config={
            "algorithm": RunAlgorithm.KQD,
            "krylov_dim": 4,
            "time_step": 0.2,
            "evolution_method": "trotter",
            "trotter_steps": 4,
        },
    )

    response = validate_run_request(run, ibm_credentials_available=True)

    assert response.valid is True
    assert not response.errors
    assert any("matrix elements" in warning for warning in response.warnings)
