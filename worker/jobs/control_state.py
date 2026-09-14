"""Repository-backed pause and cancellation checkpoints for worker runs."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from worker.contracts import HamiltonianBundleContract

from .run_execution.contracts import (
    RepositoryFactory,
    SessionFactory,
    StoppedRunResultFactory,
)

logger = logging.getLogger(__name__)


class RunCancelled(RuntimeError):
    """Raised when a run is cancelled at a cooperative control checkpoint."""


class RunPaused(RuntimeError):
    """Raised when a run reaches a cooperative pause checkpoint."""


def build_primitive_run_guard(
    run_id: str,
    *,
    session_factory: SessionFactory,
    repository_factory: RepositoryFactory,
) -> Callable[[], None]:
    """Build a guard that stops primitive work for cancelled or paused runs."""

    def guard() -> None:
        with session_factory() as session:
            status = repository_factory(session).request_control_state(run_id)
        if status == "CANCELLED":
            raise RunCancelled(run_id)
        if status in {"PAUSING", "PAUSED"}:
            raise RunPaused(run_id)

    return guard


def save_pause_checkpoint(
    session: Session,
    run_id: str,
    *,
    execution_generation: int,
    algorithm: str,
    payload: dict[str, Any],
    repository_factory: RepositoryFactory,
) -> None:
    """Persist a pause checkpoint and move the run to ``PAUSED`` when eligible."""
    repository = repository_factory(session)
    checkpoint_id = repository.save_pause_checkpoint(
        run_id,
        execution_generation,
        algorithm,
        payload,
    )
    repository.append_event(
        run_id,
        "checkpoint_saved",
        {
            "checkpoint_id": checkpoint_id,
            "execution_generation": execution_generation,
            "algorithm": algorithm,
            "reason": "pause_requested",
        },
    )
    if repository.mark_paused(run_id, execution_generation) != 0:
        repository.append_event(
            run_id,
            "status_changed",
            {"status": "PAUSED", "execution_generation": execution_generation},
        )


def finalize_cooperative_pause(
    run_id: str,
    *,
    execution_generation: int,
    algorithm: str,
    payload: dict[str, Any],
    session_factory: SessionFactory,
    repository_factory: RepositoryFactory,
) -> None:
    """Ensure a guard-triggered pause leaves the run checkpointed as ``PAUSED``."""
    with session_factory() as session:
        repository = repository_factory(session)
        status = repository.request_control_state(
            run_id,
            execution_generation,
            for_update=True,
        )
        if status != "PAUSING":
            return
        save_pause_checkpoint(
            session,
            run_id,
            execution_generation=execution_generation,
            algorithm=algorithm,
            payload=payload,
            repository_factory=repository_factory,
        )
        session.commit()


def handle_pre_start_control_state(
    session: Session,
    *,
    run_id: str,
    execution_generation: int,
    algorithm: str,
    progress_state: dict[str, Any],
    repository_factory: RepositoryFactory,
    stopped_run_result: StoppedRunResultFactory,
) -> dict[str, Any] | None:
    """Resolve pause/cancel requests observed before execution starts."""
    status = repository_factory(session).request_control_state(run_id, execution_generation)
    if status == "PAUSING":
        save_pause_checkpoint(
            session,
            run_id,
            execution_generation=execution_generation,
            algorithm=algorithm,
            payload={"stage": "before_start", "progress_state": progress_state},
            repository_factory=repository_factory,
        )
        session.commit()
        return stopped_run_result(algorithm, status="PAUSED")
    if status in {"CANCELLED", "PAUSED"}:
        logger.info("Run %s was already %s before start", run_id, status)
        return stopped_run_result(algorithm)
    return None


def handle_setup_control_state(
    session: Session,
    *,
    run_id: str,
    execution_generation: int,
    algorithm: str,
    progress_state: dict[str, Any],
    config_snapshot: dict[str, Any],
    hamiltonian_bundle: HamiltonianBundleContract,
    repository_factory: RepositoryFactory,
    stopped_run_result: StoppedRunResultFactory,
) -> dict[str, Any] | None:
    """Resolve pause/cancel requests observed after chemistry setup."""
    status = repository_factory(session).request_control_state(run_id, execution_generation)
    if status == "CANCELLED":
        logger.info("Run %s was cancelled during setup", run_id)
        return stopped_run_result(algorithm)
    if status != "PAUSING":
        return None

    save_pause_checkpoint(
        session,
        run_id,
        execution_generation=execution_generation,
        algorithm=algorithm,
        payload={
            "stage": "setup",
            "progress_state": progress_state,
            "config_snapshot": config_snapshot,
            "hamiltonian_metadata": hamiltonian_bundle.metadata,
        },
        repository_factory=repository_factory,
    )
    session.commit()
    paused_iterations = int(progress_state.get("monotonic_completed_iterations", 0))
    return stopped_run_result(algorithm, iterations=paused_iterations, status="PAUSED")


def check_progress_control_state(
    db: Session,
    *,
    run_id: str,
    execution_generation: int,
    algorithm: str,
    progress_state: dict[str, Any],
    payload: dict[str, Any],
    repository_factory: RepositoryFactory,
) -> None:
    """Apply cancellation/pause requests before persisting one progress event."""
    repository = repository_factory(db)
    status = repository.request_control_state(run_id, execution_generation)
    if status == "CANCELLED":
        logger.info("Run %s was cancelled during live progress emission", run_id)
        repository.append_event(run_id, "status_changed", {"status": "CANCELLED"})
        db.commit()
        raise RunCancelled(run_id)
    if status != "PAUSING":
        return

    payload_to_checkpoint = dict(payload)
    payload_to_checkpoint.setdefault("progress_state", dict(progress_state))
    save_pause_checkpoint(
        db,
        run_id,
        execution_generation=execution_generation,
        algorithm=algorithm,
        payload=payload_to_checkpoint,
        repository_factory=repository_factory,
    )
    db.commit()
    raise RunPaused(run_id)


def pause_after_dispatch_if_requested(
    db: Session,
    *,
    run_id: str,
    execution_generation: int,
    algorithm: str,
    progress_state: dict[str, Any],
    repository_factory: RepositoryFactory,
) -> None:
    """Checkpoint a pause request observed after solver dispatch returns."""
    repository = repository_factory(db)
    if repository.request_control_state(run_id, execution_generation) != "PAUSING":
        return

    save_pause_checkpoint(
        db,
        run_id,
        execution_generation=execution_generation,
        algorithm=algorithm,
        payload={
            "stage": "after_dispatch",
            "progress_state": progress_state,
        },
        repository_factory=repository_factory,
    )
    db.commit()
    raise RunPaused(run_id)


__all__ = [
    "RunCancelled",
    "RunPaused",
    "build_primitive_run_guard",
    "check_progress_control_state",
    "finalize_cooperative_pause",
    "handle_pre_start_control_state",
    "handle_setup_control_state",
    "pause_after_dispatch_if_requested",
    "save_pause_checkpoint",
]
