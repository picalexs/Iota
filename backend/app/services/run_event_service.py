"""Run event service operations."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.exceptions import NotFoundError
from app.models import Run, RunEvent
from app.models.enums import RunEventType


class RunEventService:
    """Business logic for run event insertion and retrieval."""

    def __init__(self, db: Session):
        self.db = db

    def _append_event(
        self, run_id: UUID, event_type: RunEventType, payload: dict[str, Any]
    ) -> None:
        """Append a sequenced event for a run in the current transaction."""
        locked_run_id = self.db.scalar(select(Run.id).where(Run.id == run_id).with_for_update())
        if locked_run_id is None:
            raise NotFoundError(f"Run {run_id} not found")

        next_sequence = int(
            self.db.scalar(
                select(func.coalesce(func.max(RunEvent.sequence), 0) + 1).where(
                    RunEvent.run_id == run_id
                )
            )
            or 1
        )
        event = RunEvent(
            run_id=run_id,
            sequence=next_sequence,
            type=event_type,
            payload=payload,
        )
        self.db.add(event)
        self.db.flush()

    def get_events(self, run_id: UUID, after_sequence: int = 0) -> tuple[list[RunEvent], int]:
        """Return events for a run with sequence greater than ``after_sequence``."""
        run_exists = self.db.scalar(select(Run.id).where(Run.id == run_id))
        if run_exists is None:
            raise NotFoundError(f"Run {run_id} not found")

        events = list(
            self.db.scalars(
                select(RunEvent)
                .where(RunEvent.run_id == run_id, RunEvent.sequence > after_sequence)
                .order_by(RunEvent.sequence)
            ).all()
        )

        last_sequence = events[-1].sequence if events else after_sequence
        return events, last_sequence
