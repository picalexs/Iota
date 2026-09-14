"""Compatibility facade for run runtime estimation services."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, load_only, selectinload

from app.models.enums import (
    BackendTarget,
    RunAlgorithm,
    RunEventType,
    RunMode,
    RunStatus,
)
from app.models.molecule import Molecule
from app.models.run import Run
from app.schemas.run_requests import RunCreate
from app.services.easy_mode_presets import (
    EASY_MODE_CATALOG_VERSION,
    build_easy_mode_advanced_config,
)
from app.services.run_event_service import RunEventService
from shared.estimation import estimate_total_iterations as _estimate_total_iterations
from shared.estimation import estimate_workload_breakdown

from .estimation.features import (
    _as_dict,
    _molecule_num_qubits,
)
from .estimation.history import _infer_history_seconds_per_iteration

logger = logging.getLogger(__name__)

_MIN_RELIABLE_HISTORY_CONFIDENCE = 0.65
_ESTIMATE_SEEDABLE_STATUSES = frozenset(
    {
        RunStatus.CREATED,
        RunStatus.QUEUED,
        RunStatus.RUNNING,
        RunStatus.SUBMITTED_TO_IBM,
        RunStatus.PAUSING,
        RunStatus.PAUSED,
    }
)


def estimate_total_iterations(
    *,
    algorithm: RunAlgorithm,
    config_payload: dict[str, Any],
    num_qubits: int | None = None,
    backend_target: BackendTarget | str | None = None,
) -> int:
    """Estimate total iterations from algorithm-native configuration payloads."""
    return _estimate_total_iterations(
        algorithm=algorithm.value,
        config_payload=config_payload,
        num_qubits=num_qubits,
        backend_target=(
            backend_target.value
            if isinstance(backend_target, BackendTarget)
            else backend_target
        ),
    )


def build_estimate_snapshot(
    *,
    algorithm: RunAlgorithm,
    config_payload: dict[str, Any],
    backend_target: BackendTarget,
    num_qubits: int,
    source: str,
    completed_iterations: int,
    confidence: float | None,
    seconds_per_iteration: float | None = None,
    total_iterations_override: int | None = None,
    extra_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a normalized estimate payload with remaining/total projections."""
    _ = backend_target
    total_iterations = total_iterations_override or estimate_total_iterations(
        algorithm=algorithm,
        config_payload=config_payload,
        num_qubits=num_qubits,
        backend_target=backend_target,
    )
    remaining_iterations = max(total_iterations - max(completed_iterations, 0), 0)
    total_seconds = (
        float(total_iterations) * seconds_per_iteration
        if seconds_per_iteration is not None
        else None
    )
    remaining_seconds = (
        float(remaining_iterations) * seconds_per_iteration
        if seconds_per_iteration is not None
        else None
    )

    estimate = {
        "source": source,
        "algorithm": algorithm.value,
        "estimated_total_iterations": total_iterations,
        "estimated_remaining_iterations": remaining_iterations,
        "estimated_total_seconds": total_seconds,
        "estimated_remaining_seconds": remaining_seconds,
        "confidence": confidence,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    estimate.update(
        estimate_workload_breakdown(
            algorithm=algorithm.value,
            config_payload=config_payload,
            num_qubits=num_qubits,
            backend_target=(
                backend_target.value
                if isinstance(backend_target, BackendTarget)
                else backend_target
            ),
        )
    )
    if seconds_per_iteration is not None:
        estimate["estimated_seconds_per_iteration"] = seconds_per_iteration
    if extra_fields:
        estimate.update(extra_fields)
    return estimate


def _estimate_input_from_new_contract(
    *,
    run_in: RunCreate,
    molecule: Molecule | None,
) -> tuple[RunAlgorithm, dict[str, Any], BackendTarget, int] | None:
    if run_in.mode == RunMode.EASY:
        if run_in.easy_options is None:
            return None
        expanded = build_easy_mode_advanced_config(
            algorithm=run_in.algorithm,
            goal=run_in.easy_options.goal,
            molecule=molecule,
            backend_target=run_in.backend_target,
            has_noise_profile=run_in.noise_profile is not None,
        )
        expanded["easy_mode_catalog_version"] = EASY_MODE_CATALOG_VERSION.lower()
        return (
            run_in.algorithm,
            expanded,
            run_in.backend_target,
            _molecule_num_qubits(molecule),
        )

    if run_in.advanced_config is None:
        return None

    return (
        run_in.algorithm,
        run_in.advanced_config.model_dump(mode="json"),
        run_in.backend_target,
        _molecule_num_qubits(molecule),
    )


def _rebuild_run_create_from_persisted_run(run: Run) -> RunCreate | None:
    config_snapshot = _as_dict(run.config_json)
    algorithm = run.algorithm or config_snapshot.get("algorithm")
    mode = run.mode or config_snapshot.get("mode")
    backend_target = run.backend_target or config_snapshot.get("backend_target")

    if algorithm is None or mode is None or backend_target is None:
        logger.warning(
            "Skipping async estimate seed for run %s because the persisted config is incomplete.",
            run.id,
        )
        return None

    try:
        return RunCreate.model_validate(
            {
                **config_snapshot,
                "molecule_id": run.molecule_id,
                "client_request_id": run.client_request_id,
                "algorithm": algorithm,
                "mode": mode,
                "backend_target": backend_target,
            }
        )
    except Exception:
        logger.warning(
            "Failed to rebuild the run-create contract while seeding estimate for run %s.",
            run.id,
            exc_info=True,
        )
        return None


def build_initial_estimate_for_persisted_run(
    *,
    run: Run,
    db: Session | None = None,
) -> dict[str, Any] | None:
    """Build an initial estimate from the persisted run snapshot."""
    run_in = _rebuild_run_create_from_persisted_run(run)
    if run_in is None:
        return None
    return build_initial_estimate_for_run_request(run_in=run_in, molecule=run.molecule, db=db)


def build_initial_estimate_for_run_request(
    *,
    run_in: RunCreate,
    molecule: Molecule | None,
    db: Session | None = None,
) -> dict[str, Any] | None:
    """Build an initial estimate for a run create request."""
    estimate_input = _estimate_input_from_new_contract(run_in=run_in, molecule=molecule)
    if estimate_input is None:
        return None

    algorithm, config_payload, backend_target, num_qubits = estimate_input
    source = "config_projection"
    confidence: float | None = None
    seconds_per_iteration: float | None = None
    total_iterations_override: int | None = None
    extra_fields: dict[str, Any] | None = None

    if db is not None:
        (
            history_seconds_per_iteration,
            history_confidence,
            history_total_iterations,
            history_fields,
        ) = _infer_history_seconds_per_iteration(
            db=db,
            run_in=run_in,
            molecule=molecule,
            algorithm=algorithm,
            config_payload=config_payload,
            backend_target=backend_target,
        )
        if (
            history_seconds_per_iteration is not None
            and history_confidence is not None
            and history_confidence >= _MIN_RELIABLE_HISTORY_CONFIDENCE
        ):
            seconds_per_iteration = history_seconds_per_iteration
            confidence = history_confidence
            total_iterations_override = history_total_iterations
            source = "history"
            extra_fields = history_fields

    return build_estimate_snapshot(
        algorithm=algorithm,
        config_payload=config_payload,
        backend_target=backend_target,
        num_qubits=num_qubits,
        source=source,
        completed_iterations=0,
        confidence=confidence,
        seconds_per_iteration=seconds_per_iteration,
        total_iterations_override=total_iterations_override,
        extra_fields=extra_fields,
    )


def seed_initial_estimate_for_run(
    *,
    run_id: UUID,
    session_factory,
) -> None:
    """Populate missing run estimates after creation without blocking the submit request."""
    db = session_factory()
    try:
        run = db.scalar(
            select(Run)
            .options(
                load_only(
                    Run.id,
                    Run.molecule_id,
                    Run.algorithm,
                    Run.mode,
                    Run.backend_target,
                    Run.status,
                    Run.client_request_id,
                    Run.config_json,
                    Run.initial_estimate,
                    Run.latest_estimate,
                ),
                selectinload(Run.molecule).load_only(
                    Molecule.id,
                    Molecule.atoms,
                    Molecule.charge,
                    Molecule.multiplicity,
                    Molecule.active_space,
                ),
            )
            .where(Run.id == run_id)
            .with_for_update()
        )
        if run is None:
            return

        needs_initial_estimate = run.initial_estimate is None
        needs_latest_estimate = (
            run.latest_estimate is None and run.status in _ESTIMATE_SEEDABLE_STATUSES
        )
        if not needs_initial_estimate and not needs_latest_estimate:
            return

        estimate = build_initial_estimate_for_persisted_run(run=run, db=db)
        if estimate is None:
            return

        emitted_estimate_event = False
        if needs_initial_estimate:
            run.initial_estimate = estimate
        if needs_latest_estimate and run.latest_estimate is None:
            run.latest_estimate = estimate
            emitted_estimate_event = True

        if emitted_estimate_event:
            RunEventService(db)._append_event(run.id, RunEventType.ESTIMATE_UPDATED, estimate)
        db.commit()
    except Exception:
        db.rollback()
        logger.warning(
            "Failed to seed an async initial estimate for run %s.",
            run_id,
            exc_info=True,
        )
    finally:
        db.close()


__all__ = [
    "build_estimate_snapshot",
    "build_initial_estimate_for_persisted_run",
    "build_initial_estimate_for_run_request",
    "estimate_total_iterations",
    "seed_initial_estimate_for_run",
]
