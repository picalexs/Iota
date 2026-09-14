"""Tests for named worker persistence and orchestration type boundaries."""

from __future__ import annotations

from typing import get_type_hints

from sqlalchemy.orm import Session

from worker.jobs.boundary_types import EventInserter, SessionFactory
from worker.jobs.control_state import build_primitive_run_guard
from worker.jobs.lifecycle import load_chemistry_input
from worker.jobs.orchestrator import dispatch_and_finalize_run
from worker.jobs.preparation import prepare_backend_and_hamiltonian
from worker.jobs.run_execution.contracts import TransactionCommitter


def test_database_boundaries_resolve_to_named_session_contracts() -> None:
    guard_hints = get_type_hints(build_primitive_run_guard)
    lifecycle_hints = get_type_hints(load_chemistry_input)
    preparation_hints = get_type_hints(prepare_backend_and_hamiltonian)
    orchestration_hints = get_type_hints(dispatch_and_finalize_run)

    assert guard_hints["session_factory"] == SessionFactory
    assert lifecycle_hints["session"] is Session
    assert preparation_hints["session_factory"] == SessionFactory
    assert preparation_hints["insert_run_event"] == EventInserter
    assert orchestration_hints["session_factory"] == SessionFactory
    assert orchestration_hints["insert_run_event"] == EventInserter
    assert orchestration_hints["commit_transaction"] == TransactionCommitter
