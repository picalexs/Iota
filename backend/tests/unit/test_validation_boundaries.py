"""
Boundary tests for validation_service.validate_run_request.

Covers F8 (hard-limit bypass via advanced_config) and F9 (disabled backend
returns proper error rather than 500). Also exercises active-space guardrails
and SQD/SKQD electron-count cross-checks.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from app.models.enums import BackendTarget, RunAlgorithm, RunMode
from app.schemas.run import RunCreate
from app.schemas.run_responses import ValidationErrorCode
from app.services.validation_service import (
    _MAX_KQD_KRYLOV_DIM,
    _MAX_KQD_TROTTER_STEPS,
    _MAX_QFD_NUM_TIME_POINTS,
    _MAX_QSE_SUBSPACE_DIM,
    _MAX_SKQD_EXTENSION_DIM,
    _MAX_SKQD_SAMPLES_PER_STATE,
    _MAX_SQD_NUM_BATCHES,
    _MAX_SQD_SAMPLES_PER_BATCH,
    _MAX_VQE_ITERATIONS,
    validate_run_request,
)
from pydantic import ValidationError

_MOLECULE_ID = uuid.uuid4()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _run_create(
    *,
    algorithm: RunAlgorithm,
    advanced_config: dict[str, Any] | None,
    mode: RunMode = RunMode.ADVANCED,
    backend_target: BackendTarget = BackendTarget.STATEVECTOR,
    backend_options: dict[str, Any] | None = None,
    easy_options: dict[str, Any] | None = None,
    noise_profile: dict[str, Any] | None = None,
    ibm_runtime_confirmed: bool = False,
) -> RunCreate:
    return RunCreate.model_validate(
        {
            "molecule_id": _MOLECULE_ID,
            "client_request_id": None,
            "algorithm": algorithm,
            "mode": mode,
            "backend_target": backend_target,
            "backend_options": backend_options or {},
            "easy_options": easy_options,
            "advanced_config": advanced_config,
            "basis_set_override": None,
            "chemical_accuracy_target_ha": None,
            "noise_profile": noise_profile,
            "ibm_runtime_confirmed": ibm_runtime_confirmed,
        }
    )


def _vqe_payload(max_iterations: int = 10) -> RunCreate:
    return _run_create(
        algorithm=RunAlgorithm.VQE,
        advanced_config={
            "algorithm": RunAlgorithm.VQE,
            "ansatz_name": "EfficientSU2",
            "optimizer_name": "COBYLA",
            "max_iterations": max_iterations,
        },
    )


def _sqd_payload(
    *,
    samples_per_batch: int = 128,
    num_batches: int = 4,
    max_iterations: int = 10,
) -> RunCreate:
    return _run_create(
        algorithm=RunAlgorithm.SQD,
        advanced_config={
            "algorithm": RunAlgorithm.SQD,
            "samples_per_batch": samples_per_batch,
            "num_batches": num_batches,
            "max_iterations": max_iterations,
        },
    )


def test_sqd_accepts_explicit_full_selected_ci_mode() -> None:
    payload = _run_create(
        algorithm=RunAlgorithm.SQD,
        advanced_config={
            "algorithm": RunAlgorithm.SQD,
            "samples_per_batch": 128,
            "num_batches": 4,
            "max_iterations": 10,
            "max_dim": "full",
        },
    )

    assert payload.advanced_config.max_dim == "full"


def test_sqd_accepts_explicit_vqe_sampling_provider() -> None:
    payload = _run_create(
        algorithm=RunAlgorithm.SQD,
        advanced_config={
            "algorithm": RunAlgorithm.SQD,
            "samples_per_batch": 128,
            "num_batches": 4,
            "max_iterations": 10,
            "sampling_state_source": "vqe",
            "sampling_vqe_ansatz_name": "NumberPreserving",
            "sampling_vqe_max_iterations": 12,
            "sampling_vqe_reps": 2,
        },
    )

    assert payload.advanced_config.sampling_state_source == "vqe"
    assert payload.advanced_config.sampling_vqe_ansatz_name == "NumberPreserving"


def test_skqd_accepts_declared_trotter_steps() -> None:
    payload = _run_create(
        algorithm=RunAlgorithm.SKQD,
        advanced_config={
            "algorithm": RunAlgorithm.SKQD,
            "samples_per_state": 16,
            "base_sampling_options": {},
            "krylov_extension_dim": 2,
            "trotter_steps": 3,
        },
    )

    assert payload.advanced_config.trotter_steps == 3


def _kqd_payload(krylov_dim: int = 4, trotter_steps: int = 1) -> RunCreate:
    return _run_create(
        algorithm=RunAlgorithm.KQD,
        advanced_config={
            "algorithm": RunAlgorithm.KQD,
            "krylov_dim": krylov_dim,
            "time_step": 0.1,
            "trotter_steps": trotter_steps,
        },
    )


def _qfd_payload(
    num_time_points: int = 5,
    trotter_steps: int = 1,
    *,
    qfd_variant: str = "qfd_chemistry_forward",
    kappa: float = 1.0,
    time_grid_type: str = "linear",
) -> RunCreate:
    return _run_create(
        algorithm=RunAlgorithm.QFD,
        advanced_config={
            "algorithm": RunAlgorithm.QFD,
            "num_time_points": num_time_points,
            "max_time": 1.0,
            "trotter_steps": trotter_steps,
            "qfd_variant": qfd_variant,
            "kappa": kappa,
            "time_grid_type": time_grid_type,
        },
    )


def _qse_payload(
    max_subspace_dim: int = 4,
    *,
    reference_method: str = "vqe",
    provided_sector_amplitudes: list[dict[str, object]] | None = None,
) -> RunCreate:
    return _run_create(
        algorithm=RunAlgorithm.QSE,
        advanced_config={
            "algorithm": RunAlgorithm.QSE,
            "reference_method": reference_method,
            "provided_sector_amplitudes": provided_sector_amplitudes,
            "excitation_level": "singles",
            "max_subspace_dim": max_subspace_dim,
        },
    )


def _skqd_payload(
    krylov_extension_dim: int = 2,
    samples_per_state: int = 128,
) -> RunCreate:
    return _run_create(
        algorithm=RunAlgorithm.SKQD,
        advanced_config={
            "algorithm": RunAlgorithm.SKQD,
            "samples_per_state": samples_per_state,
            "base_sampling_options": {},
            "krylov_extension_dim": krylov_extension_dim,
        },
    )


# ── Backend capability and credential validation ─────────────────────────────


class TestBackendCapabilityValidation:
    """Backend validation returns structured errors rather than exploding."""

    def test_aer_backend_is_valid(self) -> None:
        payload = _run_create(
            algorithm=RunAlgorithm.VQE,
            backend_target=BackendTarget.AER_SIMULATOR,
            advanced_config={
                "algorithm": RunAlgorithm.VQE,
                "ansatz_name": "EfficientSU2",
                "optimizer_name": "COBYLA",
                "max_iterations": 10,
            },
        )
        result = validate_run_request(payload)
        assert result.valid
        assert not result.errors

    def test_ibm_backend_without_credentials_returns_error(self) -> None:
        payload = _run_create(
            algorithm=RunAlgorithm.VQE,
            backend_target=BackendTarget.IBM_RUNTIME,
            backend_options={"backend_name": "ibm_brisbane"},
            advanced_config={
                "algorithm": RunAlgorithm.VQE,
                "ansatz_name": "EfficientSU2",
                "optimizer_name": "COBYLA",
                "max_iterations": 10,
            },
        )
        result = validate_run_request(payload)
        assert not result.valid
        assert any(error.field == "ibm_runtime_credentials" for error in result.errors)

    def test_statevector_backend_is_valid(self) -> None:
        result = validate_run_request(_vqe_payload())
        # statevector with valid config should produce no backend errors
        backend_errors = [e for e in result.errors if e.field == "backend_target"]
        assert not backend_errors


# ── F8: Hard-limit boundary checks ───────────────────────────────────────────


class TestVQEHardLimits:
    """VQE max_iterations must not exceed _MAX_VQE_ITERATIONS via advanced_config."""

    def test_at_limit_is_valid(self) -> None:
        result = validate_run_request(_vqe_payload(max_iterations=_MAX_VQE_ITERATIONS))
        limit_errors = [e for e in result.errors if "max_iterations" in e.field]
        assert not limit_errors

    def test_over_limit_is_rejected_by_schema(self) -> None:
        with pytest.raises(ValidationError):
            _vqe_payload(max_iterations=_MAX_VQE_ITERATIONS + 1)


class TestSQDHardLimits:
    def test_samples_per_batch_at_limit(self) -> None:
        result = validate_run_request(_sqd_payload(samples_per_batch=_MAX_SQD_SAMPLES_PER_BATCH))
        assert not any("samples_per_batch" in e.field for e in result.errors)

    def test_samples_per_batch_over_limit(self) -> None:
        result = validate_run_request(
            _sqd_payload(samples_per_batch=_MAX_SQD_SAMPLES_PER_BATCH + 1)
        )
        assert not result.valid
        assert any("samples_per_batch" in e.field for e in result.errors)

    def test_num_batches_over_limit(self) -> None:
        result = validate_run_request(_sqd_payload(num_batches=_MAX_SQD_NUM_BATCHES + 1))
        assert not result.valid
        assert any("num_batches" in e.field for e in result.errors)

    def test_max_iterations_over_limit(self) -> None:
        result = validate_run_request(_sqd_payload(max_iterations=_MAX_VQE_ITERATIONS + 1))
        assert not result.valid
        assert any("max_iterations" in e.field for e in result.errors)


class TestKQDHardLimits:
    def test_krylov_dim_at_limit(self) -> None:
        result = validate_run_request(_kqd_payload(krylov_dim=_MAX_KQD_KRYLOV_DIM))
        assert not any("krylov_dim" in e.field for e in result.errors)

    def test_krylov_dim_over_limit(self) -> None:
        result = validate_run_request(_kqd_payload(krylov_dim=_MAX_KQD_KRYLOV_DIM + 1))
        assert not result.valid
        assert any("krylov_dim" in e.field for e in result.errors)

    def test_trotter_steps_at_limit(self) -> None:
        result = validate_run_request(_kqd_payload(trotter_steps=_MAX_KQD_TROTTER_STEPS))
        assert not any("trotter_steps" in e.field for e in result.errors)

    def test_trotter_steps_over_limit_rejected_by_schema(self) -> None:
        with pytest.raises(ValidationError):
            _kqd_payload(trotter_steps=_MAX_KQD_TROTTER_STEPS + 1)


class TestQFDHardLimits:
    def test_custom_variant_is_rejected_by_schema(self) -> None:
        with pytest.raises(ValidationError):
            _qfd_payload(qfd_variant="qfd_custom_grid")

    def test_unknown_time_grid_type_is_rejected_by_schema(self) -> None:
        with pytest.raises(ValidationError):
            _qfd_payload(time_grid_type="typo")

    def test_original_symmetric_variant_accepts_odd_grid(self) -> None:
        result = validate_run_request(
            _qfd_payload(
                num_time_points=5,
                qfd_variant="qfd_original_symmetric",
                kappa=2.0,
            )
        )
        assert result.valid

    @pytest.mark.parametrize("num_time_points", [2, 4, 128])
    def test_original_symmetric_variant_rejects_even_grid(
        self, num_time_points: int
    ) -> None:
        result = validate_run_request(
            _qfd_payload(
                num_time_points=num_time_points,
                qfd_variant="qfd_original_symmetric",
            )
        )
        assert not result.valid
        assert any("num_time_points" in error.field for error in result.errors)

    def test_num_time_points_at_limit(self) -> None:
        result = validate_run_request(_qfd_payload(num_time_points=_MAX_QFD_NUM_TIME_POINTS))
        assert not any("num_time_points" in e.field for e in result.errors)

    def test_num_time_points_over_limit(self) -> None:
        result = validate_run_request(_qfd_payload(num_time_points=_MAX_QFD_NUM_TIME_POINTS + 1))
        assert not result.valid
        assert any("num_time_points" in e.field for e in result.errors)

    def test_trotter_steps_at_limit(self) -> None:
        result = validate_run_request(_qfd_payload(trotter_steps=_MAX_KQD_TROTTER_STEPS))
        assert not any("trotter_steps" in e.field for e in result.errors)

    def test_trotter_steps_over_limit_rejected_by_schema(self) -> None:
        with pytest.raises(ValidationError):
            _qfd_payload(trotter_steps=_MAX_KQD_TROTTER_STEPS + 1)


class TestQSEHardLimits:
    def test_max_subspace_dim_at_limit(self) -> None:
        result = validate_run_request(_qse_payload(max_subspace_dim=_MAX_QSE_SUBSPACE_DIM))
        assert not any("max_subspace_dim" in e.field for e in result.errors)

    def test_max_subspace_dim_over_limit_rejected_by_schema(self) -> None:
        with pytest.raises(ValidationError):
            _qse_payload(max_subspace_dim=_MAX_QSE_SUBSPACE_DIM + 1)

    def test_provided_references_accept_complex_json_scalars(self) -> None:
        state_payload = _run_create(
            algorithm=RunAlgorithm.QSE,
            advanced_config={
                "algorithm": RunAlgorithm.QSE,
                "reference_method": "provided_state",
                "provided_state_vector": [
                    {"real": 1.0, "imag": 0.0},
                    {"real": 0.0, "imag": 0.5},
                ],
                "excitation_level": "singles",
                "max_subspace_dim": 2,
            },
        )
        sector_payload = _qse_payload(
            reference_method="provided_sector",
            provided_sector_amplitudes=[
                {"bitstring": "0101", "amplitude": {"real": 0.5, "imag": -0.25}},
            ],
        )

        state_result = validate_run_request(state_payload)
        sector_result = validate_run_request(sector_payload)

        assert state_result.valid
        assert sector_result.valid


class TestSKQDHardLimits:
    def test_samples_per_state_at_limit(self) -> None:
        result = validate_run_request(
            _skqd_payload(samples_per_state=_MAX_SKQD_SAMPLES_PER_STATE)
        )
        assert not any("samples_per_state" in e.field for e in result.errors)

    def test_samples_per_state_over_limit_rejected_by_schema(self) -> None:
        with pytest.raises(ValidationError):
            _skqd_payload(samples_per_state=_MAX_SKQD_SAMPLES_PER_STATE + 1)

    def test_krylov_extension_dim_at_limit(self) -> None:
        result = validate_run_request(_skqd_payload(krylov_extension_dim=_MAX_SKQD_EXTENSION_DIM))
        assert not any("krylov_extension_dim" in e.field for e in result.errors)

    def test_krylov_extension_dim_over_limit_rejected_by_schema(self) -> None:
        with pytest.raises(ValidationError):
            _skqd_payload(krylov_extension_dim=_MAX_SKQD_EXTENSION_DIM + 1)

    def test_skqd_time_step_is_part_of_advanced_contract(self) -> None:
        payload = _run_create(
            algorithm=RunAlgorithm.SKQD,
            advanced_config={
                "algorithm": RunAlgorithm.SKQD,
                "samples_per_state": 128,
                "base_sampling_options": {},
                "krylov_extension_dim": 2,
                "time_step": 0.25,
            },
        )

        assert payload.snapshot_config()["advanced_config"]["time_step"] == pytest.approx(0.25)


@pytest.mark.parametrize("backend_target", [BackendTarget.STATEVECTOR, BackendTarget.AER_SIMULATOR])
def test_custom_settings_matrix_validates_for_each_algorithm_without_fallback(
    backend_target: BackendTarget,
) -> None:
    noise_profile = (
        {
            "source": "custom_preset",
            "preset": "depolarizing_cx",
            "strength": 0.01,
        }
        if backend_target == BackendTarget.AER_SIMULATOR
        else None
    )
    payloads = [
        _run_create(
            algorithm=RunAlgorithm.VQE,
            backend_target=backend_target,
            noise_profile=noise_profile,
            advanced_config={
                "algorithm": RunAlgorithm.VQE,
                "ansatz_name": "EfficientSU2",
                "optimizer_name": "COBYLA",
                "max_iterations": 17,
                "max_function_evaluations": 19,
                "reps": 1,
            },
        ),
        _run_create(
            algorithm=RunAlgorithm.SQD,
            backend_target=backend_target,
            noise_profile=noise_profile,
            advanced_config={
                "algorithm": RunAlgorithm.SQD,
                "samples_per_batch": 17,
                "num_batches": 2,
                "max_iterations": 3,
                "energy_tol": 1e-5,
                "occupancies_tol": 2e-5,
            },
        ),
        _run_create(
            algorithm=RunAlgorithm.SKQD,
            backend_target=backend_target,
            noise_profile=noise_profile,
            advanced_config={
                "algorithm": RunAlgorithm.SKQD,
                "samples_per_state": 17,
                "base_sampling_options": {"max_dim": 8},
                "krylov_extension_dim": 2,
                "time_step": 0.17,
                "trotter_steps": 2,
            },
        ),
        _run_create(
            algorithm=RunAlgorithm.KQD,
            backend_target=backend_target,
            noise_profile=noise_profile,
            advanced_config={
                "algorithm": RunAlgorithm.KQD,
                "krylov_dim": 3,
                "time_step": 0.13,
                "evolution_method": "trotter",
                "trotter_steps": 2,
            },
        ),
        _run_create(
            algorithm=RunAlgorithm.QFD,
            backend_target=backend_target,
            noise_profile=noise_profile,
            advanced_config={
                "algorithm": RunAlgorithm.QFD,
                "num_time_points": 5,
                "max_time": 0.7,
                "time_grid_type": "linear",
                "qfd_variant": "qfd_chemistry_forward",
                "kappa": 1.3,
                "trotter_steps": 2,
            },
        ),
        _run_create(
            algorithm=RunAlgorithm.QSE,
            backend_target=backend_target,
            noise_profile=noise_profile,
            advanced_config={
                "algorithm": RunAlgorithm.QSE,
                "reference_method": "hf",
                "excitation_level": "singles",
                "max_subspace_dim": 3,
                "regularization": 2e-7,
                "overlap_threshold": 2e-5,
            },
        ),
    ]

    for payload in payloads:
        result = validate_run_request(payload)
        assert result.valid, f"{payload.algorithm} custom settings failed: {result.errors}"
        if payload.algorithm == RunAlgorithm.QSE and backend_target == BackendTarget.AER_SIMULATOR:
            assert any("measured QSE" in warning for warning in result.warnings)
        advanced = payload.snapshot_config()["advanced_config"]
        if payload.algorithm == RunAlgorithm.VQE:
            assert advanced["max_iterations"] == 17
            assert advanced["max_function_evaluations"] == 19
        elif payload.algorithm == RunAlgorithm.SQD:
            assert advanced["samples_per_batch"] == 17
            assert advanced["num_batches"] == 2
        elif payload.algorithm == RunAlgorithm.SKQD:
            assert advanced["samples_per_state"] == 17
            assert advanced["krylov_extension_dim"] == 2
        elif payload.algorithm == RunAlgorithm.KQD:
            assert advanced["krylov_dim"] == 3
            assert advanced["trotter_steps"] == 2
        elif payload.algorithm == RunAlgorithm.QFD:
            assert advanced["num_time_points"] == 5
            assert advanced["kappa"] == pytest.approx(1.3)
        elif payload.algorithm == RunAlgorithm.QSE:
            assert advanced["max_subspace_dim"] == 3
            assert advanced["regularization"] == pytest.approx(2e-7)


# ── Active-space guardrails ───────────────────────────────────────────────────


class TestActiveSpaceGuardrails:
    def test_orbitals_le_8_no_warning(self) -> None:
        result = validate_run_request(_vqe_payload(), molecule_active_space_n_orbitals=8)
        assert not result.warnings or not any("n_orbitals" in w for w in result.warnings)

    def test_vqe_orbitals_9_to_12_produces_warning(self) -> None:
        result = validate_run_request(_vqe_payload(), molecule_active_space_n_orbitals=10)
        assert any("9-12" in w or "n_orbitals" in w for w in result.warnings)

    def test_vqe_orbitals_above_12_warns_but_remains_valid(self) -> None:
        result = validate_run_request(_vqe_payload(), molecule_active_space_n_orbitals=13)
        assert result.valid
        assert any("above 12" in w for w in result.warnings)

    def test_kqd_above_6_orbitals_uses_sector_path(self) -> None:
        result = validate_run_request(
            _kqd_payload(),
            molecule_active_space_n_electrons=2,
            molecule_active_space_n_orbitals=7,
        )
        assert result.valid
        assert not any("n_orbitals" in e.field for e in result.errors)
        assert any("fixed-particle-sector matrix-free" in w for w in result.warnings)

    def test_qfd_above_6_orbitals_uses_sector_path(self) -> None:
        result = validate_run_request(
            _qfd_payload(),
            molecule_active_space_n_electrons=2,
            molecule_active_space_n_orbitals=7,
        )
        assert result.valid
        assert not any("n_orbitals" in e.field for e in result.errors)
        assert any("fixed-particle-sector matrix-free" in w for w in result.warnings)

    def test_qse_above_6_orbitals_remains_valid(self) -> None:
        result = validate_run_request(
            _qse_payload(reference_method="hf"),
            molecule_active_space_n_electrons=2,
            molecule_active_space_n_orbitals=7,
        )
        assert result.valid
        assert not any("n_orbitals" in e.field for e in result.errors)

    def test_qse_vqe_reference_above_6_orbitals_is_invalid(self) -> None:
        result = validate_run_request(
            _qse_payload(reference_method="vqe"),
            molecule_active_space_n_electrons=2,
            molecule_active_space_n_orbitals=7,
        )
        assert not result.valid
        assert any("reference_method" in e.field for e in result.errors)

    def test_ibm_qse_hf_reference_validates_via_measured_path(self) -> None:
        payload = _run_create(
            algorithm=RunAlgorithm.QSE,
            backend_target=BackendTarget.IBM_RUNTIME,
            backend_options={"backend_name": "ibm_brisbane"},
            advanced_config={
                "algorithm": RunAlgorithm.QSE,
                "reference_method": "hf",
                "excitation_level": "singles",
                "max_subspace_dim": 4,
            },
        )

        result = validate_run_request(
            payload,
            molecule_active_space_n_electrons=2,
            molecule_active_space_n_orbitals=2,
            ibm_credentials_available=True,
        )

        assert result.valid
        assert not any(error.field == "backend_target" for error in result.errors)
        assert any("measured QSE" in warning for warning in result.warnings)

    @pytest.mark.parametrize("reference_method", ["vqe", "provided_state", "provided_sector"])
    @pytest.mark.parametrize(
        "backend_target,noise_profile",
        [
            (BackendTarget.IBM_RUNTIME, None),
            (
                BackendTarget.AER_SIMULATOR,
                {
                    "source": "custom_preset",
                    "preset": "depolarizing_cx",
                    "strength": 0.01,
                },
            ),
        ],
    )
    def test_measured_qse_rejects_non_hf_references(
        self,
        reference_method: str,
        backend_target: BackendTarget,
        noise_profile: dict[str, object] | None,
    ) -> None:
        payload = _run_create(
            algorithm=RunAlgorithm.QSE,
            backend_target=backend_target,
            backend_options={"backend_name": "ibm_brisbane"}
            if backend_target == BackendTarget.IBM_RUNTIME
            else None,
            noise_profile=noise_profile,
            advanced_config={
                "algorithm": RunAlgorithm.QSE,
                "reference_method": reference_method,
                "provided_state_vector": [1.0, 0.0]
                if reference_method == "provided_state"
                else None,
                "provided_sector_amplitudes": [
                    {"bitstring": "1100", "amplitude": 1.0}
                ]
                if reference_method == "provided_sector"
                else None,
                "excitation_level": "singles",
                "max_subspace_dim": 4,
            },
        )

        result = validate_run_request(
            payload,
            molecule_active_space_n_electrons=2,
            molecule_active_space_n_orbitals=2,
            ibm_credentials_available=True,
        )

        assert not result.valid
        assert any(
            error.field == "advanced_config.reference_method"
            and error.code == ValidationErrorCode.UNSUPPORTED_OPTION
            for error in result.errors
        )

    def test_skqd_above_6_orbitals_remains_valid(self) -> None:
        result = validate_run_request(
            _skqd_payload(),
            molecule_active_space_n_electrons=2,
            molecule_active_space_n_orbitals=7,
        )
        assert result.valid


class TestSQDSymmetrizationValidation:
    def test_sqd_symmetrize_spin_requires_balanced_electron_counts(self) -> None:
        payload = _run_create(
            algorithm=RunAlgorithm.SQD,
            advanced_config={
                "algorithm": RunAlgorithm.SQD,
                "samples_per_batch": 128,
                "num_batches": 4,
                "max_iterations": 10,
                "num_elec_a": 2,
                "num_elec_b": 0,
                "symmetrize_spin": True,
            },
        )

        result = validate_run_request(payload)

        assert not result.valid
        assert any(error.field == "advanced_config.symmetrize_spin" for error in result.errors)

    def test_skqd_symmetrize_spin_requires_matching_spin_caps(self) -> None:
        payload = _run_create(
            algorithm=RunAlgorithm.SKQD,
            advanced_config={
                "algorithm": RunAlgorithm.SKQD,
                "samples_per_state": 128,
                "base_sampling_options": {
                    "symmetrize_spin": True,
                    "max_dim": (8, 16),
                },
                "krylov_extension_dim": 2,
            },
        )

        result = validate_run_request(payload)

        assert not result.valid
        assert any(
            error.field == "advanced_config.base_sampling_options.max_dim"
            for error in result.errors
        )
        assert not any("n_orbitals" in e.field for e in result.errors)


# ── SQD electron cross-checks ─────────────────────────────────────────────────


class TestSQDElectronCrossChecks:
    def test_mismatched_elec_ab_vs_active_space_is_invalid(self) -> None:
        payload = _run_create(
            algorithm=RunAlgorithm.SQD,
            advanced_config={
                "algorithm": RunAlgorithm.SQD,
                "samples_per_batch": 128,
                "num_batches": 4,
                "max_iterations": 10,
                "num_elec_a": 1,
                "num_elec_b": 1,
            },
        )
        # Active space says 4 electrons but config says 1+1=2
        result = validate_run_request(payload, molecule_active_space_n_electrons=4)
        assert not result.valid
        assert any("num_elec_a" in e.field or "num_elec_b" in e.field for e in result.errors)

    def test_only_one_elec_count_provided_is_invalid(self) -> None:
        payload = _run_create(
            algorithm=RunAlgorithm.SQD,
            advanced_config={
                "algorithm": RunAlgorithm.SQD,
                "samples_per_batch": 128,
                "num_batches": 4,
                "max_iterations": 10,
                "num_elec_a": 1,
                "num_elec_b": None,
            },
        )
        result = validate_run_request(payload)
        assert not result.valid

    def test_odd_total_electrons_is_invalid(self) -> None:
        payload = _run_create(
            algorithm=RunAlgorithm.SQD,
            advanced_config={
                "algorithm": RunAlgorithm.SQD,
                "samples_per_batch": 128,
                "num_batches": 4,
                "max_iterations": 10,
                "num_elec_a": 1,
                "num_elec_b": 2,
            },
        )
        result = validate_run_request(payload)
        assert not result.valid


# ── Contract shape enforcement ────────────────────────────────────────────────


class TestContractShapeEnforcement:
    def test_easy_mode_requires_easy_options(self) -> None:
        payload = _run_create(
            algorithm=RunAlgorithm.VQE,
            mode=RunMode.EASY,
            easy_options=None,
            advanced_config=None,
        )
        result = validate_run_request(payload)
        assert not result.valid
        assert any(error.field == "easy_options" for error in result.errors)

    def test_advanced_mode_requires_advanced_config(self) -> None:
        payload = _run_create(
            algorithm=RunAlgorithm.VQE,
            advanced_config=None,
        )
        result = validate_run_request(payload)
        assert not result.valid
        assert any(error.field == "advanced_config" for error in result.errors)

    def test_advanced_config_algorithm_must_match_top_level(self) -> None:
        payload = _run_create(
            algorithm=RunAlgorithm.VQE,
            advanced_config={
                "algorithm": RunAlgorithm.KQD,
                "krylov_dim": 4,
                "time_step": 0.1,
            },
        )
        result = validate_run_request(payload)
        assert not result.valid
        assert any(error.field == "advanced_config.algorithm" for error in result.errors)

    def test_noise_profile_rejected_for_statevector(self) -> None:
        from app.schemas.run import CustomNoisePreset, NoiseModelSource

        payload = _run_create(
            algorithm=RunAlgorithm.VQE,
            advanced_config={
                "algorithm": RunAlgorithm.VQE,
                "ansatz_name": "EfficientSU2",
                "optimizer_name": "COBYLA",
                "max_iterations": 10,
            },
            noise_profile={
                "source": NoiseModelSource.CUSTOM_PRESET,
                "preset": CustomNoisePreset.DEPOLARIZING_CX,
                "strength": 0.01,
            },
        )
        result = validate_run_request(payload)
        assert not result.valid
        assert any("noise_profile" in e.field for e in result.errors)

    def test_multiplicity_ne_1_is_invalid(self) -> None:
        result = validate_run_request(_vqe_payload(), molecule_multiplicity=3)
        assert not result.valid
        assert any("multiplicity" in e.field for e in result.errors)

    def test_odd_active_space_electrons_is_invalid(self) -> None:
        result = validate_run_request(_vqe_payload(), molecule_active_space_n_electrons=3)
        assert not result.valid
        assert any("n_electrons" in e.field for e in result.errors)
