"""PostgreSQL transaction-retry contracts for worker callbacks."""

from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, Iterator
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, create_engine, text

from worker.jobs import callbacks
from worker.persistence.run_repository import SqlRunRepository


def _database_url() -> str:
    value = os.environ.get("TEST_POSTGRES_URL", "").strip()
    if not value:
        pytest.skip("TEST_POSTGRES_URL is not configured")
    return value


def _insert_run(connection: Any, *, molecule_id: UUID, run_id: UUID) -> None:
    now = datetime.now(UTC)
    connection.execute(
        text(
            "INSERT INTO molecules "
            "(id, name, atoms, charge, multiplicity, created_at, updated_at) "
            "VALUES (:id, :name, CAST(:atoms AS jsonb), 0, 1, :created_at, :updated_at)"
        ),
        {
            "id": molecule_id,
            "name": f"retry-contract-{run_id}",
            "atoms": '[{"symbol":"H","x":0,"y":0,"z":0}]',
            "created_at": now,
            "updated_at": now,
        },
    )
    connection.execute(
        text(
            "INSERT INTO runs "
            "(id, molecule_id, status, config_json, execution_generation, created_at, updated_at) "
            "VALUES (:id, :molecule_id, 'CREATED', CAST(:config AS jsonb), 1, "
            ":created_at, :updated_at)"
        ),
        {
            "id": run_id,
            "molecule_id": molecule_id,
            "config": '{"algorithm":"vqe"}',
            "created_at": now,
            "updated_at": now,
        },
    )


@contextmanager
def _postgres_session(engine: Engine) -> Iterator[Any]:
    """Provide one transaction per callback retry attempt."""
    with engine.begin() as connection:
        yield connection


def _job_for(run_id: UUID) -> MagicMock:
    job = MagicMock()
    job.id = f"retry-contract-{run_id}"
    job.args = (str(run_id),)
    job.kwargs = {}
    return job


@pytest.mark.postgres
def test_success_callback_retries_after_postgres_transaction_failure(monkeypatch) -> None:
    """A failed PostgreSQL transaction rolls back before the callback retries."""
    engine = create_engine(_database_url())
    molecule_id = uuid4()
    run_id = uuid4()
    attempts = 0
    original_save_result = SqlRunRepository.save_result

    def fail_once(repository: SqlRunRepository, *args: Any, **kwargs: Any) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            repository._session.execute(text("SELECT 1 / 0"))
        original_save_result(repository, *args, **kwargs)

    monkeypatch.setattr(callbacks, "get_db_session", lambda: _postgres_session(engine))
    monkeypatch.setattr(SqlRunRepository, "save_result", fail_once)

    try:
        with engine.begin() as connection:
            _insert_run(connection, molecule_id=molecule_id, run_id=run_id)

        callbacks.on_job_success(
            _job_for(run_id),
            MagicMock(),
            result={"energy": -1.0, "iterations": 2, "converged": True},
        )

        with engine.connect() as connection:
            status = connection.execute(
                text("SELECT status FROM runs WHERE id = :run_id"),
                {"run_id": run_id},
            ).scalar_one()
            result_count = connection.execute(
                text("SELECT COUNT(*) FROM run_results WHERE run_id = :run_id"),
                {"run_id": run_id},
            ).scalar_one()
            event_types = (
                connection.execute(
                    text("SELECT type FROM run_events WHERE run_id = :run_id ORDER BY sequence"),
                    {"run_id": run_id},
                )
                .scalars()
                .all()
            )

        assert attempts == 2
        assert status == "COMPLETED"
        assert result_count == 1
        assert event_types == ["status_changed", "result"]
    finally:
        engine.dispose()


@pytest.mark.postgres
def test_failure_callback_retries_after_postgres_transaction_failure(monkeypatch) -> None:
    """A failed event transaction does not leave a partial FAILED callback."""
    engine = create_engine(_database_url())
    molecule_id = uuid4()
    run_id = uuid4()
    attempts = 0
    original_append_event = SqlRunRepository.append_event

    def fail_once(
        repository: SqlRunRepository,
        event_run_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            repository._session.execute(text("SELECT 1 / 0"))
        original_append_event(repository, event_run_id, event_type, payload)

    monkeypatch.setattr(callbacks, "get_db_session", lambda: _postgres_session(engine))
    monkeypatch.setattr(SqlRunRepository, "append_event", fail_once)

    try:
        with engine.begin() as connection:
            _insert_run(connection, molecule_id=molecule_id, run_id=run_id)

        callbacks.on_job_failure(
            _job_for(run_id),
            MagicMock(),
            ValueError,
            ValueError("transient database test failure"),
            None,
        )

        with engine.connect() as connection:
            status = connection.execute(
                text("SELECT status FROM runs WHERE id = :run_id"),
                {"run_id": run_id},
            ).scalar_one()
            event_types = (
                connection.execute(
                    text("SELECT type FROM run_events WHERE run_id = :run_id ORDER BY sequence"),
                    {"run_id": run_id},
                )
                .scalars()
                .all()
            )

        assert attempts == 3
        assert status == "FAILED"
        assert event_types == ["error", "status_changed"]
    finally:
        engine.dispose()
