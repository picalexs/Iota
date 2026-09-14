"""Tests for RQ job success callbacks."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
from unittest.mock import call as mock_call

import pytest

from worker.jobs import on_job_success
from worker.jobs.callbacks import (
    _DB_WRITE_ATTEMPTS,
    _DB_WRITE_BACKOFF_SECONDS,
)
from worker.tests._job_callback_helpers import make_job, make_session_mock

# ---------------------------------------------------------------------------
# Callback retry tests
# ---------------------------------------------------------------------------


def test_on_job_success_retries_transient_database_errors() -> None:
    job = make_job()
    session = make_session_mock()
    result = {"energy": -1.0, "iterations": 2, "converged": True}

    with (
        patch("worker.jobs.callbacks.get_db_session") as mock_ctx,
        patch("worker.jobs.callbacks.time.sleep") as sleep,
    ):
        mock_ctx.return_value.__enter__ = MagicMock(
            side_effect=[Exception("temporary"), Exception("temporary"), session]
        )
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

        on_job_success(job, MagicMock(), result=result)

    assert mock_ctx.call_count == 3
    assert sleep.call_count == 2
    assert sleep.call_args_list == [
        mock_call(_DB_WRITE_BACKOFF_SECONDS * attempt) for attempt in range(1, _DB_WRITE_ATTEMPTS)
    ]
    assert session.execute.call_count >= 4


def test_on_job_success_bounds_database_retries_and_reraises_final_error() -> None:
    job = make_job()
    database_errors = [Exception("database unavailable") for _ in range(_DB_WRITE_ATTEMPTS)]

    with (
        patch("worker.jobs.callbacks.get_db_session") as mock_ctx,
        patch("worker.jobs.callbacks.time.sleep") as sleep,
    ):
        mock_ctx.return_value.__enter__ = MagicMock(side_effect=database_errors)
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

        with pytest.raises(Exception, match="database unavailable"):
            on_job_success(job, MagicMock(), result={"energy": -1.0})

    assert mock_ctx.call_count == _DB_WRITE_ATTEMPTS
    assert sleep.call_args_list == [
        mock_call(_DB_WRITE_BACKOFF_SECONDS * attempt) for attempt in range(1, _DB_WRITE_ATTEMPTS)
    ]


# ---------------------------------------------------------------------------
# on_job_success tests
# ---------------------------------------------------------------------------


class TestOnJobSuccess:
    def test_updates_run_status_to_completed(self) -> None:
        job = make_job()
        session = make_session_mock()
        result = {"energy": -1.137, "iterations": 5, "converged": True}

        with patch("worker.jobs.callbacks.get_db_session") as mock_ctx:
            mock_ctx.return_value.__enter__ = lambda s: session
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            on_job_success(job, MagicMock(), result=result)

        executed_sqls = [str(c.args[0]) for c in session.execute.call_args_list]
        assert any("COMPLETED" in sql for sql in executed_sqls)

    @pytest.mark.parametrize(
        "result",
        [
            {"algorithm": "vqe"},
            {"algorithm": "vqe", "energy": float("nan")},
            {
                "algorithm": "vqe",
                "algorithm_metrics": {"classical_references": {"fci": -1.1}},
            },
        ],
    )
    def test_invalid_energy_marks_run_failed_without_completion(self, result: dict) -> None:
        job = make_job()
        session = make_session_mock()

        with patch("worker.jobs.callbacks.get_db_session") as mock_ctx:
            mock_ctx.return_value.__enter__ = lambda s: session
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            on_job_success(job, MagicMock(), result=result)

        executed_calls = [
            (str(call.args[0]), call.args[1] if len(call.args) > 1 else {})
            for call in session.execute.call_args_list
        ]
        assert any("SET status = 'FAILED'" in sql for sql, _ in executed_calls)
        assert not any("SET status = 'COMPLETED'" in sql for sql, _ in executed_calls)

        failure_update = next(
            params for sql, params in executed_calls if "SET status = 'FAILED'" in sql
        )
        failure_metadata = json.loads(failure_update["error"])
        assert failure_metadata["error_code"] == "invalid_result"
        assert failure_metadata["reason"] == "missing_or_non_finite_energy"

        event_types = [params.get("type") for _, params in executed_calls]
        assert "error" in event_types
        assert "status_changed" in event_types
        assert "result" not in event_types

    def test_unstable_branch_energy_marks_run_failed_without_completion(self) -> None:
        job = make_job()
        session = make_session_mock()
        result = {
            "algorithm": "qfd",
            "energy": -1.07,
            "primary_energy": -1.07,
            "iterations": 4,
            "converged": True,
            "algorithm_metrics": {
                "matrix_element_summary": {"matrix_element_strategy": "branch_estimator"},
                "stability_summary": {"stability_state": "stabilized", "dropped_rank": 1},
            },
        }

        with patch("worker.jobs.callbacks.get_db_session") as mock_ctx:
            mock_ctx.return_value.__enter__ = lambda s: session
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            on_job_success(job, MagicMock(), result=result)

        executed_calls = [
            (str(call.args[0]), call.args[1] if len(call.args) > 1 else {})
            for call in session.execute.call_args_list
        ]
        failure_update = next(
            params for sql, params in executed_calls if "SET status = 'FAILED'" in sql
        )
        failure_metadata = json.loads(failure_update["error"])
        assert failure_metadata["reason"] == "unstable_projected_metric"
        assert not any("SET status = 'COMPLETED'" in sql for sql, _ in executed_calls)

    def test_inserts_run_result_when_result_is_dict(self) -> None:
        job = make_job()
        session = make_session_mock()
        result = {
            "energy": -1.137,
            "iterations": 42,
            "optimal_parameters": [0.1, 0.2],
            "converged": True,
            "raw_result": {"extra": "data"},
        }

        with patch("worker.jobs.callbacks.get_db_session") as mock_ctx:
            mock_ctx.return_value.__enter__ = lambda s: session
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            on_job_success(job, MagicMock(), result=result)

        executed_sqls = [str(c.args[0]) for c in session.execute.call_args_list]
        assert any("run_results" in sql for sql in executed_sqls)

    def test_non_dict_result_raises_in_test_mode(self) -> None:
        """Replaces old graceful-skip test: non-dict result must raise in test mode (F1)."""
        job = make_job()
        session = make_session_mock()

        import pytest

        with patch("worker.jobs.callbacks.get_db_session") as mock_ctx:
            mock_ctx.return_value.__enter__ = lambda s: session
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            with pytest.raises(RuntimeError, match="non-dict result"):
                on_job_success(job, MagicMock(), result=None)

    def test_inserts_status_changed_run_event(self) -> None:
        job = make_job()
        session = make_session_mock()
        result = {"energy": -1.0, "iterations": 3, "converged": False}

        with patch("worker.jobs.callbacks.get_db_session") as mock_ctx:
            mock_ctx.return_value.__enter__ = lambda s: session
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            on_job_success(job, MagicMock(), result=result)

        executed_sqls = [str(c.args[0]) for c in session.execute.call_args_list]
        assert any("run_events" in sql for sql in executed_sqls)

    def test_inserts_result_run_event_when_result_is_dict(self) -> None:
        job = make_job()
        session = make_session_mock()
        result = {"energy": -1.0, "iterations": 10, "optimal_parameters": [], "converged": False}

        with patch("worker.jobs.callbacks.get_db_session") as mock_ctx:
            mock_ctx.return_value.__enter__ = lambda s: session
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            on_job_success(job, MagicMock(), result=result)

        assert session.execute.call_count >= 4

    def test_rewrites_terminal_latest_estimate_from_actual_runtime(self) -> None:
        job = make_job()
        session = make_session_mock()
        fetchone_result = session.execute.return_value.fetchone.return_value
        fetchone_result.__getitem__ = lambda self, i: (
            1,
            {
                "source": "telemetry",
                "algorithm": "vqe",
                "estimated_total_iterations": 3500,
                "estimated_remaining_iterations": 3147,
                "estimated_total_seconds": 1206.8,
                "estimated_remaining_seconds": 1202.9,
                "confidence": 0.8,
            },
        )[i]
        result = {
            "algorithm": "vqe",
            "energy": -1.0,
            "iterations": 353,
            "converged": True,
            "runtime_seconds": 5.5,
            "algorithm_metrics": {"objective_evaluations": 353},
        }

        with patch("worker.jobs.callbacks.get_db_session") as mock_ctx:
            mock_ctx.return_value.__enter__ = lambda s: session
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            on_job_success(job, MagicMock(), result=result)

        latest_estimate_update = None
        estimate_event_payload = None
        for call in session.execute.call_args_list:
            if len(call.args) < 2 or not isinstance(call.args[1], dict):
                continue
            sql = str(call.args[0])
            params = call.args[1]
            if "UPDATE runs SET latest_estimate" in sql:
                latest_estimate_update = json.loads(params["estimate"])
            if params.get("type") == "estimate_updated" and "payload" in params:
                estimate_event_payload = json.loads(params["payload"])

        assert latest_estimate_update is not None
        assert latest_estimate_update["estimated_total_iterations"] == 353
        assert latest_estimate_update["estimated_remaining_iterations"] == 0
        assert latest_estimate_update["estimated_total_seconds"] == pytest.approx(5.5)
        assert latest_estimate_update["estimated_remaining_seconds"] == pytest.approx(0.0)
        assert estimate_event_payload == latest_estimate_update

    def test_skips_success_writes_when_run_is_still_pausing(self) -> None:
        job = make_job()
        session = MagicMock()
        session.execute.return_value.fetchone.return_value = None
        result = {"energy": -1.0, "iterations": 2, "converged": False}

        with patch("worker.jobs.callbacks.get_db_session") as mock_ctx:
            mock_ctx.return_value.__enter__ = lambda s: session
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            on_job_success(job, MagicMock(), result=result)

        executed_sqls = [str(c.args[0]) for c in session.execute.call_args_list]
        assert len(executed_sqls) == 1
        assert "UPDATE runs" in executed_sqls[0]
        assert "PAUSING" in executed_sqls[0]
        assert not any("run_events" in sql for sql in executed_sqls)

    def test_normalizes_algorithm_native_result_payload(self) -> None:
        job = make_job()
        session = make_session_mock()
        result = {
            "algorithm": "sqd",
            "primary_energy": -1.221,
            "primary_iterations": 17,
            "algorithm_metrics": {"samples_per_batch": 256},
            "raw_result": {"solver": "sqd"},
        }

        with patch("worker.jobs.callbacks.get_db_session") as mock_ctx:
            mock_ctx.return_value.__enter__ = lambda s: session
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            on_job_success(job, MagicMock(), result=result)

        insert_result_params = None
        result_event_payload = None
        for call in session.execute.call_args_list:
            if len(call.args) < 2 or not isinstance(call.args[1], dict):
                continue
            sql = str(call.args[0])
            params = call.args[1]
            if "INSERT INTO run_results" in sql:
                insert_result_params = params
            if params.get("type") == "result" and "payload" in params:
                result_event_payload = json.loads(params["payload"])

        assert insert_result_params is not None
        assert insert_result_params["energy"] == -1.221
        assert insert_result_params["iterations"] == 17
        assert insert_result_params["optimal_parameters"] == "[]"
        assert insert_result_params["converged"] is False
        assert insert_result_params["algorithm_metrics"] == json.dumps({"samples_per_batch": 256})

        raw_result = json.loads(insert_result_params["raw_result"])
        assert raw_result["algorithm"] == "sqd"
        assert raw_result["algorithm_metrics"] == {"samples_per_batch": 256}
        assert raw_result["primary_energy"] == -1.221
        assert raw_result["primary_iterations"] == 17

        assert result_event_payload is not None
        assert result_event_payload["algorithm"] == "sqd"
        assert result_event_payload["energy"] == -1.221
        assert result_event_payload["iterations"] == 17
        assert result_event_payload["algorithm_metrics"] == {"samples_per_batch": 256}

    def test_persists_skqd_solution_provenance(self) -> None:
        job = make_job()
        session = make_session_mock()
        provenance = "selected_krylov_extension_classical_exact"
        result = {
            "algorithm": "skqd",
            "primary_energy": -1.221,
            "reported_energy": -1.221,
            "reported_energy_source": provenance,
            "primary_iterations": 4,
            "converged": True,
            "algorithm_metrics": {
                "krylov_extension_diagnostics": {"selected_solution": "krylov_extension"},
                "energy_policy": {"selected_solution_provenance": provenance},
            },
            "raw_result": {
                "algorithm": "skqd",
                "reported_energy_source": provenance,
            },
        }

        with patch("worker.jobs.callbacks.get_db_session") as mock_ctx:
            mock_ctx.return_value.__enter__ = lambda s: session
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            on_job_success(job, MagicMock(), result=result)

        insert_result_params = next(
            call.args[1]
            for call in session.execute.call_args_list
            if len(call.args) > 1 and "INSERT INTO run_results" in str(call.args[0])
        )

        assert insert_result_params["reported_energy_source"] == provenance
        assert json.loads(insert_result_params["raw_result"])["reported_energy_source"] == provenance

    def test_persists_enriched_sqd_diagnostics_payloads(self) -> None:
        job = make_job()
        session = make_session_mock()
        result = {
            "algorithm": "sqd",
            "primary_energy": -1.333,
            "primary_iterations": 3,
            "algorithm_metrics": {
                "sci_energies": [-1.31, -1.32, -1.333],
                "postselection_summary": {"selected_fraction": 0.67},
                "subsampling_summary": {"num_batches": 8},
                "sci_result_package": {"final_energy": -1.333},
                "configuration_recovery_trace": [{"iteration": 1}],
                "spin_diagnostics": {"spin_sq": 0.0},
            },
        }

        with patch("worker.jobs.callbacks.get_db_session") as mock_ctx:
            mock_ctx.return_value.__enter__ = lambda s: session
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            on_job_success(job, MagicMock(), result=result)

        insert_result_params = None
        for call in session.execute.call_args_list:
            if len(call.args) < 2 or not isinstance(call.args[1], dict):
                continue
            sql = str(call.args[0])
            if "INSERT INTO run_results" in sql:
                insert_result_params = call.args[1]
                break

        assert insert_result_params is not None
        parsed_algorithm_metrics = json.loads(insert_result_params["algorithm_metrics"])
        assert parsed_algorithm_metrics["postselection_summary"][
            "selected_fraction"
        ] == pytest.approx(0.67)
        assert parsed_algorithm_metrics["subsampling_summary"]["num_batches"] == 8
        assert parsed_algorithm_metrics["sci_result_package"]["final_energy"] == pytest.approx(
            -1.333
        )

    def test_sanitizes_non_finite_qfd_metrics_for_json_persistence(self) -> None:
        job = make_job()
        session = make_session_mock()
        result = {
            "algorithm": "qfd",
            "primary_energy": -9.53,
            "primary_iterations": 8,
            "converged": True,
            "algorithm_metrics": {
                "conditioning_summary": {
                    "condition_number": float("inf"),
                    "min_eigenvalue": float("nan"),
                }
            },
        }

        with patch("worker.jobs.callbacks.get_db_session") as mock_ctx:
            mock_ctx.return_value.__enter__ = lambda s: session
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            on_job_success(job, MagicMock(), result=result)

        insert_result_params = None
        for call in session.execute.call_args_list:
            if len(call.args) < 2 or not isinstance(call.args[1], dict):
                continue
            sql = str(call.args[0])
            if "INSERT INTO run_results" in sql:
                insert_result_params = call.args[1]
                break

        assert insert_result_params is not None
        metrics_json = insert_result_params["algorithm_metrics"]
        raw_result_json = insert_result_params["raw_result"]
        assert "Infinity" not in metrics_json
        assert "NaN" not in metrics_json
        assert "Infinity" not in raw_result_json
        assert "NaN" not in raw_result_json

        parsed_metrics = json.loads(metrics_json)
        assert parsed_metrics["conditioning_summary"]["condition_number"] is None
        assert parsed_metrics["conditioning_summary"]["min_eigenvalue"] is None

    def test_handles_missing_run_id_gracefully(self) -> None:
        job = MagicMock()
        job.id = "rq-job-xyz"
        job.args = ()
        job.kwargs = {}

        # Should not raise, even with no run_id
        on_job_success(job, MagicMock(), result=None)

    def test_handles_database_error_reraises_in_test_mode(self) -> None:
        """In test mode, DB exceptions in on_job_success must propagate (F2)."""
        import pytest

        job = make_job()

        with patch("worker.jobs.callbacks.get_db_session") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(side_effect=Exception("DB down"))
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            with pytest.raises(Exception, match="DB down"):
                on_job_success(job, MagicMock(), result={"energy": -1.0})

    def test_skips_success_writes_when_cancel_wins_race(self) -> None:
        job = make_job()
        session = MagicMock()
        session.execute.return_value.fetchone.return_value = None

        with patch("worker.jobs.callbacks.get_db_session") as mock_ctx:
            mock_ctx.return_value.__enter__ = lambda s: session
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            on_job_success(job, MagicMock(), result={"energy": -1.0, "iterations": 2})

        executed_sqls = [str(c.args[0]) for c in session.execute.call_args_list]
        assert len(executed_sqls) == 1
        assert "UPDATE runs" in executed_sqls[0]
        assert "COMPLETED" in executed_sqls[0]
        assert not any("run_results" in sql for sql in executed_sqls)
        assert not any("run_events" in sql for sql in executed_sqls)
