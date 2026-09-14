"""Tests for RQ job failure callbacks."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

from worker.jobs import on_job_failure
from worker.tests._job_callback_helpers import make_exc_info, make_job, make_session_mock

GET_DB_SESSION_PATCH = "worker.jobs.callbacks.get_db_session"


def load_error_payload(payload: object) -> dict[str, Any]:
    assert isinstance(payload, str)
    parsed = json.loads(payload)
    assert isinstance(parsed, dict)
    return parsed


# ---------------------------------------------------------------------------
# Callback retry tests
# ---------------------------------------------------------------------------


def test_on_job_failure_retries_transient_database_errors() -> None:
    job = make_job()
    session = make_session_mock()
    exc_type, exc_value, exc_tb = make_exc_info("temporary failure")

    with (
        patch(GET_DB_SESSION_PATCH) as mock_ctx,
        patch("worker.jobs.callbacks.time.sleep") as sleep,
    ):
        mock_ctx.return_value.__enter__ = MagicMock(side_effect=[Exception("temporary"), session])
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

        on_job_failure(job, MagicMock(), exc_type, exc_value, exc_tb)

    assert mock_ctx.call_count == 2
    assert sleep.call_count == 1
    assert session.execute.call_count >= 3


# ---------------------------------------------------------------------------
# on_job_failure tests
# ---------------------------------------------------------------------------


class TestOnJobFailure:
    def make_exc_info(self, message: str = "something went wrong") -> tuple[type, Exception, Any]:
        try:
            raise ValueError(message)
        except ValueError:
            import sys

            exc_type, exc_value, exc_tb = sys.exc_info()
            return exc_type, exc_value, exc_tb  # type: ignore[return-value]

    def test_routes_run_excluded_error_to_excluded_state(self) -> None:
        from worker.exceptions import RunExcludedError

        job = make_job()
        session = make_session_mock()
        try:
            raise RunExcludedError(
                "Noisy Aer QSE projected-matrix runs are limited to 6 orbitals.",
                reason="projected_matrix_active_space_too_large",
            )
        except RunExcludedError:
            import sys

            exc_type, exc_value, exc_tb = sys.exc_info()

        with patch(GET_DB_SESSION_PATCH) as mock_ctx:
            mock_ctx.return_value.__enter__ = lambda s: session
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            on_job_failure(job, MagicMock(), exc_type, exc_value, exc_tb)

        executed_sqls = [str(c.args[0]) for c in session.execute.call_args_list]
        assert any("EXCLUDED" in sql for sql in executed_sqls)
        assert not any("status = 'FAILED'" in sql for sql in executed_sqls)
        params_list = [c.args[1] for c in session.execute.call_args_list if len(c.args) > 1]
        exclusion_payloads = [
            p.get("exclusion") for p in params_list if isinstance(p, dict) and "exclusion" in p
        ]
        assert exclusion_payloads
        exclusion_data = load_error_payload(exclusion_payloads[0])
        assert exclusion_data["exclusion_reason"] == "projected_matrix_active_space_too_large"

    def test_updates_run_status_to_failed(self) -> None:
        job = make_job()
        session = make_session_mock()
        exc_type, exc_value, exc_tb = self.make_exc_info()

        with patch(GET_DB_SESSION_PATCH) as mock_ctx:
            mock_ctx.return_value.__enter__ = lambda s: session
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            on_job_failure(job, MagicMock(), exc_type, exc_value, exc_tb)

        executed_sqls = [str(c.args[0]) for c in session.execute.call_args_list]
        assert any("FAILED" in sql for sql in executed_sqls)

    def test_stores_public_error_context_in_metadata(self) -> None:
        job = make_job()
        session = make_session_mock()
        exc_type, exc_value, exc_tb = self.make_exc_info(
            "IBM token abc123 failed for https://service.example"
        )

        with patch(GET_DB_SESSION_PATCH) as mock_ctx:
            mock_ctx.return_value.__enter__ = lambda s: session
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            on_job_failure(job, MagicMock(), exc_type, exc_value, exc_tb)

        # Find the UPDATE call params
        params_list = [c.args[1] for c in session.execute.call_args_list if len(c.args) > 1]
        error_payloads = [
            p.get("error") for p in params_list if isinstance(p, dict) and "error" in p
        ]
        assert error_payloads, "No error payload found in UPDATE call"
        raw_error_payload = error_payloads[0]
        assert isinstance(raw_error_payload, str)
        error_data = load_error_payload(raw_error_payload)
        assert error_data["error_code"] == "worker_job_failed"
        assert error_data["error_message"] == "Run execution failed. Check worker logs for details."
        assert error_data["error_type"] == "ValueError"
        assert "abc123" not in raw_error_payload
        assert "service.example" not in raw_error_payload

    def test_inserts_error_and_status_changed_run_events(self) -> None:
        job = make_job()
        session = make_session_mock()
        exc_type, exc_value, exc_tb = self.make_exc_info()

        with patch(GET_DB_SESSION_PATCH) as mock_ctx:
            mock_ctx.return_value.__enter__ = lambda s: session
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            on_job_failure(job, MagicMock(), exc_type, exc_value, exc_tb)

        executed_sqls = [str(c.args[0]) for c in session.execute.call_args_list]
        run_event_inserts = [s for s in executed_sqls if "run_events" in s and "INSERT" in s]
        assert len(run_event_inserts) == 2

    def test_classifies_job_timeouts_with_public_timeout_message(self) -> None:
        class JobTimeoutException(Exception):
            pass

        job = make_job()
        session = make_session_mock()
        exc_type = JobTimeoutException
        exc_value = JobTimeoutException("Task exceeded maximum timeout value (3600 seconds)")
        exc_tb = None

        with patch(GET_DB_SESSION_PATCH) as mock_ctx:
            mock_ctx.return_value.__enter__ = lambda s: session
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            on_job_failure(job, MagicMock(), exc_type, exc_value, exc_tb)

        params_list = [c.args[1] for c in session.execute.call_args_list if len(c.args) > 1]
        error_payloads = [
            p.get("error") for p in params_list if isinstance(p, dict) and "error" in p
        ]
        assert error_payloads, "No error payload found in UPDATE call"

        error_data = load_error_payload(error_payloads[0])
        assert error_data["error_code"] == "worker_job_timed_out"
        assert error_data["error_type"] == "JobTimeoutException"
        assert (
            error_data["error_message"] == "Run timed out after reaching the 1h 0m execution limit."
        )
        assert error_data["timeout_seconds"] == 3600

    def test_handles_missing_run_id_gracefully(self) -> None:
        job = MagicMock()
        job.id = "rq-job-xyz"
        job.args = ()
        job.kwargs = {}
        exc_type, exc_value, exc_tb = self.make_exc_info()

        on_job_failure(job, MagicMock(), exc_type, exc_value, exc_tb)

    def test_handles_database_error_reraises_in_test_mode(self) -> None:
        """In test mode, DB exceptions in on_job_failure must propagate (F2)."""
        import pytest

        job = make_job()
        exc_type, exc_value, exc_tb = self.make_exc_info()

        with patch(GET_DB_SESSION_PATCH) as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(side_effect=Exception("DB down"))
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            with pytest.raises(Exception, match="DB down"):
                on_job_failure(job, MagicMock(), exc_type, exc_value, exc_tb)

    def test_traceback_not_stored_in_error_payload(self) -> None:
        job = make_job()
        session = make_session_mock()
        exc_type, exc_value, exc_tb = self.make_exc_info("boom")

        with patch(GET_DB_SESSION_PATCH) as mock_ctx:
            mock_ctx.return_value.__enter__ = lambda s: session
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            on_job_failure(job, MagicMock(), exc_type, exc_value, exc_tb)

        params_list = [c.args[1] for c in session.execute.call_args_list if len(c.args) > 1]
        error_payloads = [
            p.get("error") for p in params_list if isinstance(p, dict) and "error" in p
        ]
        error_data = load_error_payload(error_payloads[0])
        assert "traceback" not in error_data
        assert error_data["error_message"] == "Run execution failed. Check worker logs for details."

    def test_skips_failure_writes_when_cancel_wins_race(self) -> None:
        job = make_job()
        session = MagicMock()
        session.execute.return_value.fetchone.return_value = None
        exc_type, exc_value, exc_tb = self.make_exc_info("cancelled first")

        with patch(GET_DB_SESSION_PATCH) as mock_ctx:
            mock_ctx.return_value.__enter__ = lambda s: session
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            on_job_failure(job, MagicMock(), exc_type, exc_value, exc_tb)

        executed_sqls = [str(c.args[0]) for c in session.execute.call_args_list]
        assert len(executed_sqls) == 1
        assert "UPDATE runs" in executed_sqls[0]
        assert "FAILED" in executed_sqls[0]
        assert not any("run_events" in sql for sql in executed_sqls)

    def test_skips_failure_writes_when_run_is_still_pausing(self) -> None:
        job = make_job()
        session = MagicMock()
        session.execute.return_value.fetchone.return_value = None
        exc_type, exc_value, exc_tb = self.make_exc_info("pause in progress")

        with patch(GET_DB_SESSION_PATCH) as mock_ctx:
            mock_ctx.return_value.__enter__ = lambda s: session
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            on_job_failure(job, MagicMock(), exc_type, exc_value, exc_tb)

        executed_sqls = [str(c.args[0]) for c in session.execute.call_args_list]
        assert len(executed_sqls) == 1
        assert "UPDATE runs" in executed_sqls[0]
        assert "PAUSING" in executed_sqls[0]
        assert not any("run_events" in sql for sql in executed_sqls)
