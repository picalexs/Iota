"""Tests for the stable background-job facade."""

from __future__ import annotations

import worker.jobs as jobs


def test_jobs_facade_exports_only_stable_entrypoints() -> None:
    assert jobs.__all__ == ["execute_run", "on_job_failure", "on_job_success"]
    assert callable(jobs.execute_run)
    assert callable(jobs.on_job_failure)
    assert callable(jobs.on_job_success)
    assert not hasattr(jobs, "_insert_run_event")
