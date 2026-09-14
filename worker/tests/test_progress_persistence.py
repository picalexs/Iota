"""Focused tests for repository-backed progress callback orchestration."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from worker.jobs.progress_persistence import emit_progress_update


def test_emit_progress_update_persists_estimate_before_iteration_event() -> None:
    db = MagicMock()
    progress_state = {
        "count": 0,
        "start_time": None,
        "ema_cost": None,
        "phase_offset": 0,
        "last_raw_completed_iterations": None,
        "monotonic_completed_iterations": 0,
    }
    estimate = {"estimated_remaining_iterations": 2}

    with (
        patch("worker.jobs.progress_persistence.check_progress_control_state") as check_control,
        patch(
            "worker.jobs.progress_persistence._build_telemetry_estimate",
            return_value=estimate,
        ),
        patch("worker.jobs.progress_persistence._persist_latest_estimate") as persist_estimate,
        patch("worker.jobs.progress_persistence.SqlRunRepository") as repository_factory,
    ):
        emit_progress_update(
            {"completed_iterations": 1, "total_iterations": 3},
            db=db,
            run_id="run-1",
            execution_generation=2,
            algorithm="vqe",
            progress_state=progress_state,
            progress_total=3,
            hamiltonian_bundle=SimpleNamespace(),
            backend_target="statevector",
            eta_seed_seconds_per_iteration=1.0,
            eta_seed_confidence=0.5,
        )

    check_control.assert_called_once()
    persist_estimate.assert_called_once_with(db, "run-1", estimate)
    repository = repository_factory.return_value
    assert [call.args[1] for call in repository.append_event.call_args_list] == [
        "estimate_updated",
        "iteration_update",
    ]
    assert repository.append_event.call_args_list[1].args[2]["completed_iterations"] == 1
    db.commit.assert_called_once()


def test_emit_progress_update_heartbeats_the_active_execution_segment() -> None:
    db = MagicMock()
    progress_state = {
        "count": 0,
        "start_time": None,
        "ema_cost": None,
        "phase_offset": 0,
        "last_raw_completed_iterations": None,
        "monotonic_completed_iterations": 0,
        "_execution_segment_id": "segment-1",
        "_execution_segment_started_monotonic": 10.0,
    }

    with (
        patch("worker.jobs.progress_persistence.check_progress_control_state"),
        patch(
            "worker.jobs.progress_persistence._build_telemetry_estimate",
            return_value={"estimated_remaining_iterations": 1},
        ),
        patch("worker.jobs.progress_persistence._persist_latest_estimate"),
        patch("worker.jobs.progress_persistence.heartbeat_execution_segment") as heartbeat,
    ):
        emit_progress_update(
            {"completed_iterations": 1, "total_iterations": 2},
            db=db,
            run_id="run-1",
            execution_generation=2,
            algorithm="vqe",
            progress_state=progress_state,
            progress_total=2,
            hamiltonian_bundle=SimpleNamespace(),
            backend_target="statevector",
            eta_seed_seconds_per_iteration=1.0,
            eta_seed_confidence=0.5,
        )

    heartbeat.assert_called_once_with(
        db,
        progress_state=progress_state,
        run_id="run-1",
        execution_generation=2,
        heartbeat_at=None,
    )
