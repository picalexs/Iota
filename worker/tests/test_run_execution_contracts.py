"""Compatibility and ownership tests for run-execution contracts."""

from __future__ import annotations

from worker.jobs.boundary_types import EventInserter as LegacyEventInserter
from worker.jobs.boundary_types import SessionFactory as LegacySessionFactory
from worker.jobs.execution_context import (
    PreparedRunContext as LegacyPreparedRunContext,
)
from worker.jobs.execution_context import StartedRunContext as LegacyStartedRunContext
from worker.jobs.run_execution.contracts import (
    EventInserter,
    PreparedRunContext,
    SessionFactory,
    StartedRunContext,
)


def test_legacy_contract_paths_remain_identical_to_run_execution_owner() -> None:
    assert LegacyEventInserter == EventInserter
    assert LegacySessionFactory == SessionFactory
    assert LegacyPreparedRunContext is PreparedRunContext
    assert LegacyStartedRunContext is StartedRunContext
