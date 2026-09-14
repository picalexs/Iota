"""Tests for worker task wrappers."""

from __future__ import annotations

from unittest.mock import patch
from uuid import UUID

from worker.tasks import enqueueable_execute_run


def test_enqueueable_execute_run_accepts_legacy_string_run_id() -> None:
    with patch("worker.tasks.execute_run", return_value={"ok": True}) as mock_execute_run:
        result = enqueueable_execute_run("00000000-0000-0000-0000-000000000001")

    assert result == {"ok": True}
    mock_execute_run.assert_called_once_with("00000000-0000-0000-0000-000000000001")


def test_enqueueable_execute_run_accepts_payload_mapping() -> None:
    run_id = UUID("00000000-0000-0000-0000-000000000002")

    with patch("worker.tasks.execute_run", return_value={"ok": True}) as mock_execute_run:
        result = enqueueable_execute_run({"run_id": run_id})

    assert result == {"ok": True}
    mock_execute_run.assert_called_once_with(str(run_id))
