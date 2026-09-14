"""Tests for the worker persistence boundary."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from worker.persistence.run_repository import SqlRunRepository, normalize_payload_value


def _make_session() -> MagicMock:
    session = MagicMock()
    session.execute.return_value.fetchone.return_value = (3,)
    return session


def test_append_event_keeps_parent_lock_before_sequence_read() -> None:
    session = _make_session()

    SqlRunRepository(session).append_event(
        "run-1",
        "iteration_update",
        {"iteration": 2},
    )

    sql_calls = [str(call.args[0]) for call in session.execute.call_args_list]
    assert "FOR UPDATE" in sql_calls[0]
    assert "MAX(sequence)" in sql_calls[1]
    assert "INSERT INTO run_events" in sql_calls[2]


def test_get_execution_generation_defaults_when_database_has_no_value() -> None:
    session = _make_session()
    session.execute.return_value.fetchone.return_value = (None,)

    assert SqlRunRepository(session).get_execution_generation("run-1") == 1


def test_get_run_snapshot_maps_database_columns_to_worker_names() -> None:
    session = _make_session()
    session.execute.return_value.fetchone.return_value = (
        {"algorithm": "vqe"},
        {"mode": "advanced"},
        {"remaining": 2},
        {"total": 10},
        "profile-1",
    )

    assert SqlRunRepository(session).get_run_snapshot("run-1") == {
        "config_snapshot": {"algorithm": "vqe"},
        "metadata": {"mode": "advanced"},
        "latest_estimate": {"remaining": 2},
        "initial_estimate": {"total": 10},
        "credential_profile_id": "profile-1",
    }


def test_append_event_normalizes_payload_before_serializing() -> None:
    session = _make_session()
    event_id = uuid4()

    SqlRunRepository(session).append_event(
        "run-1",
        "iteration_update",
        {
            "id": event_id,
            "timestamp": datetime(2026, 1, 1, tzinfo=UTC),
            "not_finite": float("inf"),
        },
    )

    params = session.execute.call_args_list[-1].args[1]
    payload = json.loads(params["payload"])
    assert payload == {
        "id": str(event_id),
        "timestamp": "2026-01-01T00:00:00+00:00",
        "not_finite": None,
    }


def test_normalize_payload_value_handles_nested_tuples() -> None:
    assert normalize_payload_value({"values": (1, float("nan"))}) == {"values": [1, None]}


def test_normalize_payload_value_recovers_from_expected_item_errors() -> None:
    class _InvalidItem:
        def item(self) -> object:
            raise ValueError("not a scalar")

    value = _InvalidItem()

    assert normalize_payload_value(value) is value


def test_normalize_payload_value_does_not_hide_unexpected_item_errors() -> None:
    class _BrokenItem:
        def item(self) -> object:
            raise RuntimeError("unexpected conversion failure")

    with pytest.raises(RuntimeError, match="unexpected conversion failure"):
        normalize_payload_value(_BrokenItem())


def test_json_expressions_use_portable_bind_parameters_for_sqlite() -> None:
    session = _make_session()
    session.get_bind.return_value.dialect.name = "sqlite"
    repository = SqlRunRepository(session)

    assert repository._json_expression("payload") == ":payload"
    assert repository._json_expression("payload", jsonb=False) == ":payload"
    assert repository._empty_json_expression() == "'{}'"


def test_save_progress_uses_repository_owned_json_normalization() -> None:
    session = _make_session()

    SqlRunRepository(session).save_progress(
        "run-1",
        {"remaining": 2, "updated_at": datetime(2026, 1, 1, tzinfo=UTC)},
    )

    sql, params = session.execute.call_args.args
    assert "UPDATE runs SET latest_estimate" in str(sql)
    assert json.loads(params["estimate"]) == {
        "remaining": 2,
        "updated_at": "2026-01-01T00:00:00+00:00",
    }
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


def test_save_result_keeps_result_upsert_in_the_repository() -> None:
    session = _make_session()

    SqlRunRepository(session).save_result(
        "run-1",
        energy=-1.2,
        final_energy=-1.1,
        best_observed_energy=-1.2,
        reported_energy=-1.2,
        reported_energy_source="best_observed_energy",
        reference_energy=-1.0,
        reference_basis="sto-3g",
        signed_error=-0.2,
        iterations=4,
        optimal_parameters=[0.1, 0.2],
        converged=True,
        algorithm_metrics={"objective_evaluations": 4},
        raw_result={"algorithm": "vqe"},
    )

    sql, params = session.execute.call_args.args
    assert "INSERT INTO run_results" in str(sql)
    assert "ON CONFLICT (run_id) DO UPDATE" in str(sql)
    assert params["energy"] == -1.2
    assert json.loads(params["raw_result"]) == {"algorithm": "vqe"}


def test_terminal_status_updates_are_generation_guarded_and_race_safe() -> None:
    session = _make_session()
    repository = SqlRunRepository(session)

    repository.mark_completed("run-1", 7, {"run_finished_at": "now"})
    completed_sql = str(session.execute.call_args_list[-1].args[0])
    assert "status = 'COMPLETED'" in completed_sql
    assert "execution_generation = :execution_generation" in completed_sql
    assert "NOT IN ('CANCELLED', 'PAUSED', 'PAUSING', 'COMPLETED', 'FAILED')" in completed_sql

    repository.mark_failed("run-1", 7, {"error_code": "worker_job_failed"})
    failed_sql = str(session.execute.call_args_list[-1].args[0])
    assert "status = 'FAILED'" in failed_sql
    assert "execution_generation = :execution_generation" in failed_sql
    assert "NOT IN ('CANCELLED', 'PAUSED', 'PAUSING', 'COMPLETED', 'FAILED')" in failed_sql


def test_mark_running_only_claims_created_or_queued_rows() -> None:
    session = _make_session()

    SqlRunRepository(session).mark_running("run-1", 3, "now")

    sql = str(session.execute.call_args.args[0])
    assert "status IN ('CREATED', 'QUEUED')" in sql


def test_execution_segment_writes_are_generation_and_status_aware() -> None:
    session = _make_session()
    repository = SqlRunRepository(session)
    started_at = datetime(2026, 1, 1, tzinfo=UTC)

    segment_id = repository.start_execution_segment(
        "run-1",
        3,
        started_at,
        rq_job_id="rq-job-1",
    )
    assert segment_id == "3"
    start_sql, start_params = session.execute.call_args_list[-1].args
    assert "INSERT INTO run_execution_segments" in str(start_sql)
    assert start_params["execution_generation"] == 3
    assert start_params["rq_job_id"] == "rq-job-1"

    repository.heartbeat_execution_segment("3", 1.25, started_at)
    heartbeat_sql, heartbeat_params = session.execute.call_args_list[-1].args
    assert "status = 'running'" in str(heartbeat_sql)
    assert heartbeat_params["duration_seconds"] == 1.25

    repository.finish_execution_segment(
        "3",
        status="completed",
        duration_seconds=2.5,
        worker_finished_at=started_at,
        termination_reason=None,
    )
    finish_sql, finish_params = session.execute.call_args_list[-1].args
    assert "status = :status" in str(finish_sql)
    assert "WHERE id = :segment_id AND status = 'running'" in str(finish_sql)
    assert finish_params["status"] == "completed"
    assert finish_params["duration_seconds"] == 2.5


def test_recovery_queries_and_closes_abandoned_segments() -> None:
    session = _make_session()
    repository = SqlRunRepository(session)
    session.execute.return_value.fetchall.return_value = [
        ("segment-1", "run-1", 4, "rq-job-1", None, 3.5, "RUNNING")
    ]

    segments = repository.list_open_execution_segments()
    assert segments == [
        {
            "id": "segment-1",
            "run_id": "run-1",
            "execution_generation": 4,
            "rq_job_id": "rq-job-1",
            "last_heartbeat_at": None,
            "last_heartbeat_duration_seconds": 3.5,
            "run_status": "RUNNING",
        }
    ]

    repository.recover_execution_segment(
        "segment-1",
        duration_seconds=3.5,
        worker_finished_at=datetime(2026, 1, 1, tzinfo=UTC),
        termination_reason="worker_stack_restart",
    )
    segment_sql = str(session.execute.call_args_list[-1].args[0])
    assert "status = 'interrupted'" in segment_sql
    assert "status = 'running'" in segment_sql

    repository.recover_interrupted_run(
        "run-1",
        4,
        status="FAILED",
        runtime_metadata={"runtime_seconds": 3.5},
    )
    run_sql = str(session.execute.call_args_list[-1].args[0])
    assert "status IN (" in run_sql
    assert "'RUNNING', 'PAUSING', 'SUBMITTED_TO_IBM', 'PAUSED', 'FAILED', 'CANCELLED'" in run_sql


def test_execution_runtime_sums_closed_segments_and_updates_run_metadata() -> None:
    session = _make_session()
    repository = SqlRunRepository(session)
    session.execute.side_effect = None
    session.execute.return_value.fetchone.return_value = (6.5,)

    assert repository.get_closed_execution_duration("run-1") == 6.5

    repository.update_execution_runtime(
        "run-1",
        3,
        runtime_seconds=8.0,
        runtime_complete=False,
    )
    sql, params = session.execute.call_args.args
    assert "runtime_seconds" in params["runtime_metadata"]
    assert "execution_generation = :execution_generation" in str(sql)


def test_control_state_can_lock_the_run_for_a_pause_transition() -> None:
    session = _make_session()

    assert (
        SqlRunRepository(session).request_control_state(
            "run-1",
            3,
            for_update=True,
        )
        == "3"
    )

    sql, params = session.execute.call_args.args
    assert "SELECT status FROM runs" in str(sql)
    assert "execution_generation = :execution_generation" in str(sql)
    assert "FOR UPDATE" in str(sql)
    assert params == {"run_id": "run-1", "execution_generation": 3}


def test_pause_status_update_only_wins_while_request_is_still_pending() -> None:
    session = _make_session()

    SqlRunRepository(session).mark_paused("run-1", 3)

    sql, params = session.execute.call_args.args
    assert "status = 'PAUSED'" in str(sql)
    assert "status = 'PAUSING'" in str(sql)
    assert params["run_id"] == "run-1"
    assert params["execution_generation"] == 3


def test_get_run_control_snapshot_returns_status_and_generation() -> None:
    session = _make_session()
    session.execute.return_value.fetchone.return_value = ("RUNNING", 4)

    assert SqlRunRepository(session).get_run_control_snapshot("run-1", for_update=True) == (
        "RUNNING",
        4,
    )

    sql = str(session.execute.call_args.args[0])
    assert "SELECT status, execution_generation FROM runs" in sql
    assert "FOR UPDATE" in sql


def test_record_ibm_job_inserts_when_no_existing_observation_matches() -> None:
    session = _make_session()
    session.execute.return_value.rowcount = 0
    observed_at = datetime(2026, 1, 1, tzinfo=UTC)

    SqlRunRepository(session).record_ibm_job(
        "run-1",
        2,
        "ibm-job-1",
        primitive_type="EstimatorV2",
        backend_name="ibm_brisbane",
        status="QUEUED",
        submitted_at=observed_at,
        completed_at=None,
        metadata={"queue_position": 3},
        now=observed_at,
    )

    assert session.execute.call_count == 2
    insert_sql, params = session.execute.call_args_list[-1].args
    assert "INSERT INTO ibm_runtime_jobs" in str(insert_sql)
    assert params["ibm_job_id"] == "ibm-job-1"
    assert json.loads(params["job_metadata"]) == {"queue_position": 3}


def test_update_ibm_runtime_snapshot_keeps_paused_runs_protected() -> None:
    session = _make_session()
    observed_at = datetime(2026, 1, 1, tzinfo=UTC)

    SqlRunRepository(session).update_ibm_runtime_snapshot(
        "run-1",
        status="SUBMITTED_TO_IBM",
        ibm_job_id="ibm-job-1",
        runtime_metadata={"ibm_status": "QUEUED"},
        now=observed_at,
    )

    sql, params = session.execute.call_args.args
    assert "status NOT IN ('PAUSED')" in str(sql)
    assert params["status"] == "SUBMITTED_TO_IBM"
    assert json.loads(params["runtime_metadata"]) == {"ibm_status": "QUEUED"}


def test_get_chemistry_input_keeps_molecule_join_out_of_orchestration() -> None:
    session = _make_session()
    expected = ([{"symbol": "H"}], 0, 1, None, "sto-3g")
    session.execute.return_value.fetchone.return_value = expected

    assert SqlRunRepository(session).get_chemistry_input("run-1") == expected
    sql, params = session.execute.call_args.args
    assert "JOIN molecules" in str(sql)
    assert params == {"run_id": "run-1"}
