"""Tests for sanitized worker failure metadata."""

from __future__ import annotations

from worker.jobs.failure_reporting import build_public_failure_context


def test_build_public_failure_context_hides_exception_details() -> None:
    context = build_public_failure_context(
        "ValueError",
        ValueError("IBM token secret-value failed at https://service.example"),
    )

    assert context == {
        "error_code": "worker_job_failed",
        "error_message": "Run execution failed. Check worker logs for details.",
        "error_type": "ValueError",
    }
    assert "secret-value" not in str(context)
    assert "service.example" not in str(context)


def test_build_public_failure_context_classifies_configured_timeout(monkeypatch) -> None:
    monkeypatch.setenv("QUANTUM_JOB_TIMEOUT_SECONDS", "125")

    context = build_public_failure_context(
        "RuntimeError",
        RuntimeError("Task exceeded maximum timeout value"),
    )

    assert context == {
        "error_code": "worker_job_timed_out",
        "error_message": "Run timed out after reaching the 2m 5s execution limit.",
        "error_type": "RuntimeError",
        "timeout_seconds": 125,
    }


def test_build_public_failure_context_handles_invalid_timeout_configuration(monkeypatch) -> None:
    monkeypatch.setenv("QUANTUM_JOB_TIMEOUT_SECONDS", "not-a-number")

    context = build_public_failure_context("JobTimeoutException", RuntimeError("timeout"))

    assert context == {
        "error_code": "worker_job_timed_out",
        "error_message": "Run timed out after reaching the execution time limit.",
        "error_type": "JobTimeoutException",
    }
