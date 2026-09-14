"""Focused tests for run event and export services."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.exceptions import NotFoundError
from app.models import RunEvent, RunEventType, RunExecutionSegment, RunResult, RunStatus
from app.services.run_event_service import RunEventService
from app.services.run_export_service import RunExportService
from sqlalchemy.orm import Session


def test_run_event_service_appends_next_sequence(test_db: Session, sample_run) -> None:
    service = RunEventService(test_db)
    test_db.add(
        RunEvent(
            run_id=sample_run.id,
            sequence=1,
            type=RunEventType.STATUS_CHANGED,
            payload={"status": RunStatus.RUNNING.value},
        )
    )
    test_db.commit()

    service._append_event(
        sample_run.id,
        RunEventType.ITERATION_UPDATE,
        {"iteration": 1, "energy": -1.0},
    )
    test_db.commit()

    events, last_sequence = service.get_events(sample_run.id)

    assert [event.sequence for event in events] == [1, 2]
    assert last_sequence == 2


def test_run_event_service_appends_unique_sequences_in_single_transaction(
    test_db: Session,
    sample_run,
) -> None:
    service = RunEventService(test_db)

    with test_db.no_autoflush:
        service._append_event(
            sample_run.id,
            RunEventType.CONTROL_REQUESTED,
            {"action": "pause"},
        )
        service._append_event(
            sample_run.id,
            RunEventType.STATUS_CHANGED,
            {"status": RunStatus.PAUSING.value},
        )
    test_db.commit()

    events, last_sequence = service.get_events(sample_run.id)

    assert [event.sequence for event in events] == [1, 2]
    assert last_sequence == 2


def test_run_event_service_get_events_preserves_after_sequence(
    test_db: Session,
    sample_run,
) -> None:
    service = RunEventService(test_db)

    events, last_sequence = service.get_events(sample_run.id, after_sequence=5)

    assert events == []
    assert last_sequence == 5


def test_run_export_service_returns_result_and_bundle(test_db: Session, sample_run) -> None:
    result = RunResult(
        run_id=sample_run.id,
        energy=-1.137,
        iterations=12,
        optimal_parameters=[0.1, -0.2],
        converged=True,
        algorithm_metrics={"depth": 4},
    )
    event = RunEvent(
        run_id=sample_run.id,
        sequence=1,
        type=RunEventType.STATUS_CHANGED,
        payload={"status": RunStatus.COMPLETED.value},
    )
    segment = RunExecutionSegment(
        run_id=sample_run.id,
        execution_generation=1,
        attempt_number=1,
        status="completed",
        worker_started_at=datetime(2026, 1, 1, tzinfo=UTC),
        worker_finished_at=datetime(2026, 1, 1, 0, 0, 2, tzinfo=UTC),
        duration_seconds=2.0,
    )
    sample_run.versions = {"api": "test"}
    test_db.add_all([result, event, segment])
    test_db.commit()

    service = RunExportService(test_db)

    assert service.get_result(sample_run.id).energy == -1.137
    bundle = service.build_export(sample_run.id)
    assert bundle.run.id == sample_run.id
    assert bundle.result is not None
    assert bundle.result.energy == -1.137
    assert [export_event.sequence for export_event in bundle.events] == [1]
    assert bundle.versions == {"api": "test"}
    assert len(bundle.execution_segments) == 1
    assert bundle.execution_segments[0].duration_seconds == 2.0


def test_run_export_service_missing_result_raises(test_db: Session, sample_run) -> None:
    with pytest.raises(NotFoundError, match="No result found"):
        RunExportService(test_db).get_result(sample_run.id)
