"""Repository-backed lifecycle and persisted chemistry-input helpers."""

from __future__ import annotations

import json
from typing import Any, cast

from sqlalchemy.orm import Session

from worker.chemistry.types import ChemistryInput
from worker.persistence.run_repository import SqlRunRepository

from .execution_config import (
    RunRowSnapshot,
    _extract_active_space,
    _resolve_basis_set,
)


def current_execution_generation(session: Session, run_id: str) -> int:
    return SqlRunRepository(session).get_execution_generation(run_id)


def mark_run_running(
    session: Session,
    *,
    run_id: str,
    execution_generation: int,
    run_started_at: str,
) -> int:
    return SqlRunRepository(session).mark_running(
        run_id,
        execution_generation,
        run_started_at,
    )


def force_run_running(
    session: Session,
    *,
    run_id: str,
    execution_generation: int,
    run_started_at: str,
) -> int:
    return SqlRunRepository(session).force_run_running(
        run_id,
        execution_generation,
        run_started_at,
    )


def load_run_row_snapshot(session: Session, run_id: str) -> RunRowSnapshot | None:
    return cast(RunRowSnapshot | None, SqlRunRepository(session).get_run_snapshot(run_id))


def parse_molecule_atoms(atoms_raw: Any) -> list[Any]:
    if isinstance(atoms_raw, str):
        try:
            atoms_raw = json.loads(atoms_raw)
        except json.JSONDecodeError as exc:
            raise ValueError("molecule atoms payload is not valid JSON") from exc
    if not isinstance(atoms_raw, list) or not atoms_raw:
        raise ValueError("molecule atoms payload must be a non-empty list")
    return atoms_raw


def load_chemistry_input(
    session: Session,
    *,
    run_id: str,
    config_snapshot: dict[str, Any],
) -> ChemistryInput:
    molecule_row = SqlRunRepository(session).get_chemistry_input(run_id)
    if molecule_row is None:
        raise RuntimeError(f"Unable to resolve molecule for run {run_id}")

    atoms = parse_molecule_atoms(molecule_row[0])
    charge_raw = molecule_row[1]
    multiplicity_raw = molecule_row[2]
    return ChemistryInput(
        atoms=atoms,
        charge=int(charge_raw) if isinstance(charge_raw, (int, float)) else 0,
        multiplicity=int(multiplicity_raw) if isinstance(multiplicity_raw, (int, float)) else 1,
        basis=_resolve_basis_set(config_snapshot, molecule_row[4]),
        active_space=_extract_active_space(molecule_row[3]),
    )
