"""Focused tests for worker pause and cancellation control boundaries."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from worker.jobs.control_state import (
    RunCancelled,
    RunPaused,
    build_primitive_run_guard,
    check_progress_control_state,
    finalize_cooperative_pause,
    handle_pre_start_control_state,
    handle_setup_control_state,
    pause_after_dispatch_if_requested,
)


def test_pre_start_pause_persists_checkpoint_and_returns_paused_result() -> None:
    session = MagicMock()
    repository = MagicMock()
    repository.request_control_state.return_value = "PAUSING"
    repository.save_pause_checkpoint.return_value = "checkpoint-1"
    repository.mark_paused.return_value = 1
    stopped = MagicMock(return_value={"status": "PAUSED"})

    result = handle_pre_start_control_state(
        session,
        run_id="run-1",
        execution_generation=2,
        algorithm="vqe",
        progress_state={"count": 0},
        repository_factory=lambda _: repository,
        stopped_run_result=stopped,
    )

    assert result == {"status": "PAUSED"}
    repository.save_pause_checkpoint.assert_called_once()
    session.commit.assert_called_once()
    stopped.assert_called_once_with("vqe", status="PAUSED")


def test_setup_pause_includes_chemistry_metadata_and_progress_count() -> None:
    session = MagicMock()
    repository = MagicMock()
    repository.request_control_state.return_value = "PAUSING"
    repository.save_pause_checkpoint.return_value = "checkpoint-2"
    repository.mark_paused.return_value = 1
    stopped = MagicMock(return_value={"status": "PAUSED", "iterations": 3})

    result = handle_setup_control_state(
        session,
        run_id="run-1",
        execution_generation=1,
        algorithm="kqd",
        progress_state={"monotonic_completed_iterations": 3},
        config_snapshot={"max_iterations": 4},
        hamiltonian_bundle=SimpleNamespace(metadata={"num_qubits": 4}),
        repository_factory=lambda _: repository,
        stopped_run_result=stopped,
    )

    assert result == {"status": "PAUSED", "iterations": 3}
    checkpoint_payload = repository.save_pause_checkpoint.call_args.args[3]
    assert checkpoint_payload["stage"] == "setup"
    assert checkpoint_payload["hamiltonian_metadata"] == {"num_qubits": 4}
    stopped.assert_called_once_with("kqd", iterations=3, status="PAUSED")


@pytest.mark.parametrize("status", ["CANCELLED", "PAUSED"])
def test_pre_start_terminal_control_state_returns_stopped_result(status: str) -> None:
    session = MagicMock()
    repository = MagicMock()
    repository.request_control_state.return_value = status
    stopped = MagicMock(return_value={"status": "STOPPED"})

    result = handle_pre_start_control_state(
        session,
        run_id="run-1",
        execution_generation=2,
        algorithm="vqe",
        progress_state={},
        repository_factory=lambda _: repository,
        stopped_run_result=stopped,
    )

    assert result == {"status": "STOPPED"}
    repository.save_pause_checkpoint.assert_not_called()
    session.commit.assert_not_called()
    stopped.assert_called_once_with("vqe")


def test_setup_cancellation_returns_stopped_result_without_checkpoint() -> None:
    session = MagicMock()
    repository = MagicMock()
    repository.request_control_state.return_value = "CANCELLED"
    stopped = MagicMock(return_value={"status": "STOPPED"})

    result = handle_setup_control_state(
        session,
        run_id="run-1",
        execution_generation=1,
        algorithm="vqe",
        progress_state={},
        config_snapshot={},
        hamiltonian_bundle=SimpleNamespace(metadata={}),
        repository_factory=lambda _: repository,
        stopped_run_result=stopped,
    )

    assert result == {"status": "STOPPED"}
    repository.save_pause_checkpoint.assert_not_called()
    session.commit.assert_not_called()
    stopped.assert_called_once_with("vqe")


def test_progress_cancellation_appends_status_event_before_raising() -> None:
    db = MagicMock()
    repository = MagicMock()
    repository.request_control_state.return_value = "CANCELLED"

    with pytest.raises(RunCancelled, match="run-1"):
        check_progress_control_state(
            db,
            run_id="run-1",
            execution_generation=1,
            algorithm="vqe",
            progress_state={},
            payload={"iteration": 2},
            repository_factory=lambda _: repository,
        )

    repository.append_event.assert_called_once_with(
        "run-1", "status_changed", {"status": "CANCELLED"}
    )
    db.commit.assert_called_once()


def test_after_dispatch_pause_saves_stage_checkpoint_before_raising() -> None:
    db = MagicMock()
    repository = MagicMock()
    repository.request_control_state.return_value = "PAUSING"
    repository.save_pause_checkpoint.return_value = "checkpoint-3"
    repository.mark_paused.return_value = 1

    with pytest.raises(RunPaused, match="run-1"):
        pause_after_dispatch_if_requested(
            db,
            run_id="run-1",
            execution_generation=1,
            algorithm="vqe",
            progress_state={"monotonic_completed_iterations": 4},
            repository_factory=lambda _: repository,
        )

    checkpoint_payload = repository.save_pause_checkpoint.call_args.args[3]
    assert checkpoint_payload == {
        "stage": "after_dispatch",
        "progress_state": {"monotonic_completed_iterations": 4},
    }
    db.commit.assert_called_once()


def test_finalize_cooperative_pause_rechecks_pending_state_under_lock() -> None:
    session = MagicMock()
    session.__enter__.return_value = session
    repository = MagicMock()
    repository.request_control_state.return_value = "PAUSING"
    repository.save_pause_checkpoint.return_value = "checkpoint-4"
    repository.mark_paused.return_value = 1

    finalize_cooperative_pause(
        "run-1",
        execution_generation=1,
        algorithm="vqe",
        payload={"stage": "guard"},
        session_factory=lambda: session,
        repository_factory=lambda _: repository,
    )

    repository.request_control_state.assert_called_once_with(
        "run-1",
        1,
        for_update=True,
    )
    repository.save_pause_checkpoint.assert_called_once()
    session.commit.assert_called_once()


def test_primitive_guard_raises_pause_for_persisted_pausing_state() -> None:
    session = MagicMock()
    session.__enter__.return_value = session
    repository = MagicMock()
    repository.request_control_state.return_value = "PAUSED"

    guard = build_primitive_run_guard(
        "run-1",
        session_factory=lambda: session,
        repository_factory=lambda _: repository,
    )

    with pytest.raises(RunPaused, match="run-1"):
        guard()
