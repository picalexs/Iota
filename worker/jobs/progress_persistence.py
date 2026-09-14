"""Progress callback orchestration and repository-backed telemetry writes."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from worker.chemistry.types import HamiltonianBundle
from worker.persistence.run_repository import SqlRunRepository

from ._progress_tracking import (
    _build_telemetry_estimate,
    _compute_elapsed_seconds,
    _persist_latest_estimate,
)
from .control_state import check_progress_control_state
from .execution_segments import heartbeat_execution_segment
from .progress import (
    estimated_total_iterations_for_progress,
    prepare_progress_payload,
)


def emit_progress_update(
    payload: dict[str, Any],
    *,
    db: Session,
    run_id: str,
    execution_generation: int,
    algorithm: str,
    progress_state: dict[str, Any],
    progress_total: int,
    hamiltonian_bundle: HamiltonianBundle,
    backend_target: str,
    eta_seed_seconds_per_iteration: float | None,
    eta_seed_confidence: float | None,
    workload_fields: dict[str, Any] | None = None,
) -> None:
    """Normalize one solver callback and persist its estimate/event batch."""
    check_progress_control_state(
        db,
        run_id=run_id,
        execution_generation=execution_generation,
        algorithm=algorithm,
        progress_state=progress_state,
        payload=payload,
        repository_factory=SqlRunRepository,
    )
    payload_to_store = prepare_progress_payload(
        payload,
        algorithm=algorithm,
        progress_state=progress_state,
    )
    elapsed_seconds = _compute_elapsed_seconds(progress_state)
    estimate_total_iterations = estimated_total_iterations_for_progress(
        payload_to_store,
        progress_total=progress_total,
        progress_state=progress_state,
    )
    estimate_payload = _build_telemetry_estimate(
        algorithm=algorithm,
        total_iterations=estimate_total_iterations,
        completed_iterations=int(payload_to_store["completed_iterations"]),
        hamiltonian_bundle=hamiltonian_bundle,
        backend_target=backend_target,
        elapsed_seconds=elapsed_seconds,
        ema_state=progress_state,
        seed_seconds_per_iteration=eta_seed_seconds_per_iteration,
        seed_confidence=eta_seed_confidence,
        workload_fields=workload_fields,
    )
    _persist_latest_estimate(db, run_id, estimate_payload)
    repository = SqlRunRepository(db)
    heartbeat_execution_segment(
        db,
        progress_state=progress_state,
        run_id=run_id,
        execution_generation=execution_generation,
        heartbeat_at=None,
    )
    repository.append_event(run_id, "estimate_updated", estimate_payload)
    repository.append_event(run_id, "iteration_update", payload_to_store)
    db.commit()


__all__ = ["emit_progress_update"]
