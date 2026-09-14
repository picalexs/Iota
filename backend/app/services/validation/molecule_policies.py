"""Molecule-derived guardrails for algorithm-aware run validation."""

from __future__ import annotations

from app.schemas.run_requests import RunCreate
from app.schemas.run_responses import RunValidationErrorDetail, ValidationErrorCode
from app.services.validation.guardrails import _append_resource_guardrail_messages

__all__ = ["_append_molecule_guardrail_messages"]


def _append_molecule_guardrail_messages(
    *,
    payload: RunCreate,
    molecule_active_space_n_electrons: int | None,
    molecule_active_space_n_orbitals: int | None,
    molecule_multiplicity: int | None,
    errors: list[RunValidationErrorDetail],
    warnings: list[str],
) -> None:
    _append_resource_guardrail_messages(
        payload=payload,
        molecule_active_space_n_electrons=molecule_active_space_n_electrons,
        molecule_active_space_n_orbitals=molecule_active_space_n_orbitals,
        errors=errors,
        warnings=warnings,
    )

    if molecule_multiplicity is not None and molecule_multiplicity != 1:
        errors.append(
            RunValidationErrorDetail(
                field="molecule.multiplicity",
                code=ValidationErrorCode.INCOMPATIBLE_BACKEND,
                message=(
                    "Only singlet molecules (multiplicity=1) are supported in the current rollout"
                ),
                suggestion="Use multiplicity=1 for this rollout",
            )
        )

    if molecule_active_space_n_electrons is not None and molecule_active_space_n_electrons % 2 != 0:
        errors.append(
            RunValidationErrorDetail(
                field="molecule.active_space.n_electrons",
                code=ValidationErrorCode.INCOMPATIBLE_BACKEND,
                message=(
                    "Odd active-space electron counts are not supported for closed-shell rollout"
                ),
                suggestion="Use an even active-space electron count for this rollout",
            )
        )
