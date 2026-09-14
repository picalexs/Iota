"""Backend capability, credential, and projected-path validation policies."""

from __future__ import annotations

from app.config import BackendCapability
from app.models.enums import BackendTarget, EasyGoal, RunAlgorithm, RunMode
from app.schemas.run_config import (
    BackendSelectionPolicy,
    KQDAdvancedConfig,
    NoiseModelSource,
    QFDAdvancedConfig,
)
from app.schemas.run_requests import RunCreate
from app.schemas.run_responses import RunValidationErrorDetail, ValidationErrorCode
from app.services.basis_sets import SUPPORTED_BASIS_SET_IDS

_IBM_RUNTIME_ALGORITHMS = frozenset(
    {
        RunAlgorithm.VQE,
        RunAlgorithm.SQD,
        RunAlgorithm.QSE,
        RunAlgorithm.SKQD,
        RunAlgorithm.KQD,
        RunAlgorithm.QFD,
    }
)
_DENSE_CLASSICAL_ALGORITHMS = frozenset({RunAlgorithm.KQD, RunAlgorithm.QFD})
_AER_STATEVECTOR_METHODS = frozenset({"automatic", "statevector", "matrix_product_state"})
_MAX_HARDWARE_MATRIX_DIM = 8
_MAX_NOISY_AER_PROJECTED_MATRIX_ORBITALS = 6
_MAX_IBM_PROJECTED_MATRIX_ORBITALS = _MAX_NOISY_AER_PROJECTED_MATRIX_ORBITALS
_KQD_EASY_DIMS = {
    EasyGoal.FASTEST: 2,
    EasyGoal.BALANCED: 8,
    EasyGoal.BEST_ACCURACY: 8,
}
_QFD_EASY_DIMS = {
    EasyGoal.FASTEST: 2,
    EasyGoal.BALANCED: 8,
    EasyGoal.BEST_ACCURACY: 8,
}

__all__ = [
    "_append_aer_matrix_validation_messages",
    "_append_backend_credential_validation_messages",
    "_append_backend_target_validation_messages",
    "_append_basis_set_validation_messages",
    "_append_ibm_runtime_validation_messages",
    "_append_projected_matrix_validation_messages",
]


def _append_basis_set_validation_messages(
    payload: RunCreate,
    *,
    errors: list[RunValidationErrorDetail],
) -> None:
    basis = payload.effective_basis_set()
    if basis.strip().lower() not in SUPPORTED_BASIS_SET_IDS:
        errors.append(
            RunValidationErrorDetail(
                field="basis_set_override",
                code=ValidationErrorCode.UNSUPPORTED_OPTION,
                message=f"Basis set '{basis}' is not supported by this app.",
                suggestion="Choose one of the selectable basis sets in the run form.",
            )
        )


def _append_backend_target_validation_messages(
    payload: RunCreate,
    *,
    errors: list[RunValidationErrorDetail],
    capability: BackendCapability,
) -> None:
    if not capability.enabled:
        errors.append(
            RunValidationErrorDetail(
                field="backend_target",
                code=ValidationErrorCode.UNSUPPORTED_OPTION,
                message=f"backend_target '{payload.backend_target.value}' is not enabled",
                suggestion="Use 'statevector' in current rollout",
            )
        )

    if payload.noise_profile is not None and not capability.supports_noise_profile:
        errors.append(
            RunValidationErrorDetail(
                field="noise_profile",
                code=ValidationErrorCode.UNSUPPORTED_OPTION,
                message="noise_profile is not supported by selected backend_target",
                suggestion="Remove noise_profile or select a noise-capable backend when enabled",
            )
        )


def _is_large_aer_projected_matrix_run(
    payload: RunCreate,
    *,
    molecule_active_space_n_orbitals: int | None,
) -> bool:
    return (
        payload.backend_target == BackendTarget.AER_SIMULATOR
        and payload.algorithm in _DENSE_CLASSICAL_ALGORITHMS
        and payload.noise_profile is None
        and molecule_active_space_n_orbitals is not None
        and molecule_active_space_n_orbitals > 6
    )


def _is_noisy_aer_projected_matrix_run(payload: RunCreate) -> bool:
    return (
        payload.backend_target == BackendTarget.AER_SIMULATOR
        and payload.algorithm in _DENSE_CLASSICAL_ALGORITHMS
        and payload.noise_profile is not None
    )


def _is_aer_projected_matrix_run(
    payload: RunCreate,
    *,
    molecule_active_space_n_orbitals: int | None,
) -> bool:
    return _is_noisy_aer_projected_matrix_run(payload) or _is_large_aer_projected_matrix_run(
        payload,
        molecule_active_space_n_orbitals=molecule_active_space_n_orbitals,
    )


def _is_ibm_projected_matrix_run(payload: RunCreate) -> bool:
    return (
        payload.backend_target == BackendTarget.IBM_RUNTIME
        and payload.algorithm in _DENSE_CLASSICAL_ALGORITHMS
    )


def _easy_projected_matrix_dimension(payload: RunCreate) -> tuple[int, str] | None:
    if payload.mode != RunMode.EASY or payload.easy_options is None:
        return None

    if payload.algorithm == RunAlgorithm.KQD:
        return _KQD_EASY_DIMS[payload.easy_options.goal], "Krylov states"
    return _QFD_EASY_DIMS[payload.easy_options.goal], "time points"


def _append_projected_matrix_easy_messages(
    payload: RunCreate,
    *,
    errors: list[RunValidationErrorDetail],
    projected_target_label: str,
) -> None:
    easy_dimension = _easy_projected_matrix_dimension(payload)
    if easy_dimension is None:
        return

    dimension, field_label = easy_dimension
    if dimension <= _MAX_HARDWARE_MATRIX_DIM:
        return

    errors.append(
        RunValidationErrorDetail(
            field="easy_options.goal",
            code=ValidationErrorCode.INVALID_RANGE,
            message=(
                f"{payload.algorithm.value.upper()} {projected_target_label} "
                "matrix-element "
                f"runs are capped at {_MAX_HARDWARE_MATRIX_DIM} {field_label}; "
                f"the selected easy goal expands to {dimension}"
            ),
            suggestion="Use the fastest easy goal or advanced mode with a smaller basis.",
        )
    )


def _append_projected_matrix_kqd_messages(
    advanced_config: KQDAdvancedConfig,
    *,
    errors: list[RunValidationErrorDetail],
    projected_target_label: str,
) -> None:
    if advanced_config.krylov_dim <= _MAX_HARDWARE_MATRIX_DIM:
        return

    errors.append(
        RunValidationErrorDetail(
            field="advanced_config.krylov_dim",
            code=ValidationErrorCode.INVALID_RANGE,
            message=(
                f"KQD {projected_target_label} matrix-element runs are capped "
                f"at {_MAX_HARDWARE_MATRIX_DIM} Krylov states"
            ),
            suggestion="Lower krylov_dim or use statevector for local sector runs.",
        )
    )


def _append_projected_matrix_qfd_messages(
    advanced_config: QFDAdvancedConfig,
    *,
    errors: list[RunValidationErrorDetail],
    projected_target_label: str,
) -> None:
    num_time_points = int(advanced_config.num_time_points)
    if num_time_points <= _MAX_HARDWARE_MATRIX_DIM:
        return

    errors.append(
        RunValidationErrorDetail(
            field="advanced_config.num_time_points",
            code=ValidationErrorCode.INVALID_RANGE,
            message=(
                f"QFD {projected_target_label} matrix-element runs are capped "
                f"at {_MAX_HARDWARE_MATRIX_DIM} time points"
            ),
            suggestion="Lower num_time_points or use statevector for local sector runs.",
        )
    )


def _append_projected_matrix_active_space_messages(
    *,
    warnings: list[str],
    molecule_active_space_n_orbitals: int | None,
    ibm_projected_matrix_run: bool,
    noisy_aer_projected_matrix_run: bool,
) -> None:
    if molecule_active_space_n_orbitals is None:
        return
    if noisy_aer_projected_matrix_run and (
        molecule_active_space_n_orbitals > _MAX_NOISY_AER_PROJECTED_MATRIX_ORBITALS
    ):
        warnings.append(
            "Noisy Aer KQD/QFD projected-matrix runs are limited to active spaces up to "
            f"{_MAX_NOISY_AER_PROJECTED_MATRIX_ORBITALS} orbitals in the current rollout. "
            "This configuration is accepted but will be marked EXCLUDED at execution "
            "instead of running. Use statevector or ideal Aer for larger local runs."
        )
    if ibm_projected_matrix_run and (
        molecule_active_space_n_orbitals > _MAX_IBM_PROJECTED_MATRIX_ORBITALS
    ):
        warnings.append(
            "IBM Runtime KQD/QFD projected-matrix runs are limited to active spaces up to "
            f"{_MAX_IBM_PROJECTED_MATRIX_ORBITALS} orbitals in the current rollout. "
            "This configuration is accepted but will be marked EXCLUDED at execution "
            "instead of running. Use statevector or ideal Aer for larger local runs."
        )


def _append_projected_matrix_warning(
    *,
    warnings: list[str],
    ibm_projected_matrix_run: bool,
    noisy_aer_projected_matrix_run: bool,
) -> None:
    if ibm_projected_matrix_run:
        warnings.append(
            "KQD/QFD IBM Runtime execution measures projected Hamiltonian and overlap "
            "matrix elements with branch-state Estimator circuits; the final generalized "
            "eigensolve remains local."
        )
        return

    if noisy_aer_projected_matrix_run:
        warnings.append(
            "KQD/QFD noisy Aer execution measures projected Hamiltonian and overlap "
            "matrix elements with local Aer Estimator branch-state circuits using the "
            "configured Aer noise model; the final generalized eigensolve remains local."
        )
        return

    warnings.append(
        "KQD/QFD large ideal Aer execution stays local and uses the fixed-particle-"
        "sector matrix-free path instead of projected matrix-element Estimator jobs."
    )


def _append_projected_matrix_validation_messages(
    payload: RunCreate,
    *,
    errors: list[RunValidationErrorDetail],
    warnings: list[str],
    molecule_active_space_n_orbitals: int | None,
) -> None:
    aer_projected_matrix_run = _is_aer_projected_matrix_run(
        payload,
        molecule_active_space_n_orbitals=molecule_active_space_n_orbitals,
    )
    noisy_aer_projected_matrix_run = _is_noisy_aer_projected_matrix_run(payload)
    ibm_projected_matrix_run = _is_ibm_projected_matrix_run(payload)
    if not (ibm_projected_matrix_run or aer_projected_matrix_run):
        return

    projected_target_label = "IBM Runtime" if ibm_projected_matrix_run else "Aer"
    _append_projected_matrix_easy_messages(
        payload,
        errors=errors,
        projected_target_label=projected_target_label,
    )
    if isinstance(payload.advanced_config, KQDAdvancedConfig):
        _append_projected_matrix_kqd_messages(
            payload.advanced_config,
            errors=errors,
            projected_target_label=projected_target_label,
        )
    if isinstance(payload.advanced_config, QFDAdvancedConfig):
        _append_projected_matrix_qfd_messages(
            payload.advanced_config,
            errors=errors,
            projected_target_label=projected_target_label,
        )
    _append_projected_matrix_active_space_messages(
        warnings=warnings,
        molecule_active_space_n_orbitals=molecule_active_space_n_orbitals,
        ibm_projected_matrix_run=ibm_projected_matrix_run,
        noisy_aer_projected_matrix_run=noisy_aer_projected_matrix_run,
    )
    _append_projected_matrix_warning(
        warnings=warnings,
        ibm_projected_matrix_run=ibm_projected_matrix_run,
        noisy_aer_projected_matrix_run=noisy_aer_projected_matrix_run,
    )


def _append_aer_matrix_validation_messages(
    payload: RunCreate,
    *,
    errors: list[RunValidationErrorDetail],
    warnings: list[str],
    molecule_active_space_n_orbitals: int | None,
) -> None:
    if payload.backend_target != BackendTarget.AER_SIMULATOR:
        return
    if payload.algorithm not in _DENSE_CLASSICAL_ALGORITHMS:
        return

    aer_projected_matrix_run = _is_aer_projected_matrix_run(
        payload,
        molecule_active_space_n_orbitals=molecule_active_space_n_orbitals,
    )
    if (
        payload.noise_profile is None
        and payload.backend_options.aer_method not in _AER_STATEVECTOR_METHODS
    ):
        errors.append(
            RunValidationErrorDetail(
                field="backend_options.aer_method",
                code=ValidationErrorCode.UNSUPPORTED_OPTION,
                message=(
                    "KQD/QFD Aer execution requires aer_method 'automatic', "
                    "'statevector', or 'matrix_product_state'."
                ),
                suggestion="Use aer_method='automatic' or 'statevector'.",
            )
        )
    if not aer_projected_matrix_run:
        if (
            payload.noise_profile is None
            and molecule_active_space_n_orbitals is not None
            and molecule_active_space_n_orbitals > 6
        ):
            warnings.append(
                "KQD/QFD large ideal Aer execution stays local and uses the fixed-particle-"
                "sector matrix-free path instead of projected matrix-element Estimator jobs."
            )
        else:
            warnings.append(
                "KQD/QFD Aer execution uses AerSimulator for time-evolution state "
                "propagation; projected matrices and the generalized eigensolve remain local."
            )


def _append_ibm_runtime_validation_messages(
    payload: RunCreate,
    *,
    errors: list[RunValidationErrorDetail],
    require_ibm_confirmation: bool,
    ibm_credentials_available: bool | None,
) -> None:
    if payload.backend_target != BackendTarget.IBM_RUNTIME:
        return

    if (
        payload.algorithm not in _IBM_RUNTIME_ALGORITHMS
        and payload.algorithm not in _DENSE_CLASSICAL_ALGORITHMS
    ):
        errors.append(
            RunValidationErrorDetail(
                field="algorithm",
                code=ValidationErrorCode.INCOMPATIBLE_BACKEND,
                message=(
                    f"algorithm '{payload.algorithm.value}' does not have an IBM Runtime "
                    "hardware execution path"
                ),
                suggestion=(
                    "Use statevector/aer_simulator for this algorithm, or select vqe/sqd/qse/skqd."
                ),
            )
        )

    if require_ibm_confirmation and not payload.ibm_runtime_confirmed:
        errors.append(
            RunValidationErrorDetail(
                field="ibm_runtime_confirmed",
                code=ValidationErrorCode.MISSING_REQUIRED,
                message="Confirm IBM Runtime submission before creating a hardware run.",
                suggestion="Use the confirmation dialog in the run form.",
            )
        )

    has_ibm_credentials = bool(ibm_credentials_available)
    if not has_ibm_credentials:
        errors.append(
            RunValidationErrorDetail(
                field="ibm_runtime_credentials",
                code=ValidationErrorCode.MISSING_REQUIRED,
                message="IBM Quantum credentials are not connected.",
                suggestion="Save an IBM profile in Settings and make it active before trying again.",
            )
        )

    if (
        payload.backend_options.selection_policy == BackendSelectionPolicy.MANUAL
        and not payload.backend_options.backend_name
    ):
        errors.append(
            RunValidationErrorDetail(
                field="backend_options.backend_name",
                code=ValidationErrorCode.MISSING_REQUIRED,
                message=(
                    "backend_options.backend_name is required for manual IBM Runtime selection"
                ),
                suggestion="Set backend_name or choose selection_policy='least_busy'.",
            )
        )


def _append_backend_credential_validation_messages(
    payload: RunCreate,
    *,
    errors: list[RunValidationErrorDetail],
    ibm_credentials_available: bool | None,
) -> None:
    needs_backend_derived_noise_credentials = (
        payload.backend_target == BackendTarget.AER_SIMULATOR
        and payload.noise_profile is not None
        and payload.noise_profile.source == NoiseModelSource.BACKEND_DERIVED
    )
    if needs_backend_derived_noise_credentials and not bool(ibm_credentials_available):
        errors.append(
            RunValidationErrorDetail(
                field="noise_profile",
                code=ValidationErrorCode.MISSING_REQUIRED,
                message="backend_derived Aer noise requires an active saved IBM credential profile.",
                suggestion=(
                    "Save an IBM profile in Settings and make it active before using backend-derived noise."
                ),
            )
        )
