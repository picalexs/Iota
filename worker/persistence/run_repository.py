"""Worker-owned persistence boundary for run lifecycle writes."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Protocol, runtime_checkable
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session


def normalize_payload_value(value: Any) -> Any:
    """Convert common structured values into JSON-safe primitives."""
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return normalize_payload_value(item())
        except (AttributeError, TypeError, ValueError):
            pass

    if isinstance(value, Mapping):
        return {key: normalize_payload_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_payload_value(item) for item in value]
    if isinstance(value, tuple):
        return [normalize_payload_value(item) for item in value]
    if isinstance(value, float):
        # Postgres JSON/JSONB rejects NaN/Infinity tokens; persist as null.
        if not math.isfinite(value):
            return None
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    return value


@runtime_checkable
class RunRepository(Protocol):
    """Persistence operations used by worker run lifecycle code."""

    def get_execution_generation(self, run_id: str) -> int:
        """Read the current execution generation for a run."""

    def get_run_snapshot(self, run_id: str) -> dict[str, Any] | None:
        """Read the configuration snapshot needed to start a run."""

    def mark_running(self, run_id: str, execution_generation: int, run_started_at: str) -> int:
        """Move a matching run to RUNNING and return affected row count."""

    def force_run_running(self, run_id: str, execution_generation: int, run_started_at: str) -> int:
        """Force a matching generation to RUNNING after a resume path."""

    def start_execution_segment(
        self,
        run_id: str,
        execution_generation: int,
        worker_started_at: datetime,
        *,
        rq_job_id: str | None = None,
    ) -> str:
        """Create one worker execution segment."""

    def heartbeat_execution_segment(
        self,
        segment_id: str,
        duration_seconds: float,
        heartbeat_at: datetime,
    ) -> int:
        """Persist the latest known monotonic duration for a segment."""

    def finish_execution_segment(
        self,
        segment_id: str,
        *,
        status: str,
        duration_seconds: float,
        worker_finished_at: datetime,
        termination_reason: str | None = None,
    ) -> int:
        """Close one worker execution segment."""

    def list_open_execution_segments(self) -> list[dict[str, Any]]:
        """List open segments with their run control state."""

    def get_closed_execution_duration(self, run_id: str) -> float:
        """Return the durable duration of closed segments for one run."""

    def update_execution_runtime(
        self,
        run_id: str,
        execution_generation: int,
        *,
        runtime_seconds: float,
        runtime_complete: bool,
    ) -> int:
        """Publish cumulative execution timing while a run is active."""

    def recover_execution_segment(
        self,
        segment_id: str,
        *,
        duration_seconds: float,
        worker_finished_at: datetime,
        termination_reason: str,
    ) -> int:
        """Close one abandoned segment with its last durable duration."""

    def recover_interrupted_run(
        self,
        run_id: str,
        execution_generation: int,
        *,
        status: str,
        runtime_metadata: dict[str, Any],
    ) -> int:
        """Move one interrupted run to a resumable control state."""

    def mark_paused(self, run_id: str, execution_generation: int) -> int:
        """Move a matching PAUSING generation to PAUSED."""

    def request_control_state(
        self,
        run_id: str,
        execution_generation: int | None = None,
        *,
        for_update: bool = False,
    ) -> str | None:
        """Read the current control state, optionally for one generation."""

    def get_run_control_snapshot(
        self,
        run_id: str,
        *,
        for_update: bool = False,
    ) -> tuple[str | None, int] | None:
        """Read status and execution generation for a lifecycle transition."""

    def save_pause_checkpoint(
        self,
        run_id: str,
        execution_generation: int,
        algorithm: str,
        payload: dict[str, Any],
    ) -> str | None:
        """Persist one checkpoint and return its identifier."""

    def record_ibm_job(
        self,
        run_id: str,
        execution_generation: int,
        ibm_job_id: str,
        *,
        primitive_type: str | None,
        backend_name: str | None,
        status: str | None,
        submitted_at: datetime | None,
        completed_at: datetime | None,
        metadata: dict[str, Any],
        now: datetime,
    ) -> None:
        """Insert or update one IBM Runtime job observation."""

    def update_ibm_runtime_snapshot(
        self,
        run_id: str,
        *,
        status: str,
        ibm_job_id: str | None,
        runtime_metadata: dict[str, Any],
        now: datetime,
    ) -> None:
        """Persist IBM status metadata without overwriting a paused run."""

    def get_chemistry_input(self, run_id: str) -> Any | None:
        """Read the molecule fields required to construct a worker input."""

    def append_event(self, run_id: str, event_type: str, payload: dict[str, Any]) -> None:
        """Append one ordered event for a run."""

    def save_progress(self, run_id: str, estimate: dict[str, Any]) -> None:
        """Persist the latest progress estimate."""

    def save_result(
        self,
        run_id: str,
        **result_fields: Any,
    ) -> None:
        """Insert or update the result for a run."""

    def mark_completed(
        self,
        run_id: str,
        execution_generation: int | None,
        runtime_metadata: dict[str, Any],
    ) -> Any | None:
        """Mark a matching run completed and return its latest estimate."""

    def mark_failed(
        self,
        run_id: str,
        execution_generation: int | None,
        failure_metadata: dict[str, Any],
    ) -> Any | None:
        """Mark a matching run failed and return the affected row."""

    def mark_excluded(
        self,
        run_id: str,
        execution_generation: int | None,
        exclusion_metadata: dict[str, Any],
    ) -> Any | None:
        """Mark a matching run excluded and return the affected row."""


class SqlRunRepository:
    """SQLAlchemy Core implementation for worker run persistence."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def _dialect_name(self) -> str:
        """Return the active SQL dialect, defaulting to the production dialect in mocks."""
        try:
            dialect_name = self._session.get_bind().dialect.name
        except AttributeError:
            return "postgresql"
        return dialect_name if isinstance(dialect_name, str) else "postgresql"

    def _json_expression(self, parameter: str, *, jsonb: bool = True) -> str:
        """Build a portable JSON bind expression for production and unit-test databases."""
        if self._dialect_name() == "postgresql":
            return f"CAST(:{parameter} AS {'jsonb' if jsonb else 'json'})"
        return f":{parameter}"

    def _empty_json_expression(self) -> str:
        """Return an empty JSON object literal for the active SQL dialect."""
        return "'{}'::jsonb" if self._dialect_name() == "postgresql" else "'{}'"

    def _next_sequence(self, run_id: str) -> int:
        row = self._session.execute(
            text("SELECT COALESCE(MAX(sequence), 0) + 1 FROM run_events WHERE run_id = :run_id"),
            {"run_id": run_id},
        ).fetchone()
        if row is None:
            raise RuntimeError("run-event sequence query returned no row")
        return int(row[0])

    def get_execution_generation(self, run_id: str) -> int:
        row = self._session.execute(
            text("SELECT execution_generation FROM runs WHERE id = :run_id"),
            {"run_id": run_id},
        ).fetchone()
        if row and isinstance(row[0], (int, float)):
            return int(row[0])
        return 1

    def request_control_state(
        self,
        run_id: str,
        execution_generation: int | None = None,
        *,
        for_update: bool = False,
    ) -> str | None:
        """Read a run status, optionally restricting the result to one generation."""
        # These interpolated fragments are fixed internal SQL clauses. All values remain bound.
        where = "id = :run_id"
        params: dict[str, Any] = {"run_id": run_id}
        if execution_generation is not None:
            where += " AND execution_generation = :execution_generation"
            params["execution_generation"] = execution_generation
        lock_clause = " FOR UPDATE" if for_update else ""
        row = self._session.execute(
            text(f"SELECT status FROM runs WHERE {where}{lock_clause}"),  # nosec B608
            params,
        ).fetchone()
        return str(row[0]) if row and row[0] is not None else None

    def get_run_control_snapshot(
        self,
        run_id: str,
        *,
        for_update: bool = False,
    ) -> tuple[str | None, int] | None:
        """Read status and generation, optionally locking the run row."""
        lock_clause = " FOR UPDATE" if for_update else ""
        row = self._session.execute(
            text(f"SELECT status, execution_generation FROM runs WHERE id = :run_id{lock_clause}"),  # nosec B608
            {"run_id": run_id},
        ).fetchone()
        if row is None:
            return None
        status = str(row[0]) if row[0] is not None else None
        generation = int(row[1]) if row[1] is not None else 1
        return status, generation

    def mark_running(self, run_id: str, execution_generation: int, run_started_at: str) -> int:
        """Move only a queued matching run to RUNNING."""
        update_result = self._session.execute(
            text(
                "UPDATE runs "
                "SET status = 'RUNNING', updated_at = :now, "
                "metadata = COALESCE(metadata, "
                f"{self._empty_json_expression()}) || {self._json_expression('runtime_metadata')} "  # nosec B608
                "WHERE id = :run_id AND execution_generation = :execution_generation "
                "AND status IN ('CREATED', 'QUEUED')"
            ),
            {
                "now": datetime.now(UTC),
                "run_id": run_id,
                "execution_generation": execution_generation,
                "runtime_metadata": json.dumps({"run_started_at": run_started_at}),
            },
        )
        return int(getattr(update_result, "rowcount", 0) or 0)

    def start_execution_segment(
        self,
        run_id: str,
        execution_generation: int,
        worker_started_at: datetime,
        *,
        rq_job_id: str | None = None,
    ) -> str:
        """Create one worker segment after the run generation becomes owned."""
        attempt_row = self._session.execute(
            text(
                "SELECT COALESCE(MAX(attempt_number), 0) + 1 "
                "FROM run_execution_segments WHERE run_id = :run_id"
            ),
            {"run_id": run_id},
        ).fetchone()
        attempt_number = int(attempt_row[0]) if attempt_row else 1
        segment_id = str(uuid4())
        row = self._session.execute(
            text(
                "INSERT INTO run_execution_segments "
                "(id, run_id, execution_generation, attempt_number, rq_job_id, status, "
                "worker_started_at) VALUES (:id, :run_id, :execution_generation, "
                ":attempt_number, :rq_job_id, 'running', :worker_started_at) RETURNING id"
            ),
            {
                "id": segment_id,
                "run_id": run_id,
                "execution_generation": execution_generation,
                "attempt_number": attempt_number,
                "rq_job_id": rq_job_id,
                "worker_started_at": worker_started_at,
            },
        ).fetchone()
        return str(row[0]) if row else segment_id

    def heartbeat_execution_segment(
        self,
        segment_id: str,
        duration_seconds: float,
        heartbeat_at: datetime,
    ) -> int:
        """Persist the last monotonic duration known by the worker."""
        update_result = self._session.execute(
            text(
                "UPDATE run_execution_segments SET "
                "last_heartbeat_at = :heartbeat_at, "
                "last_heartbeat_duration_seconds = :duration_seconds "
                "WHERE id = :segment_id AND status = 'running'"
            ),
            {
                "segment_id": segment_id,
                "duration_seconds": duration_seconds,
                "heartbeat_at": heartbeat_at,
            },
        )
        return int(getattr(update_result, "rowcount", 0) or 0)

    def finish_execution_segment(
        self,
        segment_id: str,
        *,
        status: str,
        duration_seconds: float,
        worker_finished_at: datetime,
        termination_reason: str | None = None,
    ) -> int:
        """Close one open worker segment with its monotonic duration."""
        update_result = self._session.execute(
            text(
                "UPDATE run_execution_segments SET status = :status, "
                "worker_finished_at = :worker_finished_at, "
                "duration_seconds = :duration_seconds, "
                "last_heartbeat_at = :worker_finished_at, "
                "last_heartbeat_duration_seconds = :duration_seconds, "
                "termination_reason = :termination_reason "
                "WHERE id = :segment_id AND status = 'running'"
            ),
            {
                "segment_id": segment_id,
                "status": status,
                "worker_finished_at": worker_finished_at,
                "duration_seconds": duration_seconds,
                "termination_reason": termination_reason,
            },
        )
        return int(getattr(update_result, "rowcount", 0) or 0)

    def list_open_execution_segments(self) -> list[dict[str, Any]]:
        """List open segments and the current run control state."""
        rows = self._session.execute(
            text(
                "SELECT s.id, s.run_id, s.execution_generation, s.rq_job_id, "
                "s.last_heartbeat_at, s.last_heartbeat_duration_seconds, r.status "
                "FROM run_execution_segments AS s JOIN runs AS r ON r.id = s.run_id "
                "WHERE s.status = 'running'"
            )
        ).fetchall()
        return [
            {
                "id": str(row[0]),
                "run_id": str(row[1]),
                "execution_generation": int(row[2]),
                "rq_job_id": str(row[3]) if row[3] is not None else None,
                "last_heartbeat_at": row[4],
                "last_heartbeat_duration_seconds": row[5],
                "run_status": str(row[6]) if row[6] is not None else None,
            }
            for row in rows
        ]

    def get_closed_execution_duration(self, run_id: str) -> float:
        """Return the sum of durations already closed for one run."""
        row = self._session.execute(
            text(
                "SELECT COALESCE(SUM(duration_seconds), 0) "
                "FROM run_execution_segments "
                "WHERE run_id = :run_id AND status <> 'running'"
            ),
            {"run_id": run_id},
        ).fetchone()
        if row is None or not isinstance(row[0], (int, float)):
            return 0.0
        return max(float(row[0]), 0.0)

    def update_execution_runtime(
        self,
        run_id: str,
        execution_generation: int,
        *,
        runtime_seconds: float,
        runtime_complete: bool,
    ) -> int:
        """Publish cumulative timing without changing run control state."""
        update_result = self._session.execute(
            text(
                "UPDATE runs SET updated_at = :now, metadata = COALESCE(metadata, "  # nosec B608
                f"{self._empty_json_expression()}) || {self._json_expression('runtime_metadata')} "
                "WHERE id = :run_id AND execution_generation = :execution_generation "
                "AND status IN ("
                "'RUNNING', 'PAUSING', 'SUBMITTED_TO_IBM', 'PAUSED', 'FAILED', 'CANCELLED'"
                ")"
            ),
            {
                "now": datetime.now(UTC),
                "run_id": run_id,
                "execution_generation": execution_generation,
                "runtime_metadata": json.dumps(
                    normalize_payload_value(
                        {
                            "runtime_seconds": max(float(runtime_seconds), 0.0),
                            "runtime_basis": "worker_execution_segment_monotonic",
                            "runtime_complete": runtime_complete,
                        }
                    ),
                    allow_nan=False,
                ),
            },
        )
        return int(getattr(update_result, "rowcount", 0) or 0)

    def recover_execution_segment(
        self,
        segment_id: str,
        *,
        duration_seconds: float,
        worker_finished_at: datetime,
        termination_reason: str,
    ) -> int:
        """Close one open segment after worker lease recovery."""
        update_result = self._session.execute(
            text(
                "UPDATE run_execution_segments SET status = 'interrupted', "
                "worker_finished_at = :worker_finished_at, "
                "duration_seconds = :duration_seconds, "
                "termination_reason = :termination_reason "
                "WHERE id = :segment_id AND status = 'running'"
            ),
            {
                "segment_id": segment_id,
                "worker_finished_at": worker_finished_at,
                "duration_seconds": max(float(duration_seconds), 0.0),
                "termination_reason": termination_reason,
            },
        )
        return int(getattr(update_result, "rowcount", 0) or 0)

    def recover_interrupted_run(
        self,
        run_id: str,
        execution_generation: int,
        *,
        status: str,
        runtime_metadata: dict[str, Any],
    ) -> int:
        """Move a worker-interrupted run to FAILED or PAUSED once."""
        update_result = self._session.execute(
            text(
                "UPDATE runs SET status = :status, updated_at = :now, "  # nosec B608
                "metadata = COALESCE(metadata, "
                f"{self._empty_json_expression()}) || {self._json_expression('runtime_metadata')} "
                "WHERE id = :run_id AND execution_generation = :execution_generation "
                "AND status IN ("
                "'RUNNING', 'PAUSING', 'SUBMITTED_TO_IBM', 'PAUSED', 'FAILED', 'CANCELLED'"
                ")"
            ),
            {
                "status": status,
                "now": datetime.now(UTC),
                "run_id": run_id,
                "execution_generation": execution_generation,
                "runtime_metadata": json.dumps(
                    normalize_payload_value(runtime_metadata),
                    allow_nan=False,
                ),
            },
        )
        return int(getattr(update_result, "rowcount", 0) or 0)

    def force_run_running(self, run_id: str, execution_generation: int, run_started_at: str) -> int:
        """Set a matching run to RUNNING after an already-started execution resumes."""
        update_result = self._session.execute(
            text(
                "UPDATE runs "  # nosec B608
                "SET status = 'RUNNING', updated_at = :now, "
                "metadata = COALESCE(metadata, "
                f"{self._empty_json_expression()}) || {self._json_expression('runtime_metadata')} "
                "WHERE id = :run_id AND execution_generation = :execution_generation "
                "AND status IN ('CREATED', 'QUEUED')"
            ),
            {
                "now": datetime.now(UTC),
                "run_id": run_id,
                "execution_generation": execution_generation,
                "runtime_metadata": json.dumps({"run_started_at": run_started_at}),
            },
        )
        return int(getattr(update_result, "rowcount", 0) or 0)

    def mark_paused(self, run_id: str, execution_generation: int) -> int:
        """Move only a still-pausing generation to PAUSED."""
        update_result = self._session.execute(
            text(
                "UPDATE runs SET status = 'PAUSED', updated_at = :now "
                "WHERE id = :run_id AND execution_generation = :execution_generation "
                "AND status = 'PAUSING'"
            ),
            {
                "run_id": run_id,
                "execution_generation": execution_generation,
                "now": datetime.now(UTC),
            },
        )
        return int(getattr(update_result, "rowcount", 0) or 0)

    def save_pause_checkpoint(
        self,
        run_id: str,
        execution_generation: int,
        algorithm: str,
        payload: dict[str, Any],
    ) -> str | None:
        """Insert a checkpoint without committing the caller's transaction."""
        normalized_payload = normalize_payload_value(payload)
        checkpoint_row = self._session.execute(
            text(
                "INSERT INTO run_checkpoints "  # nosec B608
                "(id, run_id, execution_generation, algorithm, checkpoint_version, "
                f"payload, created_at) VALUES (:id, :run_id, :execution_generation, :algorithm, "
                f"'1.0', {self._json_expression('payload')}, :created_at) RETURNING id"
            ),
            {
                "run_id": run_id,
                "id": str(uuid4()),
                "execution_generation": execution_generation,
                "algorithm": algorithm,
                "payload": json.dumps(normalized_payload, allow_nan=False, default=str),
                "created_at": datetime.now(UTC),
            },
        ).fetchone()
        return str(checkpoint_row[0]) if checkpoint_row else None

    def record_ibm_job(
        self,
        run_id: str,
        execution_generation: int,
        ibm_job_id: str,
        *,
        primitive_type: str | None,
        backend_name: str | None,
        status: str | None,
        submitted_at: datetime | None,
        completed_at: datetime | None,
        metadata: dict[str, Any],
        now: datetime,
    ) -> None:
        """Insert or update one IBM Runtime job observation."""
        metadata_json = json.dumps(normalize_payload_value(metadata), allow_nan=False, default=str)
        update_result = self._session.execute(
            text(
                "UPDATE ibm_runtime_jobs "  # nosec B608
                "SET execution_generation = :execution_generation, "
                "primitive_type = COALESCE(:primitive_type, primitive_type), "
                "backend_name = COALESCE(:backend_name, backend_name), "
                "status = COALESCE(:status, status), "
                "submitted_at = COALESCE(submitted_at, :submitted_at), "
                "completed_at = COALESCE(:completed_at, completed_at), "
                f"metadata = {self._json_expression('job_metadata')}, "
                "updated_at = :now WHERE ibm_job_id = :ibm_job_id"
            ),
            {
                "execution_generation": execution_generation,
                "primitive_type": primitive_type,
                "backend_name": backend_name,
                "status": status,
                "submitted_at": submitted_at,
                "completed_at": completed_at,
                "job_metadata": metadata_json,
                "now": now,
                "ibm_job_id": ibm_job_id,
            },
        )
        if int(getattr(update_result, "rowcount", 0) or 0) != 0:
            return

        self._session.execute(
            text(
                "INSERT INTO ibm_runtime_jobs "  # nosec B608
                "(id, run_id, execution_generation, ibm_job_id, "
                "primitive_type, backend_name, status, submitted_at, "
                "completed_at, metadata, created_at, updated_at) "
                "VALUES (:id, :run_id, :execution_generation, :ibm_job_id, "
                ":primitive_type, :backend_name, :status, :submitted_at, "
                f":completed_at, {self._json_expression('job_metadata')}, :now, :now)"
            ),
            {
                "id": str(uuid4()),
                "run_id": run_id,
                "execution_generation": execution_generation,
                "ibm_job_id": ibm_job_id,
                "primitive_type": primitive_type,
                "backend_name": backend_name,
                "status": status,
                "submitted_at": submitted_at or now,
                "completed_at": completed_at,
                "job_metadata": metadata_json,
                "now": now,
            },
        )

    def update_ibm_runtime_snapshot(
        self,
        run_id: str,
        *,
        status: str,
        ibm_job_id: str | None,
        runtime_metadata: dict[str, Any],
        now: datetime,
    ) -> None:
        """Persist IBM status metadata without overwriting a paused run."""
        runtime_metadata_json = json.dumps(
            normalize_payload_value(runtime_metadata),
            allow_nan=False,
            default=str,
        )
        metadata_expression = (
            "COALESCE(metadata, "
            f"{self._empty_json_expression()}) || {self._json_expression('runtime_metadata')}"
            if self._dialect_name() == "postgresql"
            else self._json_expression("runtime_metadata")
        )
        self._session.execute(
            text(
                "UPDATE runs SET status = :status, "  # nosec B608
                "ibm_job_id = COALESCE(:ibm_job_id, ibm_job_id), "
                "updated_at = :now, "
                f"metadata = {metadata_expression} "
                "WHERE id = :run_id AND status NOT IN ('PAUSED')"
            ),
            {
                "run_id": run_id,
                "status": status,
                "ibm_job_id": ibm_job_id,
                "now": now,
                "runtime_metadata": runtime_metadata_json,
            },
        )

    def get_chemistry_input(self, run_id: str) -> Any | None:
        """Read the molecule fields required to construct a worker input."""
        return self._session.execute(
            text(
                "SELECT m.atoms, m.charge, m.multiplicity, m.active_space, r.basis_set "
                "FROM runs r JOIN molecules m ON m.id = r.molecule_id "
                "WHERE r.id = :run_id"
            ),
            {"run_id": run_id},
        ).fetchone()

    def get_run_snapshot(self, run_id: str) -> dict[str, Any] | None:
        row = self._session.execute(
            text(
                "SELECT config_json, metadata, latest_estimate, initial_estimate, "
                "credential_profile_id FROM runs WHERE id = :run_id"
            ),
            {"run_id": run_id},
        ).fetchone()
        if row is None:
            return None
        return {
            "config_snapshot": row[0] if len(row) > 0 else None,
            "metadata": row[1] if len(row) > 1 else None,
            "latest_estimate": row[2] if len(row) > 2 else None,
            "initial_estimate": row[3] if len(row) > 3 else None,
            "credential_profile_id": row[4] if len(row) > 4 else None,
        }

    def append_event(self, run_id: str, event_type: str, payload: dict[str, Any]) -> None:
        """Append an audit event while preserving the parent-row lock."""
        # Lock the parent row before reading the sequence. This is the
        # concurrency contract for event ordering and must stay in one transaction.
        self._session.execute(
            text("SELECT id FROM runs WHERE id = :run_id FOR UPDATE"),
            {"run_id": run_id},
        )

        sequence = self._next_sequence(run_id)
        normalized_payload = normalize_payload_value(payload)
        self._session.execute(
            text(
                "INSERT INTO run_events (run_id, sequence, type, payload, created_at) "  # nosec B608
                f"VALUES (:run_id, :sequence, :type, {self._json_expression('payload')}, :created_at)"
            ),
            {
                "run_id": run_id,
                "sequence": sequence,
                "type": event_type,
                "payload": json.dumps(normalized_payload),
                "created_at": datetime.now(UTC),
            },
        )

    def save_progress(self, run_id: str, estimate: dict[str, Any]) -> None:
        """Persist the latest estimate without committing the caller's transaction."""
        self._session.execute(
            text(
                "UPDATE runs SET latest_estimate = "  # nosec B608
                f"{self._json_expression('estimate')}, updated_at = :now WHERE id = :run_id"
            ),
            {
                "estimate": json.dumps(normalize_payload_value(estimate), allow_nan=False),
                "now": datetime.now(UTC),
                "run_id": run_id,
            },
        )

    def save_result(
        self,
        run_id: str,
        **result_fields: Any,
    ) -> None:
        """Insert or update a run result without committing the caller's transaction."""
        energy = result_fields["energy"]
        final_energy = result_fields["final_energy"]
        best_observed_energy = result_fields["best_observed_energy"]
        reported_energy = result_fields["reported_energy"]
        reported_energy_source = result_fields["reported_energy_source"]
        reference_energy = result_fields["reference_energy"]
        reference_basis = result_fields["reference_basis"]
        signed_error = result_fields["signed_error"]
        iterations = result_fields["iterations"]
        optimal_parameters = result_fields["optimal_parameters"]
        converged = result_fields["converged"]
        algorithm_metrics = result_fields["algorithm_metrics"]
        raw_result = result_fields["raw_result"]
        self._session.execute(
            text(
                "INSERT INTO run_results "  # nosec B608
                "(id, run_id, energy, final_energy, best_observed_energy, "
                "reported_energy, reported_energy_source, reference_energy, "
                "reference_basis, signed_error, iterations, optimal_parameters, "
                "converged, algorithm_metrics, raw_result, created_at) "
                "VALUES (:id, :run_id, :energy, :final_energy, "
                ":best_observed_energy, :reported_energy, "
                ":reported_energy_source, :reference_energy, :reference_basis, "
                ":signed_error, :iterations, "
                f"{self._json_expression('optimal_parameters', jsonb=False)}, :converged, "
                f"{self._json_expression('algorithm_metrics', jsonb=False)}, "
                f"{self._json_expression('raw_result', jsonb=False)}, :created_at) "
                "ON CONFLICT (run_id) DO UPDATE SET "
                "energy = EXCLUDED.energy, final_energy = EXCLUDED.final_energy, "
                "best_observed_energy = EXCLUDED.best_observed_energy, "
                "reported_energy = EXCLUDED.reported_energy, "
                "reported_energy_source = EXCLUDED.reported_energy_source, "
                "reference_energy = EXCLUDED.reference_energy, "
                "reference_basis = EXCLUDED.reference_basis, "
                "signed_error = EXCLUDED.signed_error, "
                "iterations = EXCLUDED.iterations, "
                "optimal_parameters = EXCLUDED.optimal_parameters, "
                "converged = EXCLUDED.converged, "
                "algorithm_metrics = EXCLUDED.algorithm_metrics, "
                "raw_result = EXCLUDED.raw_result"
            ),
            {
                "id": str(uuid4()),
                "run_id": run_id,
                "energy": energy,
                "final_energy": final_energy,
                "best_observed_energy": best_observed_energy,
                "reported_energy": reported_energy,
                "reported_energy_source": reported_energy_source,
                "reference_energy": reference_energy,
                "reference_basis": reference_basis,
                "signed_error": signed_error,
                "iterations": iterations,
                "optimal_parameters": json.dumps(
                    normalize_payload_value(optimal_parameters), allow_nan=False
                ),
                "converged": converged,
                "algorithm_metrics": (
                    json.dumps(normalize_payload_value(algorithm_metrics), allow_nan=False)
                    if algorithm_metrics is not None
                    else None
                ),
                "raw_result": json.dumps(normalize_payload_value(raw_result), allow_nan=False),
                "created_at": datetime.now(UTC),
            },
        )

    def mark_completed(
        self,
        run_id: str,
        execution_generation: int | None,
        runtime_metadata: dict[str, Any],
    ) -> Any | None:
        """Mark a matching run completed, preserving cancellation and pause races."""
        generation_clause = ""
        params: dict[str, Any] = {
            "now": datetime.now(UTC),
            "run_id": run_id,
            "runtime_metadata": json.dumps(
                normalize_payload_value(runtime_metadata), allow_nan=False
            ),
        }
        if execution_generation is not None:
            generation_clause = (
                "AND (:execution_generation IS NULL "
                "OR execution_generation = :execution_generation)"
            )
            params["execution_generation"] = execution_generation
        else:
            params["execution_generation"] = None
            generation_clause = "AND :execution_generation IS NULL"
        return self._session.execute(
            text(
                "UPDATE runs SET status = 'COMPLETED', updated_at = :now, "  # nosec B608
                "metadata = COALESCE(metadata, "
                f"{self._empty_json_expression()}) || {self._json_expression('runtime_metadata')} "
                "WHERE id = :run_id "
                "AND status NOT IN ('CANCELLED', 'PAUSED', 'PAUSING', 'COMPLETED', 'FAILED') "
                f"{generation_clause} RETURNING id, latest_estimate"
            ),
            params,
        ).fetchone()

    def mark_failed(
        self,
        run_id: str,
        execution_generation: int | None,
        failure_metadata: dict[str, Any],
    ) -> Any | None:
        """Mark a matching run failed, preserving cancellation and pause races."""
        params: dict[str, Any] = {
            "now": datetime.now(UTC),
            "run_id": run_id,
            "error": json.dumps(normalize_payload_value(failure_metadata), allow_nan=False),
            "execution_generation": execution_generation,
        }
        generation_clause = (
            "AND (:execution_generation IS NULL OR execution_generation = :execution_generation)"
        )
        return self._session.execute(
            text(
                "UPDATE runs SET status = 'FAILED', updated_at = :now, "  # nosec B608
                "metadata = COALESCE(metadata, "
                f"{self._empty_json_expression()}) || {self._json_expression('error')} "
                "WHERE id = :run_id "
                "AND status NOT IN ('CANCELLED', 'PAUSED', 'PAUSING', 'COMPLETED', 'FAILED') "
                f"{generation_clause} RETURNING id"
            ),
            params,
        ).fetchone()

    def mark_excluded(
        self,
        run_id: str,
        execution_generation: int | None,
        exclusion_metadata: dict[str, Any],
    ) -> Any | None:
        """Mark a matching run excluded, preserving cancellation and pause races."""
        params: dict[str, Any] = {
            "now": datetime.now(UTC),
            "run_id": run_id,
            "exclusion": json.dumps(
                normalize_payload_value(exclusion_metadata), allow_nan=False
            ),
            "execution_generation": execution_generation,
        }
        generation_clause = (
            "AND (:execution_generation IS NULL OR execution_generation = :execution_generation)"
        )
        return self._session.execute(
            text(
                "UPDATE runs SET status = 'EXCLUDED', updated_at = :now, "  # nosec B608
                "metadata = COALESCE(metadata, "
                f"{self._empty_json_expression()}) || {self._json_expression('exclusion')} "
                "WHERE id = :run_id "
                "AND status NOT IN "
                "('CANCELLED', 'PAUSED', 'PAUSING', 'COMPLETED', 'FAILED', 'EXCLUDED') "
                f"{generation_clause} RETURNING id"
            ),
            params,
        ).fetchone()
