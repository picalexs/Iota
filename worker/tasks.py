"""RQ task definitions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from worker.jobs.execute_run import execute_run


def _extract_payload(
    value: str | UUID | Mapping[str, Any] | None,
    kwargs: dict[str, Any],
) -> tuple[str, int | None]:
    """Extract a run ID and optional execution generation from task arguments."""
    candidate: Any = value
    generation: int | None = None

    if candidate is None:
        candidate = kwargs.get("run_id") or kwargs.get("id") or kwargs.get("payload")

    if isinstance(candidate, Mapping):
        generation_raw = candidate.get("execution_generation")
        if isinstance(generation_raw, (int, float)):
            generation = int(generation_raw)
        candidate = candidate.get("run_id") or candidate.get("id")

    if isinstance(candidate, UUID):
        return str(candidate), generation

    if isinstance(candidate, str) and candidate:
        generation_raw = kwargs.get("execution_generation")
        if isinstance(generation_raw, (int, float)):
            generation = int(generation_raw)
        return candidate, generation

    raise ValueError("enqueueable_execute_run requires a run_id")


def enqueueable_execute_run(
    run_id: str | UUID | Mapping[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """RQ task wrapper for execute_run.

    Accepts the legacy positional string form and a payload-style mapping so the
    worker can remain compatible with richer queue contracts.
    """
    resolved_run_id, execution_generation = _extract_payload(run_id, kwargs)
    if execution_generation is None:
        return execute_run(resolved_run_id)
    return execute_run(resolved_run_id, execution_generation=execution_generation)


def seed_run_estimate(
    run_id: str | UUID | Mapping[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Compatibility no-op for older queued ETA seed jobs.

    ETA seeding runs as an API background task because the worker image does not
    ship the backend ``app`` package.
    """
    resolved_run_id, _ = _extract_payload(run_id, kwargs)
    return {"run_id": resolved_run_id, "status": "skipped"}
