"""RQ callback entrypoints and persistence/retry coordination."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from worker.db import get_db_session
from worker.exceptions import InvalidResultError, RunExcludedError
from worker.jobs.result_normalization import (
    ResultPersistencePayload,
    build_terminal_latest_estimate,
    normalize_result_for_persistence,
    terminal_runtime_metadata,
)
from worker.persistence.run_repository import SqlRunRepository

from . import failure_reporting as _failure_reporting

JOB_FAILURE_ERROR_CODE = _failure_reporting.JOB_FAILURE_ERROR_CODE
JOB_TIMEOUT_ERROR_CODE = _failure_reporting.JOB_TIMEOUT_ERROR_CODE
PUBLIC_JOB_FAILURE_MESSAGE = _failure_reporting.PUBLIC_JOB_FAILURE_MESSAGE
_build_public_failure_context = _failure_reporting.build_public_failure_context
_configured_job_timeout_seconds = _failure_reporting.configured_job_timeout_seconds
_format_timeout_duration = _failure_reporting.format_timeout_duration

if TYPE_CHECKING:
    from rq.job import Job

logger = logging.getLogger(__name__)

_DB_WRITE_ATTEMPTS = 3
_DB_WRITE_BACKOFF_SECONDS = 0.05


def _job_run_identity(job: Job) -> tuple[str, int | None]:
    """Extract run id and execution generation from legacy or payload RQ args."""
    candidate: Any = job.args[0] if job.args else job.kwargs.get("run_id", "")
    generation: int | None = None
    if isinstance(candidate, Mapping):
        generation_raw = candidate.get("execution_generation")
        if isinstance(generation_raw, (int, float)):
            generation = int(generation_raw)
        candidate = candidate.get("run_id") or candidate.get("id") or ""
    return str(candidate), generation


def _insert_success_result_event(
    *,
    session: Any,
    run_id: str,
    normalized_result: ResultPersistencePayload,
) -> None:
    _, iterations, _, converged, raw_payload, _, provenance = normalized_result
    SqlRunRepository(session).append_event(
        run_id,
        "result",
        {
            "algorithm": raw_payload.get("algorithm"),
            "energy": provenance.get("reported_energy"),
            "final_energy": provenance.get("final_energy"),
            "best_observed_energy": provenance.get("best_observed_energy"),
            "reported_energy_source": provenance.get("reported_energy_source"),
            "iterations": iterations,
            "converged": converged,
            "algorithm_metrics": raw_payload.get("algorithm_metrics"),
        },
    )


def _normalize_success_result(
    *,
    result: Any,
    run_id: str,
) -> ResultPersistencePayload | None:
    if isinstance(result, dict):
        return normalize_result_for_persistence(result)

    logger.error(
        "on_job_success: result for run %s is %s (expected dict); "
        "run_results row will be missing — check solver return type",
        run_id,
        type(result).__name__,
    )
    return None


def _persist_invalid_success_output(
    *,
    repository: SqlRunRepository,
    run_id: str,
    execution_generation: int | None,
    job_id: str,
    runtime_metadata: dict[str, Any],
    reason: str,
    message: str,
) -> bool:
    failure_metadata = {
        **runtime_metadata,
        "error_code": "invalid_result",
        "error_message": message,
        "error_type": "InvalidResult",
        "reason": reason,
        "failed_job_id": job_id,
    }
    updated_row = repository.mark_failed(run_id, execution_generation, failure_metadata)
    if updated_row is None:
        logger.info(
            "Run %s was cancelled/paused/pausing/stale; skipping invalid-result callback",
            run_id,
        )
        return True
    repository.append_event(run_id, "error", failure_metadata)
    repository.append_event(
        run_id,
        "status_changed",
        {"status": "FAILED", "job_id": job_id},
    )
    return True


def _persist_success_result_and_estimate(
    *,
    session: Any,
    run_id: str,
    result: dict[str, Any],
    now: datetime,
    latest_estimate: Any,
    normalized_result: ResultPersistencePayload,
) -> None:
    repository = SqlRunRepository(session)
    (
        energy,
        iterations,
        optimal_parameters,
        converged,
        raw_payload,
        algorithm_metrics,
        provenance,
    ) = normalized_result
    repository.save_result(
        run_id,
        energy=energy,
        final_energy=provenance.get("final_energy"),
        best_observed_energy=provenance.get("best_observed_energy"),
        reported_energy=provenance.get("reported_energy"),
        reported_energy_source=provenance.get("reported_energy_source"),
        reference_energy=provenance.get("reference_energy"),
        reference_basis=provenance.get("reference_basis"),
        signed_error=provenance.get("signed_error"),
        iterations=iterations,
        optimal_parameters=optimal_parameters,
        converged=converged,
        algorithm_metrics=algorithm_metrics,
        raw_result=raw_payload,
    )
    terminal_estimate = build_terminal_latest_estimate(
        result=result,
        finished_at=now,
        latest_estimate=latest_estimate,
        normalized_result=normalized_result,
    )
    if terminal_estimate is None:
        return

    repository.save_progress(run_id, terminal_estimate)
    repository.append_event(run_id, "estimate_updated", terminal_estimate)


def _persist_invalid_success_result(
    *,
    repository: SqlRunRepository,
    run_id: str,
    execution_generation: int | None,
    job_id: str,
    runtime_metadata: dict[str, Any],
    normalized_result: ResultPersistencePayload,
) -> bool:
    provenance = normalized_result[-1]
    if provenance.get("reported_energy_is_valid", False):
        return False
    reason = provenance.get("reported_energy_invalid_reason", "missing_or_non_finite_energy")
    return _persist_invalid_success_output(
        repository=repository,
        run_id=run_id,
        execution_generation=execution_generation,
        job_id=job_id,
        runtime_metadata=runtime_metadata,
        reason=reason,
        message=f"Run returned an invalid algorithm energy: {reason}.",
    )


def _run_db_write_with_retries(
    *,
    callback_name: str,
    run_id: str,
    write: Callable[[], None],
) -> None:
    """Run a callback DB write with bounded retries and backoff."""
    for attempt in range(1, _DB_WRITE_ATTEMPTS + 1):
        try:
            write()
            return
        except Exception:
            if attempt >= _DB_WRITE_ATTEMPTS:
                logger.exception(
                    "%s: failed to update database for run %s after %d attempts",
                    callback_name,
                    run_id,
                    attempt,
                )
                raise
            logger.warning(
                "%s: database update failed for run %s on attempt %d/%d; retrying",
                callback_name,
                run_id,
                attempt,
                _DB_WRITE_ATTEMPTS,
                exc_info=True,
            )
            time.sleep(_DB_WRITE_BACKOFF_SECONDS * attempt)


def _write_success_callback(
    *,
    job_id: str,
    run_id: str,
    execution_generation: int | None,
    result: Any,
) -> None:
    with get_db_session() as session:
        repository = SqlRunRepository(session)
        now = datetime.now(UTC)
        runtime_metadata = terminal_runtime_metadata(
            finished_at=now,
            result=result if isinstance(result, dict) else None,
        )
        try:
            normalized_result = _normalize_success_result(result=result, run_id=run_id)
        except InvalidResultError as exc:
            _persist_invalid_success_output(
                repository=repository,
                run_id=run_id,
                execution_generation=execution_generation,
                job_id=job_id,
                runtime_metadata=runtime_metadata,
                reason=exc.reason,
                message="Run returned an invalid result payload.",
            )
            return
        if normalized_result is None:
            _persist_invalid_success_output(
                repository=repository,
                run_id=run_id,
                execution_generation=execution_generation,
                job_id=job_id,
                runtime_metadata=runtime_metadata,
                reason="non_dict_result",
                message="Run returned a non-object result payload.",
            )
            return
        if _persist_invalid_success_result(
            repository=repository,
            run_id=run_id,
            execution_generation=execution_generation,
            job_id=job_id,
            runtime_metadata=runtime_metadata,
            normalized_result=normalized_result,
        ):
            return

        updated_row = repository.mark_completed(
            run_id,
            execution_generation,
            runtime_metadata,
        )
        if updated_row is None:
            logger.info(
                "Run %s was cancelled/paused/pausing/stale; skipping success callback",
                run_id,
            )
            return
        if isinstance(result, dict):
            _persist_success_result_and_estimate(
                session=session,
                run_id=run_id,
                result=result,
                now=now,
                latest_estimate=updated_row[1] if len(updated_row) > 1 else None,
                normalized_result=normalized_result,
            )
        repository.append_event(
            run_id,
            "status_changed",
            {"status": "COMPLETED", "job_id": job_id},
        )
        _insert_success_result_event(
            session=session,
            run_id=run_id,
            normalized_result=normalized_result,
        )


def on_job_success(job: Job, _connection: Any, result: Any, *_args: Any, **_kwargs: Any) -> None:
    """RQ success callback: validate and persist a terminal run result."""
    run_id, execution_generation = _job_run_identity(job)
    if not run_id:
        logger.error("on_job_success: could not determine run_id from job %s", job.id)
        return

    logger.info("Job %s succeeded for run %s", job.id, run_id)

    _run_db_write_with_retries(
        callback_name="on_job_success",
        run_id=run_id,
        write=lambda: _write_success_callback(
            job_id=job.id,
            run_id=run_id,
            execution_generation=execution_generation,
            result=result,
        ),
    )


def _write_run_excluded(
    *,
    job: Job,
    run_id: str,
    execution_generation: int | None,
    value: BaseException,
) -> None:
    """Persist an EXCLUDED terminal state for a valid-but-unsupported run."""
    reason = getattr(value, "reason", "excluded")
    message = str(value) or "Run excluded from the requested target."

    def _write() -> None:
        with get_db_session() as session:
            repository = SqlRunRepository(session)
            now = datetime.now(UTC)
            exclusion_metadata = {
                **terminal_runtime_metadata(finished_at=now),
                "exclusion_reason": reason,
                "exclusion_message": message,
                "excluded_job_id": job.id,
            }
            updated_row = repository.mark_excluded(
                run_id,
                execution_generation,
                exclusion_metadata,
            )
            if updated_row is None:
                logger.info(
                    "Run %s was cancelled/paused/terminal; skipping exclusion callback", run_id
                )
                return
            repository.append_event(
                run_id,
                "status_changed",
                {
                    "status": "EXCLUDED",
                    "job_id": job.id,
                    "exclusion_reason": reason,
                    "exclusion_message": message,
                },
            )

    _run_db_write_with_retries(callback_name="on_job_excluded", run_id=run_id, write=_write)


def on_job_failure(
    job: Job,
    _connection: Any,
    type: type[BaseException],
    value: BaseException,
    _traceback: Any,
) -> None:
    """RQ failure callback: mark the Run FAILED and record error details."""
    run_id, execution_generation = _job_run_identity(job)
    if not run_id:
        logger.error("on_job_failure: could not determine run_id from job %s", job.id)
        return

    error_type = type.__name__ if type else "Unknown"
    logger.error("Job %s failed for run %s with %s", job.id, run_id, error_type)

    if type is not None and issubclass(type, RunExcludedError):
        _write_run_excluded(job=job, run_id=run_id, execution_generation=execution_generation, value=value)
        return

    public_failure = _build_public_failure_context(error_type, value)

    # Keep detailed exception text out of API-visible metadata/events.
    logger.debug("Full traceback for run %s", run_id, exc_info=(type, value, _traceback))

    def _write_failure() -> None:
        with get_db_session() as session:
            repository = SqlRunRepository(session)
            now = datetime.now(UTC)
            failure_metadata = {
                **terminal_runtime_metadata(finished_at=now),
                **public_failure,
                "failed_job_id": job.id,
            }
            # Persist only minimal error context; stack traces remain in logs.
            updated_row = repository.mark_failed(
                run_id,
                execution_generation,
                failure_metadata,
            )
            if updated_row is None:
                logger.info(
                    "Run %s was cancelled/paused/pausing; skipping failure callback", run_id
                )
                return

            # Audit events carry the same sanitized error context.
            repository.append_event(
                run_id,
                "error",
                {
                    **public_failure,
                    "job_id": job.id,
                },
            )
            repository.append_event(
                run_id,
                "status_changed",
                {"status": "FAILED", "job_id": job.id},
            )

    _run_db_write_with_retries(
        callback_name="on_job_failure",
        run_id=run_id,
        write=_write_failure,
    )


__all__ = ["on_job_success", "on_job_failure"]
