"""Molecule-derived guardrails for algorithm-aware run validation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.core.active_space_capacity import minimum_basis_active_orbital_limit
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
    molecule_atoms: Sequence[Mapping[str, Any]] | None,
    molecule_charge: int,
    molecule_active_space_method: str | None,
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

    if (
        payload.effective_basis_set().strip().lower() == "sto-3g"
        and molecule_active_space_method
        in {"automatic_valence", "automatic_frontier_estimate"}
        and molecule_atoms
        and molecule_active_space_n_electrons is not None
        and molecule_active_space_n_orbitals is not None
    ):
        capacity = minimum_basis_active_orbital_limit(
            molecule_atoms,
            active_electrons=molecule_active_space_n_electrons,
            charge=molecule_charge,
        )
        if capacity is not None and molecule_active_space_n_orbitals > capacity:
            errors.append(
                RunValidationErrorDetail(
                    field="molecule.active_space.n_orbitals",
                    code=ValidationErrorCode.INVALID_RANGE,
                    message=(
                        "The active space exceeds the STO-3G orbital capacity after "
                        f"frozen-core orbitals are accounted for (maximum {capacity})"
                    ),
                    suggestion=(
                        f"Use at most {capacity} active orbitals for this molecule, "
                        "or select a larger basis set."
                    ),
                )
            )
