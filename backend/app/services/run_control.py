"""Run control operations for pause, resume, restart, and checkpoints."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.exceptions import ConflictError, NotFoundError
from app.models import Run, RunCheckpoint
from app.models.enums import RunEventType, RunStatus
from app.schemas.run_requests import RunCheckpointCreate
from app.services import queue_service
from app.services.run_event_service import RunEventService

logger = logging.getLogger(__name__)

_TERMINAL_STATUSES = frozenset({RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED})
_ACTIVE_STATUSES = frozenset({RunStatus.CREATED, RunStatus.QUEUED, RunStatus.RUNNING})
_RESUMABLE_STATUSES = frozenset({RunStatus.PAUSED, RunStatus.FAILED})


class RunControlService:
    """Business logic for user-initiated run control actions."""

    def __init__(self, db: Session):
        self.db = db
        self.events = RunEventService(db)

    def pause(self, run_id: UUID, *, reason: str | None = None, redis_client=None) -> Run:
        """Request a run pause or mark queue-local runs as paused immediately."""

        run = self._get_locked_run(run_id)

        if run.status == RunStatus.PAUSED:
            return run
        if run.status == RunStatus.PAUSING:
            return run
        if run.status in _TERMINAL_STATUSES:
            raise ConflictError(f"Cannot pause a run in {run.status} state")

        previous_status = run.status
        if run.status == RunStatus.QUEUED and redis_client is not None:
            rq_job_id = (run.run_metadata or {}).get("rq_job_id")
            if rq_job_id:
                queue_service.cancel_queued_job(rq_job_id, redis_client)

        run.status = (
            RunStatus.PAUSING
            if previous_status in {RunStatus.RUNNING, RunStatus.SUBMITTED_TO_IBM}
            else RunStatus.PAUSED
        )
        self._append_control_event(
            run,
            action="pause",
            previous_status=previous_status,
            reason=reason,
        )
        self.events._append_event(run.id, RunEventType.STATUS_CHANGED, {"status": run.status.value})

        self.db.commit()
        self.db.refresh(run)
        return run

    def resume(self, run_id: UUID, *, reason: str | None = None, redis_client=None) -> Run:
        """Resume a paused or failed run by returning it to CREATED or QUEUED."""

        run = self._get_locked_run(run_id)

        if run.status in _ACTIVE_STATUSES or run.status == RunStatus.SUBMITTED_TO_IBM:
            return run
        if run.status == RunStatus.PAUSING:
            raise ConflictError("Run is still pausing; wait for PAUSED before resuming")
        if run.status not in _RESUMABLE_STATUSES:
            raise ConflictError(f"Cannot resume a run in {run.status} state")

        previous_status = run.status
        previous_generation = int(run.execution_generation or 1)
        run.execution_generation = int(run.execution_generation or 1) + 1
        run.run_metadata = {
            key: value
            for key, value in (run.run_metadata or {}).items()
            if key != "rq_job_id"
        }
        run.status = RunStatus.QUEUED if redis_client is not None else RunStatus.CREATED
        run.run_metadata = {
            **(run.run_metadata or {}),
            "resume_mode": "restart_from_beginning",
            "resumed_from_generation": previous_generation,
            "resume_requested_at": datetime.now(UTC).isoformat(),
        }

        self._append_control_event(
            run,
            action="resume",
            previous_status=previous_status,
            reason=reason,
        )
        self.events._append_event(run.id, RunEventType.STATUS_CHANGED, {"status": run.status.value})

        self.db.commit()
        self.db.refresh(run)
        if redis_client is not None:
            rq_job_id = self._try_enqueue(run, redis_client)
            run = self._finish_resume_enqueue(
                run.id,
                execution_generation=int(run.execution_generation or 1),
                rq_job_id=rq_job_id,
            )
        return run

    def restart(
        self,
        run_id: UUID,
        *,
        reason: str | None = None,
        client_request_id: UUID | None = None,
        cancel_active: bool = False,
        redis_client=None,
    ) -> tuple[Run, Run]:
        """Clone a restartable run into a child run with the next execution generation."""

        parent = self._get_locked_run(run_id)
        source_cancelled_for_restart = self._cancel_parent_for_restart(
            parent,
            cancel_active=cancel_active,
            redis_client=redis_client,
        )
        existing = self._existing_restart_child(
            parent,
            client_request_id=client_request_id,
            refresh_parent=source_cancelled_for_restart,
        )
        if existing is not None:
            return parent, existing

        child = self._new_restart_child(
            parent,
            reason=reason,
            client_request_id=client_request_id,
        )
        self.db.add(child)
        self.db.flush()
        self._append_restart_created_event(parent, child, reason=reason)

        self.db.commit()
        if redis_client is not None:
            self._enqueue_restart_child(child, redis_client)
            self.db.commit()
        self.db.refresh(parent)
        self.db.refresh(child)
        return parent, child

    def _cancel_parent_for_restart(self, parent: Run, *, cancel_active: bool, redis_client) -> bool:
        if parent.status in _TERMINAL_STATUSES or parent.status == RunStatus.PAUSED:
            return False

        if not cancel_active:
            raise ConflictError(
                f"Cannot restart a run in {parent.status} state without cancel_active=true"
            )

        if redis_client is not None:
            rq_job_id = (parent.run_metadata or {}).get("rq_job_id")
            if rq_job_id:
                queue_service.cancel_queued_job(rq_job_id, redis_client)

        parent.status = RunStatus.CANCELLED
        self.events._append_event(
            parent.id,
            RunEventType.STATUS_CHANGED,
            {"status": RunStatus.CANCELLED.value, "reason": "restart_requested"},
        )
        return True

    def _existing_restart_child(
        self,
        parent: Run,
        *,
        client_request_id: UUID | None,
        refresh_parent: bool,
    ) -> Run | None:
        if client_request_id is None:
            return None

        existing = self.db.scalars(
            select(Run).where(Run.client_request_id == client_request_id)
        ).first()
        if existing is None:
            return None

        if refresh_parent:
            self.db.commit()
            self.db.refresh(parent)
            self.db.refresh(existing)
        return existing

    @staticmethod
    def _new_restart_child(
        parent: Run,
        *,
        reason: str | None,
        client_request_id: UUID | None,
    ) -> Run:
        parent_metadata = {
            key: value
            for key, value in (parent.run_metadata or {}).items()
            if key
            not in {
                "rq_job_id",
                "run_started_at",
                "run_finished_at",
                "runtime_seconds",
                "runtime_basis",
                "runtime_complete",
                "execution_timing",
            }
        }
        return Run(
            molecule_id=parent.molecule_id,
            basis_set=parent.basis_set,
            algorithm=parent.algorithm,
            mode=parent.mode,
            backend_target=parent.backend_target,
            status=RunStatus.CREATED,
            config_json=dict(parent.config_json or {}),
            client_request_id=client_request_id,
            execution_generation=int(parent.execution_generation or 1) + 1,
            restarted_from_run_id=parent.id,
            credential_profile_id=parent.credential_profile_id,
            credential_profile_name=parent.credential_profile_name,
            versions=parent.versions,
            run_metadata={
                **parent_metadata,
                "restart": {
                    "source_run_id": str(parent.id),
                    "source_generation": int(parent.execution_generation or 1),
                    "reason": reason,
                },
                "resume_mode": "restart_from_beginning",
            },
            initial_estimate=parent.initial_estimate,
            latest_estimate=parent.initial_estimate,
        )

    def _enqueue_restart_child(self, child: Run, redis_client) -> None:
        rq_job_id = self._try_enqueue(child, redis_client)
        if rq_job_id is None:
            return

        current = self._get_locked_run(child.id)
        if current.execution_generation != child.execution_generation:
            return
        if current.status in {
            RunStatus.CREATED,
            RunStatus.QUEUED,
            RunStatus.RUNNING,
            RunStatus.SUBMITTED_TO_IBM,
            RunStatus.PAUSING,
        }:
            if current.status == RunStatus.CREATED:
                current.status = RunStatus.QUEUED
                self.events._append_event(
                    current.id,
                    RunEventType.STATUS_CHANGED,
                    {"status": RunStatus.QUEUED.value},
                )
            current.run_metadata = {**(current.run_metadata or {}), "rq_job_id": rq_job_id}

    def _finish_resume_enqueue(
        self,
        run_id: UUID,
        *,
        execution_generation: int,
        rq_job_id: str | None,
    ) -> Run:
        """Attach a queue ID after the generation is durable and enqueue succeeds."""
        run = self._get_locked_run(run_id)
        if run.execution_generation != execution_generation:
            self.db.commit()
            self.db.refresh(run)
            return run

        if rq_job_id is None:
            if run.status == RunStatus.QUEUED:
                run.status = RunStatus.CREATED
                self.events._append_event(
                    run.id,
                    RunEventType.STATUS_CHANGED,
                    {"status": RunStatus.CREATED.value, "reason": "queue_enqueue_failed"},
                )
        elif run.status in {
            RunStatus.QUEUED,
            RunStatus.RUNNING,
            RunStatus.SUBMITTED_TO_IBM,
            RunStatus.PAUSING,
        }:
            run.run_metadata = {**(run.run_metadata or {}), "rq_job_id": rq_job_id}
            self.events._append_event(
                run.id,
                RunEventType.RESUME_ENQUEUED,
                {"status": run.status.value, "rq_job_id": rq_job_id},
            )

        self.db.commit()
        self.db.refresh(run)
        return run

    def _append_restart_created_event(self, parent: Run, child: Run, *, reason: str | None) -> None:
        self.events._append_event(
            parent.id,
            RunEventType.RESTART_CREATED,
            {
                "child_run_id": str(child.id),
                "child_generation": child.execution_generation,
                "reason": reason,
            },
        )

    def create_checkpoint(self, run_id: UUID, checkpoint_in: RunCheckpointCreate) -> RunCheckpoint:
        """Persist a checkpoint for the run's current execution generation."""

        run = self._get_locked_run(run_id)
        checkpoint = RunCheckpoint(
            run_id=run.id,
            execution_generation=int(run.execution_generation or 1),
            algorithm=self._algorithm_label(run),
            checkpoint_version=checkpoint_in.checkpoint_version,
            payload=checkpoint_in.payload,
            event_sequence=checkpoint_in.event_sequence,
        )
        self.db.add(checkpoint)
        self.db.flush()
        self.events._append_event(
            run.id,
            RunEventType.CHECKPOINT_SAVED,
            {
                "checkpoint_id": str(checkpoint.id),
                "execution_generation": checkpoint.execution_generation,
                "event_sequence": checkpoint.event_sequence,
            },
        )
        self.db.commit()
        self.db.refresh(checkpoint)
        return checkpoint

    def list_checkpoints(
        self,
        run_id: UUID,
        *,
        execution_generation: int | None = None,
    ) -> tuple[list[RunCheckpoint], int]:
        """List checkpoints for a run, optionally filtered by generation."""

        self._get_run(run_id)
        query = select(RunCheckpoint).where(RunCheckpoint.run_id == run_id)
        if execution_generation is not None:
            query = query.where(RunCheckpoint.execution_generation == execution_generation)
        total = self.db.scalar(select(func.count()).select_from(query.subquery()))
        checkpoints = list(self.db.scalars(query.order_by(RunCheckpoint.created_at.desc())).all())
        return checkpoints, int(total or 0)

    def _get_run(self, run_id: UUID) -> Run:
        run = self.db.get(Run, run_id)
        if run is None:
            raise NotFoundError(f"Run {run_id} not found")
        return run

    def _get_locked_run(self, run_id: UUID) -> Run:
        run = self.db.scalar(select(Run).where(Run.id == run_id).with_for_update())
        if run is None:
            raise NotFoundError(f"Run {run_id} not found")
        return run

    def _try_enqueue(self, run: Run, redis_client) -> str | None:
        if redis_client is None:
            return None
        try:
            return queue_service.enqueue_run(
                run.id,
                redis_client,
                execution_generation=int(run.execution_generation or 1),
                queue_name=queue_service.queue_name_for_run(run),
            )
        except Exception:
            logger.warning(
                "Failed to enqueue run %s during control action; leaving in CREATED state.",
                run.id,
                exc_info=True,
            )
            return None

    def _append_control_event(
        self,
        run: Run,
        *,
        action: str,
        previous_status: RunStatus,
        reason: str | None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "action": action,
            "previous_status": previous_status.value,
            "status": run.status.value,
            "execution_generation": int(run.execution_generation or 1),
        }
        if reason:
            payload["reason"] = reason
        if extra:
            payload.update(extra)
        self.events._append_event(run.id, RunEventType.CONTROL_REQUESTED, payload)

    @staticmethod
    def _algorithm_label(run: Run) -> str:
        if run.algorithm is not None:
            return run.algorithm.value
        config = run.config_json or {}
        algorithm = config.get("algorithm")
        return str(algorithm) if algorithm else "unknown"
