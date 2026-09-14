"""Shared fixtures for RQ callback tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

SAMPLE_RUN_ID = "00000000-0000-0000-0000-000000000002"


def make_job(run_id: str = SAMPLE_RUN_ID) -> MagicMock:
    job = MagicMock()
    job.id = "rq-job-abc"
    job.args = (run_id,)
    job.kwargs = {}
    return job


def make_session_mock() -> MagicMock:
    """Return a mock session whose execute().fetchone() returns (1,)."""
    session = MagicMock()
    fetchone_result = MagicMock()
    fetchone_result.__getitem__ = lambda self, i: 1
    session.execute.return_value.fetchone.return_value = fetchone_result
    return session


def make_exc_info(message: str = "something went wrong") -> tuple[type, Exception, Any]:
    try:
        raise ValueError(message)
    except ValueError:
        import sys

        exc_type, exc_value, exc_tb = sys.exc_info()
        return exc_type, exc_value, exc_tb  # type: ignore[return-value]
