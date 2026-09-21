"""Service layer for persisted benchmark batches."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID
from uuid import UUID as UUIDFactory

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.models import BenchmarkRun, Run
from app.schemas.benchmark import (
    BenchmarkRegistrationCreate,
    BenchmarkRunCreate,
    BenchmarkRunUpdate,
)
from app.services.run import RunService


class BenchmarkRunService:
    """CRUD operations for benchmark batch snapshots."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, data: BenchmarkRunCreate) -> BenchmarkRun:
        selected_molecule_keys, custom_molecules = _normalize_benchmark_snapshot_fields(
            selected_molecule_keys=list(data.selected_molecule_keys),
            custom_molecules=list(data.custom_molecules),
            entries=list(data.entries),
            selected_basis=data.selected_basis,
            fallback_timestamp=datetime.now(UTC),
        )
        benchmark = BenchmarkRun(
            name=data.name,
            campaign_id=data.campaign_id,
            registration_digest=data.registration_digest,
            campaign_metadata=dict(data.campaign_metadata),
            selected_molecule_keys=selected_molecule_keys,
            selected_algorithms=[algorithm.value for algorithm in data.selected_algorithms],
            selected_basis=data.selected_basis,
            selected_backend_mode=data.selected_backend_mode,
            selected_backend_name=data.selected_backend_name,
            shots=data.shots,
            selected_aer_method=data.selected_aer_method,
            selected_device=data.selected_device,
            chemical_accuracy_ha=data.chemical_accuracy_ha,
            custom_molecules=custom_molecules,
            entries=list(data.entries),
        )
        self.db.add(benchmark)
        self.db.commit()
        self.db.refresh(benchmark)
        return benchmark

    def register(self, data: BenchmarkRegistrationCreate) -> tuple[BenchmarkRun, bool]:
        """Register one campaign once and return ``(benchmark, is_new)``."""
        existing = self.db.scalar(
            select(BenchmarkRun).where(BenchmarkRun.campaign_id == data.campaign_id)
        )
        if existing is not None:
            if existing.registration_digest != data.registration_digest:
                raise ConflictError(
                    f"Campaign '{data.campaign_id}' is already registered with different content"
                )
            return existing, False

        _validate_registered_entries(self.db, data.entries)
        try:
            benchmark = self.create(data)
        except IntegrityError:
            self.db.rollback()
            existing = self.db.scalar(
                select(BenchmarkRun).where(BenchmarkRun.campaign_id == data.campaign_id)
            )
            if existing is None:
                raise
            if existing.registration_digest != data.registration_digest:
                raise ConflictError(
                    f"Campaign '{data.campaign_id}' is already registered with different content"
                ) from None
            return existing, False
        return benchmark, True

    def get_by_id(self, benchmark_id: UUID) -> BenchmarkRun:
        benchmark = self.db.get(BenchmarkRun, benchmark_id)
        if benchmark is None:
            raise NotFoundError(f"Benchmark {benchmark_id} not found")
        return benchmark

    def list_associated_runs(self, benchmark_id: UUID) -> list[Run]:
        benchmark = self.get_by_id(benchmark_id)
        run_ids = _extract_associated_run_ids(benchmark.entries)
        if not run_ids:
            return []
        return list(self.db.scalars(select(Run).where(Run.id.in_(run_ids))))

    def list(self, *, limit: int = 50, offset: int = 0) -> tuple[list[BenchmarkRun], int]:
        total = self.db.scalar(select(func.count()).select_from(BenchmarkRun)) or 0
        benchmarks = list(
            self.db.scalars(
                select(BenchmarkRun)
                .order_by(BenchmarkRun.updated_at.desc(), BenchmarkRun.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        return benchmarks, int(total)

    def update(self, benchmark_id: UUID, data: BenchmarkRunUpdate) -> BenchmarkRun:
        benchmark = self.get_by_id(benchmark_id)
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if key == "selected_algorithms" and value is not None:
                value = [
                    algorithm.value if hasattr(algorithm, "value") else algorithm
                    for algorithm in value
                ]
            setattr(benchmark, key, value)
        selected_molecule_keys, custom_molecules = _normalize_benchmark_snapshot_fields(
            selected_molecule_keys=list(benchmark.selected_molecule_keys or []),
            custom_molecules=list(benchmark.custom_molecules or []),
            entries=list(benchmark.entries or []),
            selected_basis=benchmark.selected_basis,
            fallback_timestamp=benchmark.updated_at,
        )
        benchmark.selected_molecule_keys = selected_molecule_keys
        benchmark.custom_molecules = custom_molecules
        benchmark.updated_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(benchmark)
        return benchmark

    def delete(
        self, benchmark_id: UUID, *, delete_associated_runs: bool = False, redis_client=None
    ) -> None:
        benchmark = self.get_by_id(benchmark_id)
        associated_run_ids = _extract_associated_run_ids(benchmark.entries)

        if delete_associated_runs and associated_run_ids:
            existing_run_ids = set(
                self.db.scalars(select(Run.id).where(Run.id.in_(associated_run_ids)))
            )
            run_service = RunService(self.db)
            for run_id in associated_run_ids:
                if run_id not in existing_run_ids:
                    continue
                run_service.delete(run_id, redis_client=redis_client, commit=False)

            benchmark = self.get_by_id(benchmark_id)

        self.db.delete(benchmark)
        self.db.commit()


def _extract_associated_run_ids(entries: list[dict[str, Any]]) -> list[UUID]:
    run_ids: list[UUID] = []
    seen: set[UUID] = set()

    for entry in entries:
        raw_run_id = entry.get("runId")
        if raw_run_id in (None, ""):
            continue
        try:
            run_id = raw_run_id if isinstance(raw_run_id, UUID) else UUIDFactory(str(raw_run_id))
        except (TypeError, ValueError):
            continue
        if run_id in seen:
            continue
        seen.add(run_id)
        run_ids.append(run_id)

    return run_ids


_REGISTERED_NO_RUN_STATUSES = {"planned", "excluded", "missing"}


def _validate_registered_entries(db: Session, entries: list[dict[str, Any]]) -> None:
    """Reject registered rows that claim a run which is not persisted."""
    run_ids: list[UUID] = []
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise ValidationError(f"Registered entry {index} must be an object", field="entries")
        status = str(entry.get("status") or "missing").strip().lower()
        raw_run_id = entry.get("runId", entry.get("run_id"))
        if raw_run_id in (None, ""):
            if status not in _REGISTERED_NO_RUN_STATUSES:
                raise ValidationError(
                    f"Registered entry {index} with status '{status}' has no run ID",
                    field="entries",
                )
            continue
        try:
            run_id = raw_run_id if isinstance(raw_run_id, UUID) else UUIDFactory(str(raw_run_id))
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                f"Registered entry {index} has an invalid run ID", field="entries"
            ) from exc
        run_ids.append(run_id)

    if not run_ids:
        return
    existing_ids = set(db.scalars(select(Run.id).where(Run.id.in_(run_ids))))
    missing_ids = [run_id for run_id in run_ids if run_id not in existing_ids]
    if missing_ids:
        missing = ", ".join(str(run_id) for run_id in missing_ids)
        raise ValidationError(f"Registered entries reference unknown run IDs: {missing}", field="entries")


def _normalize_benchmark_snapshot_fields(
    *,
    selected_molecule_keys: list[str],
    custom_molecules: list[dict[str, Any]],
    entries: list[dict[str, Any]],
    selected_basis: str,
    fallback_timestamp: datetime,
) -> tuple[list[str], list[dict[str, Any]]]:
    entry_selected_molecule_keys = _derive_selected_molecule_keys_from_entries(entries)
    normalized_selected_molecule_keys = (
        selected_molecule_keys if selected_molecule_keys else entry_selected_molecule_keys
    )
    derived_custom_molecules = _derive_custom_molecules_from_entries(
        entries=entries,
        selected_basis=selected_basis,
        fallback_timestamp=fallback_timestamp,
    )
    normalized_custom_molecules = _merge_custom_molecules(
        current=custom_molecules,
        incoming=derived_custom_molecules,
    )
    return normalized_selected_molecule_keys, normalized_custom_molecules


def _derive_selected_molecule_keys_from_entries(entries: list[dict[str, Any]]) -> list[str]:
    selected_molecule_keys: list[str] = []
    seen: set[str] = set()

    for entry in entries:
        preset = entry.get("preset")
        if not isinstance(preset, dict):
            continue
        key = preset.get("key")
        if not isinstance(key, str):
            continue
        normalized_key = key.strip()
        if not normalized_key or normalized_key in seen:
            continue
        seen.add(normalized_key)
        selected_molecule_keys.append(normalized_key)

    return selected_molecule_keys


def _derive_custom_molecules_from_entries(
    *,
    entries: list[dict[str, Any]],
    selected_basis: str,
    fallback_timestamp: datetime,
) -> list[dict[str, Any]]:
    custom_molecules: list[dict[str, Any]] = []
    seen: set[str] = set()
    fallback_timestamp_iso = fallback_timestamp.astimezone(UTC).isoformat()

    for entry in entries:
        custom_molecule = _build_custom_molecule_from_entry(
            entry=entry,
            selected_basis=selected_basis,
            fallback_timestamp_iso=fallback_timestamp_iso,
        )
        if custom_molecule is None:
            continue
        molecule_id = custom_molecule["id"]
        if molecule_id in seen:
            continue
        seen.add(molecule_id)
        custom_molecules.append(custom_molecule)

    return custom_molecules


def _build_custom_molecule_from_entry(
    *,
    entry: dict[str, Any],
    selected_basis: str,
    fallback_timestamp_iso: str,
) -> dict[str, Any] | None:
    preset, normalized_key = _extract_custom_preset(entry)
    if preset is None or normalized_key is None:
        return None

    molecule_id = _resolve_custom_molecule_id(entry, normalized_key)
    if molecule_id is None:
        return None

    name = preset.get("name")
    atoms = preset.get("atoms")
    if not isinstance(name, str) or not name.strip() or not isinstance(atoms, list):
        return None

    return {
        "id": molecule_id,
        "name": name.strip(),
        "atoms": atoms,
        "basis_set": _resolve_custom_molecule_basis(preset, selected_basis),
        "charge": preset.get("charge") if isinstance(preset.get("charge"), int) else 0,
        "multiplicity": preset.get("multiplicity")
        if isinstance(preset.get("multiplicity"), int)
        else 1,
        "active_space": preset.get("active_space"),
        "created_at": fallback_timestamp_iso,
        "updated_at": fallback_timestamp_iso,
        "iupac_name": preset.get("formula") if isinstance(preset.get("formula"), str) else None,
        "description": preset.get("description")
        if isinstance(preset.get("description"), str)
        else None,
    }


def _extract_custom_preset(entry: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    preset = entry.get("preset")
    if not isinstance(preset, dict):
        return None, None
    key = preset.get("key")
    if not isinstance(key, str):
        return None, None
    normalized_key = key.strip()
    if not normalized_key.startswith("custom:"):
        return None, None
    return preset, normalized_key


def _resolve_custom_molecule_id(entry: dict[str, Any], normalized_key: str) -> str | None:
    molecule_id = entry.get("moleculeId")
    if isinstance(molecule_id, UUID):
        molecule_id = str(molecule_id)
    if not isinstance(molecule_id, str) or not molecule_id.strip():
        molecule_id = normalized_key.removeprefix("custom:")
    molecule_id = molecule_id.strip()
    return molecule_id or None


def _resolve_custom_molecule_basis(preset: dict[str, Any], selected_basis: str) -> str:
    basis = preset.get("basis")
    return basis if isinstance(basis, str) and basis else selected_basis


def _merge_custom_molecules(
    *, current: list[dict[str, Any]], incoming: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}

    for molecule in current:
        molecule_id = molecule.get("id")
        if isinstance(molecule_id, UUID):
            molecule_id = str(molecule_id)
        if isinstance(molecule_id, str) and molecule_id.strip():
            merged[molecule_id.strip()] = molecule

    for molecule in incoming:
        molecule_id = molecule.get("id")
        if isinstance(molecule_id, str) and molecule_id.strip():
            merged.setdefault(molecule_id.strip(), molecule)

    return list(merged.values())
