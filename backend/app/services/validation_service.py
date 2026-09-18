"""Run request validation service for algorithm-aware run payloads."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.enums import BackendTarget
from app.models.molecule import Molecule
from app.schemas.run_config import NoiseModelSource
from app.schemas.run_requests import RunCreate, RunValidationRequest
from app.schemas.run_responses import (
    RunEstimate,
    RunValidationErrorDetail,
    RunValidationResponse,
    ValidationErrorCode,
)
from app.services.active_space import extract_active_space
from app.services.run_estimation import build_initial_estimate_for_run_request
from app.services.validation.algorithm_policies import (
    _append_kqd_validation_messages,
    _append_qse_execution_validation_messages,
    _append_qse_runtime_path_warning,
    _append_skqd_validation_messages,
    _append_sqd_validation_messages,
    _append_vqe_validation_messages,
)
from app.services.validation.backend_policies import (
    _append_aer_matrix_validation_messages,
    _append_backend_credential_validation_messages,
    _append_backend_target_validation_messages,
    _append_basis_set_validation_messages,
    _append_ibm_runtime_validation_messages,
    _append_projected_matrix_validation_messages,
)
from app.services.validation.config_alignment import (
    _append_advanced_config_alignment_messages,
    _append_mode_validation_messages,
)
from app.services.validation.guardrails import (
    _MAX_KQD_KRYLOV_DIM,
    _MAX_KQD_TROTTER_STEPS,
    _MAX_QFD_NUM_TIME_POINTS,
    _MAX_QSE_REFERENCE_VQE_ITERATIONS,
    _MAX_QSE_SUBSPACE_DIM,
    _MAX_SECTOR_DIMENSION,
    _MAX_SKQD_EXTENSION_DIM,
    _MAX_SKQD_SAMPLES_PER_STATE,
    _MAX_SQD_NUM_BATCHES,
    _MAX_SQD_SAMPLES_PER_BATCH,
    _MAX_VQE_ITERATIONS,
    _append_resource_guardrail_messages,
)
from app.services.validation.molecule_policies import _append_molecule_guardrail_messages

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
    "_MAX_VQE_ITERATIONS",
    "_append_resource_guardrail_messages",
    "validate_run_request",
    "validate_run_validation_request",
]


def validate_run_request(
    payload: RunCreate,
    *,
    molecule_active_space_n_electrons: int | None = None,
    molecule_active_space_n_orbitals: int | None = None,
    molecule_multiplicity: int | None = None,
    molecule_atoms: Sequence[Mapping[str, Any]] | None = None,
    molecule_charge: int = 0,
    molecule_active_space_method: str | None = None,
    require_ibm_confirmation: bool = False,
    ibm_credentials_available: bool | None = None,
) -> RunValidationResponse:
    """Validate algorithm-aware run request semantics."""

    errors: list[RunValidationErrorDetail] = []
    warnings: list[str] = []

    if payload.backend_target is None:
        errors.append(
            RunValidationErrorDetail(
                field="backend_target",
                code=ValidationErrorCode.MISSING_REQUIRED,
                message="backend_target is required",
            )
        )
        return RunValidationResponse(valid=False, errors=errors, warnings=warnings)

    settings = get_settings()
    capability = settings.backend_capabilities[payload.backend_target]
    _append_basis_set_validation_messages(payload, errors=errors)
    _append_backend_target_validation_messages(payload, errors=errors, capability=capability)
    _append_projected_matrix_validation_messages(
        payload,
        errors=errors,
        warnings=warnings,
        molecule_active_space_n_orbitals=molecule_active_space_n_orbitals,
    )
    _append_aer_matrix_validation_messages(
        payload,
        errors=errors,
        warnings=warnings,
        molecule_active_space_n_orbitals=molecule_active_space_n_orbitals,
    )

    _append_backend_credential_validation_messages(
        payload,
        errors=errors,
        ibm_credentials_available=ibm_credentials_available,
    )

    _append_ibm_runtime_validation_messages(
        payload,
        errors=errors,
        require_ibm_confirmation=require_ibm_confirmation,
        ibm_credentials_available=ibm_credentials_available,
    )
    _append_mode_validation_messages(payload, errors=errors)
    _append_advanced_config_alignment_messages(payload, errors=errors)
    _append_molecule_guardrail_messages(
        payload=payload,
        molecule_active_space_n_electrons=molecule_active_space_n_electrons,
        molecule_active_space_n_orbitals=molecule_active_space_n_orbitals,
        molecule_multiplicity=molecule_multiplicity,
        molecule_atoms=molecule_atoms,
        molecule_charge=molecule_charge,
        molecule_active_space_method=molecule_active_space_method,
        errors=errors,
        warnings=warnings,
    )
    _append_sqd_validation_messages(
        payload,
        errors=errors,
        molecule_active_space_n_electrons=molecule_active_space_n_electrons,
    )
    _append_vqe_validation_messages(
        payload,
        errors=errors,
        molecule_active_space_n_orbitals=molecule_active_space_n_orbitals,
    )
    _append_kqd_validation_messages(payload, errors=errors, warnings=warnings)
    _append_qse_execution_validation_messages(
        payload,
        warnings=warnings,
        molecule_active_space_n_orbitals=molecule_active_space_n_orbitals,
    )
    _append_qse_runtime_path_warning(
        payload,
        warnings=warnings,
        molecule_active_space_n_orbitals=molecule_active_space_n_orbitals,
    )
    _append_skqd_validation_messages(
        payload,
        errors=errors,
        molecule_active_space_n_electrons=molecule_active_space_n_electrons,
    )

    return RunValidationResponse(valid=len(errors) == 0, errors=errors, warnings=warnings)


def validate_run_validation_request(
    db: Session,
    request: RunValidationRequest,
) -> RunValidationResponse:
    """Validate a route-level run validation request with molecule-derived context."""
    from app.services.credential_profiles import IbmCredentialProfileService

    molecule = db.get(Molecule, request.molecule_id)
    if molecule is None:
        return RunValidationResponse(
            valid=False,
            errors=[
                RunValidationErrorDetail(
                    field="molecule_id",
                    code=ValidationErrorCode.MISSING_REQUIRED,
                    message=f"Molecule '{request.molecule_id}' was not found.",
                    suggestion="Select an existing molecule before validating the run.",
                )
            ],
            warnings=[],
            estimate=None,
        )

    n_electrons, n_orbitals = extract_active_space(molecule)
    credentials_available = False
    needs_ibm_credentials = request.run.backend_target == BackendTarget.IBM_RUNTIME or (
        request.run.backend_target == BackendTarget.AER_SIMULATOR
        and request.run.noise_profile is not None
        and request.run.noise_profile.source == NoiseModelSource.BACKEND_DERIVED
    )
    if needs_ibm_credentials:
        profile_credentials = IbmCredentialProfileService(db).resolve_credentials(
            request.run.backend_options.credential_profile_id
        )
        credentials_available = profile_credentials is not None

    response = validate_run_request(
        request.run,
        molecule_active_space_n_electrons=n_electrons,
        molecule_active_space_n_orbitals=n_orbitals,
        molecule_multiplicity=(int(molecule.multiplicity) if molecule is not None else None),
        molecule_atoms=molecule.atoms,
        molecule_charge=int(molecule.charge or 0),
        molecule_active_space_method=(
            molecule.active_space.get("method")
            if isinstance(molecule.active_space, dict)
            else None
        ),
        ibm_credentials_available=credentials_available,
    )
    estimate = build_initial_estimate_for_run_request(
        run_in=request.run,
        molecule=molecule,
        db=db,
    )
    response.estimate = RunEstimate.model_validate(estimate) if estimate is not None else None
    return response
