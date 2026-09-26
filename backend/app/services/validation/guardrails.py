"""Resource guardrails for algorithm-aware run validation."""

from __future__ import annotations

from math import comb

from app.models.enums import BackendTarget, RunAlgorithm
from app.schemas.run_config import (
    KQDAdvancedConfig,
    QFDAdvancedConfig,
    QSEAdvancedConfig,
    SKQDAdvancedConfig,
    SQDAdvancedConfig,
    VQEAdvancedConfig,
)
from app.schemas.run_requests import RunCreate
from app.schemas.run_responses import RunValidationErrorDetail, ValidationErrorCode
from shared.contracts.catalog import PUBLIC_LIMITS

# Keeps optimizer runtime bounded for synchronous validation-era rollout limits.
_MAX_VQE_ITERATIONS = int(PUBLIC_LIMITS["advanced_config.max_iterations"]["maximum"])
_LOWER_ITERATIONS_SUGGESTION = "Lower max_iterations or split the experiment into smaller runs"
# Hard cap for objective calls; most SciPy VQE methods need many calls per optimizer step.
_MAX_VQE_FUNCTION_EVALUATIONS = int(
    PUBLIC_LIMITS["advanced_config.max_function_evaluations"]["maximum"]
)
# Caps per-batch sampling memory before SQD/SKQD determinant filtering expands state.
_MAX_SQD_SAMPLES_PER_BATCH = int(PUBLIC_LIMITS["advanced_config.samples_per_batch"]["maximum"])
# Caps samples collected from each Krylov state independently of SQD batches.
_MAX_SKQD_SAMPLES_PER_STATE = int(PUBLIC_LIMITS["advanced_config.samples_per_state"]["maximum"])
# Bounds repeated SQD/SKQD sampling work so queue estimates remain conservative.
_MAX_SQD_NUM_BATCHES = int(PUBLIC_LIMITS["advanced_config.num_batches"]["maximum"])
# Limits dense Krylov operators to dimensions exercised by current solver coverage.
_MAX_KQD_KRYLOV_DIM = int(PUBLIC_LIMITS["advanced_config.krylov_dim"]["maximum"])
# Bounds QFD time grid size before dense propagation costs dominate.
_MAX_QFD_NUM_TIME_POINTS = int(PUBLIC_LIMITS["advanced_config.num_time_points"]["maximum"])
_QFD_NUM_TIME_POINTS_FIELD = "advanced_config.num_time_points"
# Keeps QSE generalized eigenproblem dimensions within the validated rollout envelope.
_MAX_QSE_SUBSPACE_DIM = int(PUBLIC_LIMITS["advanced_config.max_subspace_dim"]["maximum"])
# Prevents nested QSE reference VQE from exceeding the outer VQE rollout budget shape.
_MAX_QSE_REFERENCE_VQE_ITERATIONS = int(
    PUBLIC_LIMITS["advanced_config.vqe_reference_max_iterations"]["maximum"]
)
# Caps SKQD's extra Krylov basis growth on top of the SQD-selected subspace.
_MAX_SKQD_EXTENSION_DIM = int(PUBLIC_LIMITS["advanced_config.krylov_extension_dim"]["maximum"])
_MAX_KQD_TROTTER_STEPS = int(PUBLIC_LIMITS["advanced_config.trotter_steps"]["maximum"])
_KQD_TROTTER_STEPS_FIELD = "advanced_config.trotter_steps"
# Dense matrix helpers are capped at 12 qubits, i.e. 6 spatial orbitals.
_MAX_DENSE_ACTIVE_ORBITALS = int(PUBLIC_LIMITS["molecule.active_space.n_orbitals.dense"]["maximum"])
_LARGE_SECTOR_ALGORITHMS = {
    RunAlgorithm.KQD,
    RunAlgorithm.QFD,
    RunAlgorithm.QSE,
    RunAlgorithm.SKQD,
}
_MAX_SECTOR_DIMENSION = int(PUBLIC_LIMITS["molecule.active_space.sector_dimension"]["maximum"])
_MAX_INITIAL_POINT_CANDIDATES = int(
    PUBLIC_LIMITS["advanced_config.initial_point_candidates"]["maximum"]
)


def _uses_large_sector_solver(payload: RunCreate) -> bool:
    if payload.algorithm in _LARGE_SECTOR_ALGORITHMS:
        return True
    return isinstance(payload.advanced_config, (QSEAdvancedConfig, SKQDAdvancedConfig))


def _closed_shell_sector_dimension(
    *,
    n_electrons: int | None,
    n_orbitals: int | None,
) -> int | None:
    if n_electrons is None or n_orbitals is None or n_electrons % 2 != 0:
        return None
    n_alpha = n_electrons // 2
    n_beta = n_electrons - n_alpha
    if n_alpha < 0 or n_beta < 0 or n_alpha > n_orbitals or n_beta > n_orbitals:
        return None
    return comb(n_orbitals, n_alpha) * comb(n_orbitals, n_beta)


def _append_error(
    errors: list[RunValidationErrorDetail],
    *,
    field: str,
    code: ValidationErrorCode,
    message: str,
    suggestion: str,
) -> None:
    errors.append(
        RunValidationErrorDetail(
            field=field,
            code=code,
            message=message,
            suggestion=suggestion,
        )
    )


def _append_invalid_range(
    errors: list[RunValidationErrorDetail],
    *,
    field: str,
    message: str,
    suggestion: str,
) -> None:
    _append_error(
        errors,
        field=field,
        code=ValidationErrorCode.INVALID_RANGE,
        message=message,
        suggestion=suggestion,
    )


def _large_kqd_qfd_warning(payload: RunCreate) -> str:
    if payload.backend_target == BackendTarget.AER_SIMULATOR:
        return (
            "KQD/QFD Aer runs above 6 active-space orbitals use branch-state "
            "Estimator matrix elements and keep the projected eigensolve local."
        )
    if payload.backend_target == BackendTarget.IBM_RUNTIME:
        return (
            "KQD/QFD IBM Runtime runs above 6 active-space orbitals use "
            "branch-state Estimator matrix elements and keep the projected "
            "eigensolve local."
        )
    return (
        "KQD/QFD statevector runs above 6 active-space orbitals use the "
        "fixed-particle-sector matrix-free path instead of a dense full-Hilbert Hamiltonian."
    )


def _append_large_sector_guardrail(
    *,
    payload: RunCreate,
    molecule_active_space_n_electrons: int | None,
    molecule_active_space_n_orbitals: int,
    errors: list[RunValidationErrorDetail],
    warnings: list[str],
) -> None:
    sector_dimension = _closed_shell_sector_dimension(
        n_electrons=molecule_active_space_n_electrons,
        n_orbitals=molecule_active_space_n_orbitals,
    )
    if sector_dimension is not None and sector_dimension > _MAX_SECTOR_DIMENSION:
        _append_invalid_range(
            errors,
            field="molecule.active_space",
            message=(
                f"Fixed-sector dimension ({sector_dimension}) exceeds the rollout limit "
                f"of {_MAX_SECTOR_DIMENSION}"
            ),
            suggestion="Reduce active-space electrons/orbitals or use SQD/VQE for this size",
        )
        return

    if payload.algorithm in {RunAlgorithm.KQD, RunAlgorithm.QFD}:
        warnings.append(_large_kqd_qfd_warning(payload))
        return

    warnings.append(
        "QSE/SKQD runs above 6 active-space orbitals use the fixed-particle-sector "
        "matrix-free path."
    )


def _append_active_space_guardrails(
    *,
    payload: RunCreate,
    molecule_active_space_n_electrons: int | None,
    molecule_active_space_n_orbitals: int | None,
    errors: list[RunValidationErrorDetail],
    warnings: list[str],
) -> None:
    if molecule_active_space_n_orbitals is None:
        return

    if (
        _uses_large_sector_solver(payload)
        and molecule_active_space_n_orbitals > _MAX_DENSE_ACTIVE_ORBITALS
    ):
        _append_large_sector_guardrail(
            payload=payload,
            molecule_active_space_n_electrons=molecule_active_space_n_electrons,
            molecule_active_space_n_orbitals=molecule_active_space_n_orbitals,
            errors=errors,
            warnings=warnings,
        )
        return

    if molecule_active_space_n_orbitals > 12:
        warnings.append(
            "active_space.n_orbitals is above 12; VQE, SQD, QSE, and SKQD can be "
            "submitted, but runtime and memory usage may be high"
        )
    elif molecule_active_space_n_orbitals > 8:
        warnings.append(
            "active_space.n_orbitals is in the 9-12 range; sector and sampler paths may be slower"
        )


def _append_vqe_guardrails(
    advanced_config: VQEAdvancedConfig,
    errors: list[RunValidationErrorDetail],
) -> None:
    if advanced_config.max_iterations > _MAX_VQE_ITERATIONS:
        _append_invalid_range(
            errors,
            field="advanced_config.max_iterations",
            message=f"max_iterations exceeds the rollout limit of {_MAX_VQE_ITERATIONS}",
            suggestion=_LOWER_ITERATIONS_SUGGESTION,
        )
    if (
        advanced_config.initial_point_candidates is not None
        and advanced_config.initial_point_candidates > _MAX_INITIAL_POINT_CANDIDATES
    ):
        _append_invalid_range(
            errors,
            field="advanced_config.initial_point_candidates",
            message=(
                "initial_point_candidates exceeds the rollout limit of "
                f"{_MAX_INITIAL_POINT_CANDIDATES}"
            ),
            suggestion=(
                f"Use {_MAX_INITIAL_POINT_CANDIDATES} or fewer VQE starting-point candidates"
            ),
        )
    if (
        advanced_config.max_function_evaluations is not None
        and advanced_config.max_function_evaluations > _MAX_VQE_FUNCTION_EVALUATIONS
    ):
        _append_invalid_range(
            errors,
            field="advanced_config.max_function_evaluations",
            message=(
                "max_function_evaluations exceeds the rollout limit of "
                f"{_MAX_VQE_FUNCTION_EVALUATIONS}"
            ),
            suggestion="Lower max_function_evaluations or split the experiment",
        )


def _append_sqd_limits(
    *,
    samples_per_batch: int,
    num_batches: int,
    max_iterations: int,
    field_prefix: str,
    errors: list[RunValidationErrorDetail],
) -> None:
    if samples_per_batch > _MAX_SQD_SAMPLES_PER_BATCH:
        _append_invalid_range(
            errors,
            field=f"{field_prefix}.samples_per_batch",
            message=(
                f"samples_per_batch exceeds the rollout limit of {_MAX_SQD_SAMPLES_PER_BATCH}"
            ),
            suggestion="Lower samples_per_batch to 2000 or fewer",
        )
    if num_batches > _MAX_SQD_NUM_BATCHES:
        _append_invalid_range(
            errors,
            field=f"{field_prefix}.num_batches",
            message=f"num_batches exceeds the rollout limit of {_MAX_SQD_NUM_BATCHES}",
            suggestion="Lower num_batches to 128 or fewer",
        )
    if max_iterations > _MAX_VQE_ITERATIONS:
        _append_invalid_range(
            errors,
            field=f"{field_prefix}.max_iterations",
            message=f"max_iterations exceeds the rollout limit of {_MAX_VQE_ITERATIONS}",
            suggestion=_LOWER_ITERATIONS_SUGGESTION,
        )


def _append_sqd_guardrails(
    advanced_config: SQDAdvancedConfig,
    errors: list[RunValidationErrorDetail],
) -> None:
    _append_sqd_limits(
        samples_per_batch=advanced_config.samples_per_batch,
        num_batches=advanced_config.num_batches,
        max_iterations=advanced_config.max_iterations,
        field_prefix="advanced_config",
        errors=errors,
    )


def _append_kqd_guardrails(
    advanced_config: KQDAdvancedConfig,
    errors: list[RunValidationErrorDetail],
) -> None:
    if advanced_config.krylov_dim > _MAX_KQD_KRYLOV_DIM:
        _append_invalid_range(
            errors,
            field="advanced_config.krylov_dim",
            message=f"krylov_dim exceeds the rollout limit of {_MAX_KQD_KRYLOV_DIM}",
            suggestion="Lower krylov_dim to 64 or fewer",
        )
    if advanced_config.trotter_steps > _MAX_KQD_TROTTER_STEPS:
        _append_invalid_range(
            errors,
            field=_KQD_TROTTER_STEPS_FIELD,
            message=f"trotter_steps exceeds the rollout limit of {_MAX_KQD_TROTTER_STEPS}",
            suggestion="Lower trotter_steps to 32 or fewer",
        )


def _append_qfd_guardrails(
    advanced_config: QFDAdvancedConfig,
    errors: list[RunValidationErrorDetail],
) -> None:
    if advanced_config.qfd_variant == "qfd_original_symmetric" and (
        advanced_config.num_time_points < 3 or advanced_config.num_time_points % 2 == 0
    ):
        _append_invalid_range(
            errors,
            field=_QFD_NUM_TIME_POINTS_FIELD,
            message=(
                "qfd_original_symmetric requires an odd num_time_points value of at least 3"
            ),
            suggestion="Use 3, 5, 7, or another odd number of time points",
        )
    if advanced_config.num_time_points > _MAX_QFD_NUM_TIME_POINTS:
        _append_invalid_range(
            errors,
            field=_QFD_NUM_TIME_POINTS_FIELD,
            message=f"num_time_points exceeds the rollout limit of {_MAX_QFD_NUM_TIME_POINTS}",
            suggestion="Lower num_time_points to 128 or fewer",
        )
    if advanced_config.trotter_steps > _MAX_KQD_TROTTER_STEPS:
        _append_invalid_range(
            errors,
            field=_KQD_TROTTER_STEPS_FIELD,
            message=f"trotter_steps exceeds the rollout limit of {_MAX_KQD_TROTTER_STEPS}",
            suggestion="Lower trotter_steps to 32 or fewer",
        )


def _append_qse_reference_guardrails(
    *,
    advanced_config: QSEAdvancedConfig,
    molecule_active_space_n_orbitals: int | None,
    is_measured_target: bool,
    errors: list[RunValidationErrorDetail],
) -> None:
    if is_measured_target and advanced_config.reference_method != "hf":
        _append_error(
            errors,
            field="advanced_config.reference_method",
            code=ValidationErrorCode.UNSUPPORTED_OPTION,
            message=(
                "Measured QSE on noisy Aer and IBM Runtime supports "
                "reference_method='hf' only because the measured circuit prepares "
                "the Hartree-Fock reference state."
            ),
            suggestion=(
                "Use reference_method='hf' for measured QSE, or use statevector or "
                "ideal Aer for a non-HF reference."
            ),
        )
    if (
        advanced_config.reference_method == "provided_state"
        and not advanced_config.provided_state_vector
    ):
        _append_error(
            errors,
            field="advanced_config.provided_state_vector",
            code=ValidationErrorCode.MISSING_REQUIRED,
            message="QSE provided_state reference requires advanced_config.provided_state_vector",
            suggestion="Provide a normalized state vector matching the active Hilbert space",
        )
    if (
        advanced_config.reference_method == "provided_sector"
        and not advanced_config.provided_sector_amplitudes
    ):
        _append_error(
            errors,
            field="advanced_config.provided_sector_amplitudes",
            code=ValidationErrorCode.MISSING_REQUIRED,
            message=(
                "QSE provided_sector reference requires advanced_config.provided_sector_amplitudes"
            ),
            suggestion="Provide sparse determinant amplitudes or use reference_method='hf'",
        )
    if (
        molecule_active_space_n_orbitals is not None
        and molecule_active_space_n_orbitals > _MAX_DENSE_ACTIVE_ORBITALS
        and advanced_config.reference_method in {"vqe", "provided_state"}
    ):
        _append_error(
            errors,
            field="advanced_config.reference_method",
            code=ValidationErrorCode.UNSUPPORTED_OPTION,
            message=(
                "Large-active-space QSE supports reference_method='hf' or "
                "'provided_sector'. VQE and full provided_state references still "
                f"require {_MAX_DENSE_ACTIVE_ORBITALS} active-space orbitals or fewer."
            ),
            suggestion=(
                "Use QSE reference_method='hf', provide sparse sector amplitudes, "
                "or reduce the active space."
            ),
        )


def _append_qse_ignored_option_warnings(
    advanced_config: QSEAdvancedConfig,
    warnings: list[str],
) -> None:
    if (
        advanced_config.reference_method != "provided_state"
        and advanced_config.provided_state_vector is not None
    ):
        warnings.append(
            "QSE provided_state_vector is ignored unless reference_method='provided_state'."
        )
    if (
        advanced_config.reference_method != "provided_sector"
        and advanced_config.provided_sector_amplitudes is not None
    ):
        warnings.append(
            "QSE provided_sector_amplitudes is ignored unless reference_method='provided_sector'."
        )
    if (
        advanced_config.reference_method != "vqe"
        and advanced_config.vqe_reference_max_iterations is not None
    ):
        warnings.append(
            "QSE vqe_reference_max_iterations is ignored unless reference_method='vqe'."
        )
    if (
        advanced_config.reference_method != "vqe"
        and advanced_config.vqe_reference_seed is not None
    ):
        warnings.append("QSE vqe_reference_seed is ignored unless reference_method='vqe'.")


def _append_qse_guardrails(
    *,
    advanced_config: QSEAdvancedConfig,
    molecule_active_space_n_electrons: int | None,
    molecule_active_space_n_orbitals: int | None,
    errors: list[RunValidationErrorDetail],
    warnings: list[str],
    is_measured_target: bool = False,
) -> None:
    if (
        advanced_config.max_subspace_dim is not None
        and advanced_config.max_subspace_dim > _MAX_QSE_SUBSPACE_DIM
    ):
        _append_invalid_range(
            errors,
            field="advanced_config.max_subspace_dim",
            message=f"max_subspace_dim exceeds the rollout limit of {_MAX_QSE_SUBSPACE_DIM}",
            suggestion="Lower max_subspace_dim to 96 or fewer",
        )
    _append_qse_reference_guardrails(
        advanced_config=advanced_config,
        molecule_active_space_n_orbitals=molecule_active_space_n_orbitals,
        is_measured_target=is_measured_target,
        errors=errors,
    )
    _append_qse_ignored_option_warnings(advanced_config, warnings)
    if not is_measured_target:
        warnings.append(
            "Current QSE uses local exact or sector emulation. It does not measure projected "
            "matrix elements on the selected backend."
        )
    if (
        advanced_config.reference_method == "hf"
        and advanced_config.excitation_level == "singles"
        and molecule_active_space_n_electrons == 2
        and molecule_active_space_n_orbitals == 2
    ):
        warnings.append(
            "QSE Hartree-Fock singles in a 2e/2o active space cannot include the "
            "correlation double excitation. This setting is not accuracy-capable for the "
            "H2 benchmark; use excitation_level='singles_doubles'."
        )
    if (
        advanced_config.vqe_reference_max_iterations is not None
        and advanced_config.vqe_reference_max_iterations > _MAX_QSE_REFERENCE_VQE_ITERATIONS
    ):
        _append_invalid_range(
            errors,
            field="advanced_config.vqe_reference_max_iterations",
            message=(
                "vqe_reference_max_iterations exceeds the rollout limit of "
                f"{_MAX_QSE_REFERENCE_VQE_ITERATIONS}"
            ),
            suggestion="Lower QSE reference VQE iterations to 1000 or fewer",
        )


def _append_skqd_guardrails(
    advanced_config: SKQDAdvancedConfig,
    errors: list[RunValidationErrorDetail],
) -> None:
    if advanced_config.krylov_extension_dim > _MAX_SKQD_EXTENSION_DIM:
        _append_invalid_range(
            errors,
            field="advanced_config.krylov_extension_dim",
            message=(
                f"krylov_extension_dim exceeds the rollout limit of {_MAX_SKQD_EXTENSION_DIM}"
            ),
            suggestion="Lower krylov_extension_dim to 32 or fewer",
        )

    if advanced_config.samples_per_state > _MAX_SKQD_SAMPLES_PER_STATE:
        _append_invalid_range(
            errors,
            field="advanced_config.samples_per_state",
            message=(
                "samples_per_state exceeds the rollout limit of "
                f"{_MAX_SKQD_SAMPLES_PER_STATE}"
            ),
            suggestion="Lower samples_per_state to 4096 or fewer",
        )


def _append_resource_guardrail_messages(
    *,
    payload: RunCreate,
    molecule_active_space_n_electrons: int | None,
    molecule_active_space_n_orbitals: int | None,
    errors: list[RunValidationErrorDetail],
    warnings: list[str],
) -> None:
    """Append hard limits and heuristic warnings for resource usage."""
    _append_active_space_guardrails(
        payload=payload,
        molecule_active_space_n_electrons=molecule_active_space_n_electrons,
        molecule_active_space_n_orbitals=molecule_active_space_n_orbitals,
        errors=errors,
        warnings=warnings,
    )

    advanced_config = payload.advanced_config
    if isinstance(advanced_config, VQEAdvancedConfig):
        _append_vqe_guardrails(advanced_config, errors)

    if isinstance(advanced_config, SQDAdvancedConfig):
        _append_sqd_guardrails(advanced_config, errors)

    if isinstance(advanced_config, KQDAdvancedConfig):
        _append_kqd_guardrails(advanced_config, errors)

    if isinstance(advanced_config, QFDAdvancedConfig):
        _append_qfd_guardrails(advanced_config, errors)

    if isinstance(advanced_config, QSEAdvancedConfig):
        qse_measured_target = payload.backend_target == BackendTarget.IBM_RUNTIME or (
            payload.backend_target == BackendTarget.AER_SIMULATOR
            and payload.noise_profile is not None
        )
        _append_qse_guardrails(
            advanced_config=advanced_config,
            molecule_active_space_n_electrons=molecule_active_space_n_electrons,
            molecule_active_space_n_orbitals=molecule_active_space_n_orbitals,
            errors=errors,
            warnings=warnings,
            is_measured_target=qse_measured_target,
        )

    if isinstance(advanced_config, SKQDAdvancedConfig):
        _append_skqd_guardrails(advanced_config, errors)


__all__ = [
    "_MAX_KQD_KRYLOV_DIM",
    "_MAX_KQD_TROTTER_STEPS",
    "_MAX_QFD_NUM_TIME_POINTS",
    "_MAX_QSE_REFERENCE_VQE_ITERATIONS",
    "_MAX_QSE_SUBSPACE_DIM",
    "_MAX_SECTOR_DIMENSION",
    "_MAX_SKQD_EXTENSION_DIM",
    "_MAX_SKQD_SAMPLES_PER_STATE",
    "_MAX_SQD_NUM_BATCHES",
    "_MAX_SQD_SAMPLES_PER_BATCH",
    "_MAX_VQE_FUNCTION_EVALUATIONS",
    "_MAX_VQE_ITERATIONS",
    "_append_resource_guardrail_messages",
]
