"""Safe public failure metadata for worker job callbacks."""

from __future__ import annotations

import os
from typing import Any

PUBLIC_JOB_FAILURE_MESSAGE = "Run execution failed. Check worker logs for details."
JOB_FAILURE_ERROR_CODE = "worker_job_failed"
JOB_TIMEOUT_ERROR_CODE = "worker_job_timed_out"


def configured_job_timeout_seconds() -> int | None:
    """Read a positive worker timeout without exposing configuration details."""
    raw_value = os.environ.get("QUANTUM_JOB_TIMEOUT_SECONDS", "3600").strip()
    try:
        parsed = int(raw_value)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def format_timeout_duration(timeout_seconds: int | None) -> str | None:
    """Format a configured timeout for a user-facing failure message."""
    if timeout_seconds is None:
        return None

    if timeout_seconds < 60:
        return f"{timeout_seconds}s"

    minutes, seconds = divmod(timeout_seconds, 60)
    if minutes < 60:
        return f"{minutes}m {seconds}s"

    hours, remaining_minutes = divmod(minutes, 60)
    return f"{hours}h {remaining_minutes}m"


def build_public_failure_context(
    error_type: str,
    error_value: BaseException | None,
) -> dict[str, Any]:
    """Build sanitized API-visible metadata while keeping details in logs."""
    timeout_seconds = configured_job_timeout_seconds()
    error_text = str(error_value).strip() if error_value else ""
    is_timeout = error_type == "JobTimeoutException" or (
        "Task exceeded maximum timeout value" in error_text
    )

    if is_timeout:
        duration_label = format_timeout_duration(timeout_seconds)
        message = (
            f"Run timed out after reaching the {duration_label} execution limit."
            if duration_label is not None
            else "Run timed out after reaching the execution time limit."
        )
        payload: dict[str, Any] = {
            "error_code": JOB_TIMEOUT_ERROR_CODE,
            "error_message": message,
            "error_type": error_type,
        }
        if timeout_seconds is not None:
            payload["timeout_seconds"] = timeout_seconds
        return payload

    return {
        "error_code": JOB_FAILURE_ERROR_CODE,
        "error_message": PUBLIC_JOB_FAILURE_MESSAGE,
        "error_type": error_type,
    }


__all__ = [
    "JOB_FAILURE_ERROR_CODE",
    "JOB_TIMEOUT_ERROR_CODE",
    "PUBLIC_JOB_FAILURE_MESSAGE",
    "build_public_failure_context",
    "configured_job_timeout_seconds",
    "format_timeout_duration",
]
