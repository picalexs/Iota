"""Run result and export service operations."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.exceptions import NotFoundError
from app.models import Run, RunResult
from app.schemas.molecule import validate_molecule_response
from app.schemas.run_events import RunEventResponse
from app.schemas.run_responses import ExportBundle, RunExecutionSegmentResponse, RunResponse
from app.schemas.run_results import RunResultResponse


class RunExportService:
    """Business logic for run results and reproducibility exports."""

    def __init__(self, db: Session):
        self.db = db

    def get_result(self, run_id: UUID) -> RunResult:
        """Return the persisted result for a run."""
        run = self.db.scalars(
            select(Run).options(joinedload(Run.result)).where(Run.id == run_id)
        ).first()
        if run is None:
            raise NotFoundError(f"Run {run_id} not found")
        if run.result is None:
            raise NotFoundError(f"No result found for run {run_id}")

        return run.result

    def build_export(self, run_id: UUID) -> ExportBundle:
        """Build a reproducibility export bundle for a run."""
        run = self.db.scalars(
            select(Run)
            .options(
                joinedload(Run.molecule),
                selectinload(Run.events),
                selectinload(Run.execution_segments),
                joinedload(Run.result),
            )
            .where(Run.id == run_id)
        ).first()
        if run is None:
            raise NotFoundError(f"Run {run_id} not found")

        return ExportBundle(
            exported_at=datetime.now(UTC),
            molecule=validate_molecule_response(run.molecule),
            run=RunResponse.model_validate(run),
            versions=run.versions,
            events=[RunEventResponse.model_validate(event) for event in run.events],
            result=RunResultResponse.model_validate(run.result) if run.result else None,
            execution_segments=[
                RunExecutionSegmentResponse.model_validate(segment)
                for segment in run.execution_segments
            ],
        )
