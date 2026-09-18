"""Algorithm-specific validation policies for run requests."""

from __future__ import annotations

import logging

from app.models.enums import BackendTarget, RunAlgorithm
from app.schemas.run_config import (
    KQDAdvancedConfig,
    SKQDAdvancedConfig,
    SQDAdvancedConfig,
    VQEAdvancedConfig,
)
from app.schemas.run_requests import RunCreate
from app.schemas.run_responses import RunValidationErrorDetail, ValidationErrorCode
from shared.contracts.registry_metadata import resolve_ansatz_id

_SQD_ELECTRON_FIELD = "advanced_config.num_elec_a|num_elec_b"
_SKQD_BASE_ELECTRON_FIELD = "advanced_config.base_sampling_options.num_elec_a|num_elec_b"
logger = logging.getLogger(__name__)

__all__ = [
    "_append_kqd_validation_messages",
    "_append_qse_execution_validation_messages",
    "_append_qse_runtime_path_warning",
    "_append_skqd_validation_messages",
    "_append_sqd_validation_messages",
    "_append_vqe_validation_messages",
    "_number_preserving_parameter_count",
    "_resolve_vqe_parameter_count",
]


def _build_vqe_validation_ansatz(
    *,
    ansatz_name: str,
    num_qubits: int,
    reps: int,
):
    """Build the selected VQE ansatz for validation-time parameter counting."""
    from qiskit.circuit.library import efficient_su2, n_local, real_amplitudes

    normalized = resolve_ansatz_id(ansatz_name)
    if normalized == "realamplitudes":
        return real_amplitudes(num_qubits=num_qubits, reps=reps)
    if normalized == "twolocal":
        return n_local(
            num_qubits=num_qubits,
            rotation_blocks=["ry", "rz"],
            entanglement_blocks="cx",
            reps=reps,
        )
    if normalized == "efficientsu2":
        return efficient_su2(num_qubits=num_qubits, reps=reps)
    raise ValueError(f"Unsupported ansatz '{ansatz_name}'")


def _number_preserving_parameter_count(*, num_orbitals: int, reps: int) -> int:
    """Count same-spin and paired double-excitation gates."""
    return sum(
        2 * len(range(layer % 2, num_orbitals - 1, 2))
        + num_orbitals * (num_orbitals - 1) // 2
        for layer in range(max(1, reps))
    )


def _append_sqd_validation_messages(
    payload: RunCreate,
    *,
    errors: list[RunValidationErrorDetail],
    molecule_active_space_n_electrons: int | None,
) -> None:
    if not isinstance(payload.advanced_config, SQDAdvancedConfig):
        return

    if (payload.advanced_config.num_elec_a is None) != (payload.advanced_config.num_elec_b is None):
        errors.append(
            RunValidationErrorDetail(
                field=_SQD_ELECTRON_FIELD,
                code=ValidationErrorCode.MISSING_REQUIRED,
                message="Provide both SQD electron counts together, or omit both",
            )
        )

    if (
        payload.advanced_config.num_elec_a is not None
        and payload.advanced_config.num_elec_b is not None
        and molecule_active_space_n_electrons is not None
        and payload.advanced_config.num_elec_a + payload.advanced_config.num_elec_b
        != molecule_active_space_n_electrons
    ):
        errors.append(
            RunValidationErrorDetail(
                field=_SQD_ELECTRON_FIELD,
                code=ValidationErrorCode.INCOMPATIBLE_BACKEND,
                message="SQD electron counts must match molecule active-space electrons",
            )
        )

    if (
        payload.advanced_config.num_elec_a is not None
        and payload.advanced_config.num_elec_b is not None
        and (payload.advanced_config.num_elec_a + payload.advanced_config.num_elec_b) % 2 != 0
    ):
        errors.append(
            RunValidationErrorDetail(
                field="advanced_config.num_elec_a|num_elec_b",
                code=ValidationErrorCode.INCOMPATIBLE_BACKEND,
                message=("SQD electron counts must sum to an even number in closed-shell rollout"),
            )
        )

    if (
        payload.advanced_config.symmetrize_spin
        and payload.advanced_config.num_elec_a is not None
        and payload.advanced_config.num_elec_b is not None
        and payload.advanced_config.num_elec_a != payload.advanced_config.num_elec_b
    ):
        errors.append(
            RunValidationErrorDetail(
                field="advanced_config.symmetrize_spin",
                code=ValidationErrorCode.INCOMPATIBLE_BACKEND,
                message=("SQD symmetrize_spin requires equal alpha and beta electron counts"),
            )
        )
    if (
        payload.advanced_config.symmetrize_spin
        and isinstance(payload.advanced_config.max_dim, tuple)
        and payload.advanced_config.max_dim[0] != payload.advanced_config.max_dim[1]
    ):
        errors.append(
            RunValidationErrorDetail(
                field="advanced_config.max_dim",
                code=ValidationErrorCode.INVALID_RANGE,
                message=("SQD symmetrize_spin requires identical alpha and beta max_dim limits"),
            )
        )


def _resolve_vqe_parameter_count(
    payload: RunCreate,
    *,
    molecule_active_space_n_orbitals: int | None,
) -> int | None:
    if (
        not isinstance(payload.advanced_config, VQEAdvancedConfig)
        or molecule_active_space_n_orbitals is None
    ):
        return None

    normalized = resolve_ansatz_id(payload.advanced_config.ansatz_name)
    if normalized == "numberpreserving":
        return _number_preserving_parameter_count(
            num_orbitals=molecule_active_space_n_orbitals,
            reps=payload.advanced_config.reps,
        )

    try:
        ansatz = _build_vqe_validation_ansatz(
            ansatz_name=payload.advanced_config.ansatz_name,
            num_qubits=2 * molecule_active_space_n_orbitals,
            reps=payload.advanced_config.reps,
        )
    except (TypeError, ValueError) as exc:
        logger.debug(
            "VQE ansatz parameter count unavailable (%s); skipping length checks",
            type(exc).__name__,
        )
        return None
    return int(getattr(ansatz, "num_parameters", 0) or 0)


def _append_vqe_validation_messages(
    payload: RunCreate,
    *,
    errors: list[RunValidationErrorDetail],
    molecule_active_space_n_orbitals: int | None,
) -> None:
    if not isinstance(payload.advanced_config, VQEAdvancedConfig):
        return

    num_parameters = _resolve_vqe_parameter_count(
        payload,
        molecule_active_space_n_orbitals=molecule_active_space_n_orbitals,
    )
    if num_parameters is None:
        return

    initial_parameters = payload.advanced_config.initial_parameters
    if initial_parameters is not None and len(initial_parameters) != num_parameters:
        errors.append(
            RunValidationErrorDetail(
                field="advanced_config.initial_parameters",
                code=ValidationErrorCode.INVALID_RANGE,
                message=(
                    "VQE initial_parameters must match the ansatz parameter count "
                    f"({num_parameters})"
                ),
                suggestion="Regenerate the starting vector for the selected ansatz and reps.",
            )
        )

    parameter_bounds = payload.advanced_config.parameter_bounds
    if parameter_bounds is None:
        return
    if len(parameter_bounds) != num_parameters:
        errors.append(
            RunValidationErrorDetail(
                field="advanced_config.parameter_bounds",
                code=ValidationErrorCode.INVALID_RANGE,
                message=(
                    "VQE parameter_bounds must contain one [lower, upper] pair per ansatz "
                    f"parameter ({num_parameters})"
                ),
                suggestion="Provide exactly one bounds pair for each ansatz parameter.",
            )
        )
        return

    for index, bounds in enumerate(parameter_bounds):
        if len(bounds) != 2 or bounds[0] > bounds[1]:
            errors.append(
                RunValidationErrorDetail(
                    field=f"advanced_config.parameter_bounds.{index}",
                    code=ValidationErrorCode.INVALID_RANGE,
                    message=(
                        "Each VQE parameter_bounds entry must be [lower, upper] with lower <= upper"
                    ),
                )
            )


def _append_kqd_validation_messages(
    payload: RunCreate,
    *,
    errors: list[RunValidationErrorDetail],
    warnings: list[str],
) -> None:
    if not isinstance(payload.advanced_config, KQDAdvancedConfig):
        return

    if (
        payload.advanced_config.evolution_method == "exact"
        and payload.advanced_config.trotter_steps != 1
    ):
        warnings.append("KQD trotter_steps is ignored when evolution_method='exact'.")
    if (
        payload.advanced_config.evolution_method == "exact"
        and payload.backend_target == BackendTarget.AER_SIMULATOR
        and payload.noise_profile is None
    ):
        warnings.append(
            "KQD exact evolution uses local exact matrix evolution; the Aer simulator "
            "does not execute the time-evolution path."
        )
    if (
        payload.advanced_config.evolution_method == "exact"
        and payload.backend_target == BackendTarget.IBM_RUNTIME
    ):
        warnings.append(
            "KQD IBM Runtime matrix-element circuits use Pauli Trotter evolution; "
            "the dense exact-evolution shortcut is only available for statevector runs."
        )
    if (
        payload.advanced_config.evolution_method == "exact"
        and (
            payload.backend_target == BackendTarget.IBM_RUNTIME
            or (
                payload.backend_target == BackendTarget.AER_SIMULATOR
                and payload.noise_profile is not None
            )
        )
    ):
        errors.append(
            RunValidationErrorDetail(
                field="advanced_config.evolution_method",
                code=ValidationErrorCode.UNSUPPORTED_OPTION,
                message=(
                    "Noisy or hardware KQD projected matrix elements require "
                    "evolution_method='trotter'; exact evolution is only available "
                    "for local exact emulation."
                ),
                suggestion=(
                    "Use evolution_method='trotter' and set trotter_steps explicitly, "
                    "or use statevector without a noise profile for exact emulation."
                ),
            )
        )


_MAX_NOISY_AER_PROJECTED_MATRIX_ORBITALS = 6
_MAX_IBM_PROJECTED_MATRIX_ORBITALS = _MAX_NOISY_AER_PROJECTED_MATRIX_ORBITALS


def _append_qse_execution_validation_messages(
    payload: RunCreate,
    *,
    warnings: list[str],
    molecule_active_space_n_orbitals: int | None = None,
) -> None:
    """Warn when measured QSE exceeds the projected-matrix rollout cap.

    Measured QSE assembles projected H/S from Pauli expectation values on one
    reference state through the backend estimator (arXiv:2608.08739). It is a
    diagnostic construction: the projected metric is never promoted to a
    converged or chemically accurate result. The same active-space orbital caps
    used for KQD/QFD branch matrix elements apply. Oversized configurations are
    accepted so a benchmark can select them, then marked EXCLUDED at execution
    rather than run.
    """
    if payload.algorithm != RunAlgorithm.QSE:
        return
    if molecule_active_space_n_orbitals is None:
        return
    if (
        payload.backend_target == BackendTarget.AER_SIMULATOR
        and payload.noise_profile is not None
        and molecule_active_space_n_orbitals > _MAX_NOISY_AER_PROJECTED_MATRIX_ORBITALS
    ):
        warnings.append(
            "Noisy Aer QSE measured matrix elements are limited to active spaces up to "
            f"{_MAX_NOISY_AER_PROJECTED_MATRIX_ORBITALS} orbitals in the current rollout. "
            "This configuration is accepted but will be marked EXCLUDED at execution "
            "instead of running. Use statevector or ideal Aer for larger local QSE."
        )
    if (
        payload.backend_target == BackendTarget.IBM_RUNTIME
        and molecule_active_space_n_orbitals > _MAX_IBM_PROJECTED_MATRIX_ORBITALS
    ):
        warnings.append(
            "IBM Runtime QSE measured matrix elements are limited to active spaces up to "
            f"{_MAX_IBM_PROJECTED_MATRIX_ORBITALS} orbitals in the current rollout. "
            "This configuration is accepted but will be marked EXCLUDED at execution "
            "instead of running. Use statevector or ideal Aer for larger local QSE."
        )


def _append_qse_runtime_path_warning(
    payload: RunCreate,
    *,
    warnings: list[str],
    molecule_active_space_n_orbitals: int | None,
) -> None:
    if payload.algorithm != RunAlgorithm.QSE:
        return
    is_measured_target = payload.backend_target == BackendTarget.IBM_RUNTIME or (
        payload.backend_target == BackendTarget.AER_SIMULATOR
        and payload.noise_profile is not None
    )
    if not is_measured_target:
        return
    warnings.append(
        "QSE measures projected matrix elements on the selected backend estimator "
        "(measured QSE). The projected solve is a diagnostic: it is never reported as "
        "converged or chemically accurate on a noisy or hardware target."
    )


def _append_skqd_validation_messages(
    payload: RunCreate,
    *,
    errors: list[RunValidationErrorDetail],
    molecule_active_space_n_electrons: int | None,
) -> None:
    if not isinstance(payload.advanced_config, SKQDAdvancedConfig):
        return

    sampling = payload.advanced_config.base_sampling_options

    if (sampling.num_elec_a is None) != (sampling.num_elec_b is None):
        errors.append(
            RunValidationErrorDetail(
                field=_SKQD_BASE_ELECTRON_FIELD,
                code=ValidationErrorCode.MISSING_REQUIRED,
                message="Provide both SKQD base electron counts together, or omit both",
            )
        )

    if (
        sampling.num_elec_a is not None
        and sampling.num_elec_b is not None
        and molecule_active_space_n_electrons is not None
        and (sampling.num_elec_a + sampling.num_elec_b) != molecule_active_space_n_electrons
    ):
        errors.append(
            RunValidationErrorDetail(
                field=_SKQD_BASE_ELECTRON_FIELD,
                code=ValidationErrorCode.INCOMPATIBLE_BACKEND,
                message="SKQD base electron counts must match molecule active-space electrons",
            )
        )

    if (
        sampling.num_elec_a is not None
        and sampling.num_elec_b is not None
        and (sampling.num_elec_a + sampling.num_elec_b) % 2 != 0
    ):
        errors.append(
            RunValidationErrorDetail(
                field=_SKQD_BASE_ELECTRON_FIELD,
                code=ValidationErrorCode.INCOMPATIBLE_BACKEND,
                message=(
                    "SKQD base electron counts must sum to an even number in closed-shell rollout"
                ),
            )
        )

    if (
        sampling.symmetrize_spin
        and sampling.num_elec_a is not None
        and sampling.num_elec_b is not None
        and sampling.num_elec_a != sampling.num_elec_b
    ):
        errors.append(
            RunValidationErrorDetail(
                field="advanced_config.base_sampling_options.symmetrize_spin",
                code=ValidationErrorCode.INCOMPATIBLE_BACKEND,
                message=("SKQD base symmetrize_spin requires equal alpha and beta electron counts"),
            )
        )
    if (
        sampling.symmetrize_spin
        and isinstance(sampling.max_dim, tuple)
        and sampling.max_dim[0] != sampling.max_dim[1]
    ):
        errors.append(
            RunValidationErrorDetail(
                field="advanced_config.base_sampling_options.max_dim",
                code=ValidationErrorCode.INVALID_RANGE,
                message=(
                    "SKQD base symmetrize_spin requires identical alpha and beta max_dim limits"
                ),
            )
        )
