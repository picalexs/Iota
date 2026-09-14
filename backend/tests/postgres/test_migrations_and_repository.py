"""Contract tests that require a PostgreSQL database created by Alembic."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text

from worker.persistence.run_repository import SqlRunRepository


def _database_url() -> str:
    value = os.environ.get("TEST_POSTGRES_URL", "").strip()
    if not value:
        pytest.skip("TEST_POSTGRES_URL is not configured")
    return value


def _insert_run(connection, *, molecule_id, run_id, now) -> None:
    """Insert the minimal migrated molecule/run pair used by repository tests."""
    connection.execute(
        text(
            "INSERT INTO molecules "
            "(id, name, atoms, charge, multiplicity, created_at, updated_at) "
            "VALUES (:id, :name, CAST(:atoms AS jsonb), 0, 1, :created_at, :updated_at)"
        ),
        {
            "id": molecule_id,
            "name": f"repository-contract-{run_id}",
            "atoms": '[{"symbol":"H","x":0,"y":0,"z":0}]',
            "created_at": now,
            "updated_at": now,
        },
    )
    connection.execute(
        text(
            "INSERT INTO runs "
            "(id, molecule_id, status, config_json, execution_generation, created_at, updated_at) "
            "VALUES (:id, :molecule_id, 'CREATED', CAST(:config AS jsonb), 1, :created_at, :updated_at)"
        ),
        {
            "id": run_id,
            "molecule_id": molecule_id,
            "config": '{"algorithm":"vqe"}',
            "created_at": now,
            "updated_at": now,
        },
    )


@pytest.mark.postgres
def test_alembic_schema_contains_lifecycle_tables() -> None:
    engine = create_engine(_database_url())
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert {"molecules", "runs", "run_events", "run_results", "run_checkpoints"} <= tables

        run_columns = {column["name"] for column in inspector.get_columns("runs")}
        assert {"execution_generation", "client_request_id", "config_json"} <= run_columns

        event_columns = {column["name"] for column in inspector.get_columns("run_events")}
        assert {"run_id", "sequence", "payload", "created_at"} <= event_columns
    finally:
        engine.dispose()


@pytest.mark.postgres
def test_repository_appends_ordered_event_on_migrated_schema() -> None:
    engine = create_engine(_database_url())
    molecule_id = uuid4()
    run_id = uuid4()
    now = datetime.now(UTC)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO molecules "
                    "(id, name, atoms, charge, multiplicity, created_at, updated_at) "
                    "VALUES (:id, :name, CAST(:atoms AS jsonb), 0, 1, :created_at, :updated_at)"
                ),
                {
                    "id": molecule_id,
                    "name": f"repository-contract-{run_id}",
                    "atoms": '[{"symbol":"H","x":0,"y":0,"z":0}]',
                    "created_at": now,
                    "updated_at": now,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO runs "
                    "(id, molecule_id, status, config_json, execution_generation, created_at, updated_at) "
                    "VALUES (:id, :molecule_id, 'CREATED', CAST(:config AS jsonb), 1, :created_at, :updated_at)"
                ),
                {
                    "id": run_id,
                    "molecule_id": molecule_id,
                    "config": '{"algorithm":"vqe"}',
                    "created_at": now,
                    "updated_at": now,
                },
            )

            SqlRunRepository(connection).append_event(
                str(run_id),
                "status_changed",
                {"status": "RUNNING", "non_finite": float("inf")},
            )

            event = connection.execute(
                text(
                    "SELECT sequence, payload->>'non_finite' FROM run_events WHERE run_id = :run_id"
                ),
                {"run_id": run_id},
            ).one()
            assert event[0] == 1
            assert event[1] is None
    finally:
        engine.dispose()


@pytest.mark.postgres
def test_repository_serializes_concurrent_event_sequences() -> None:
    """Concurrent event writers receive distinct ordered sequences."""
    engine = create_engine(_database_url(), pool_size=2, max_overflow=0)
    molecule_id = uuid4()
    run_id = uuid4()
    now = datetime.now(UTC)
    try:
        with engine.begin() as connection:
            _insert_run(connection, molecule_id=molecule_id, run_id=run_id, now=now)

        start_gate = Barrier(2)

        def append_event(event_type: str) -> None:
            with engine.begin() as connection:
                start_gate.wait(timeout=10)
                SqlRunRepository(connection).append_event(
                    str(run_id),
                    event_type,
                    {"source": event_type},
                )

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(append_event, "status_changed"),
                executor.submit(append_event, "iteration_update"),
            ]
            for future in futures:
                future.result(timeout=30)

        with engine.connect() as connection:
            events = connection.execute(
                text(
                    "SELECT sequence, type FROM run_events WHERE run_id = :run_id ORDER BY sequence"
                ),
                {"run_id": run_id},
            ).all()
            assert [sequence for sequence, _ in events] == [1, 2]
            assert {event_type for _, event_type in events} == {
                "status_changed",
                "iteration_update",
            }
    finally:
        engine.dispose()


@pytest.mark.postgres
def test_repository_covers_run_lifecycle_on_migrated_schema() -> None:
    engine = create_engine(_database_url())
    molecule_id = uuid4()
    run_id = uuid4()
    now = datetime.now(UTC)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO molecules "
                    "(id, name, atoms, charge, multiplicity, created_at, updated_at) "
                    "VALUES (:id, :name, CAST(:atoms AS jsonb), 0, 1, :created_at, :updated_at)"
                ),
                {
                    "id": molecule_id,
                    "name": f"repository-lifecycle-{run_id}",
                    "atoms": '[{"symbol":"H","x":0,"y":0,"z":0}]',
                    "created_at": now,
                    "updated_at": now,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO runs "
                    "(id, molecule_id, status, config_json, execution_generation, "
                    "created_at, updated_at) "
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

            repository = SqlRunRepository(connection)
            chemistry_row = repository.get_chemistry_input(str(run_id))
            assert chemistry_row is not None
            assert chemistry_row[0][0]["symbol"] == "H"

            assert repository.mark_running(str(run_id), 1, now.isoformat()) == 1
            repository.save_progress(str(run_id), {"estimated_remaining_iterations": 2})
            repository.append_event(str(run_id), "status_changed", {"status": "RUNNING"})

            connection.execute(
                text("UPDATE runs SET status = 'PAUSING' WHERE id = :run_id"),
                {"run_id": run_id},
            )
            checkpoint_id = repository.save_pause_checkpoint(
                str(run_id),
                1,
                "vqe",
                {"iteration": 2, "state": (1, 2)},
            )
            assert checkpoint_id is not None
            assert repository.mark_paused(str(run_id), 1) == 1
            repository.append_event(
                str(run_id),
                "checkpoint_saved",
                {"checkpoint_id": checkpoint_id},
            )

            connection.execute(
                text("UPDATE runs SET status = 'RUNNING' WHERE id = :run_id"),
                {"run_id": run_id},
            )
            repository.save_result(
                str(run_id),
                energy=-1.2,
                final_energy=-1.1,
                best_observed_energy=-1.2,
                reported_energy=-1.2,
                reported_energy_source="best_observed_energy",
                reference_energy=-1.0,
                reference_basis="sto-3g",
                signed_error=-0.2,
                iterations=2,
                optimal_parameters=[0.1],
                converged=True,
                algorithm_metrics={"objective_evaluations": 2},
                raw_result={"algorithm": "vqe"},
            )
            completed_row = repository.mark_completed(
                str(run_id),
                1,
                {"run_finished_at": now.isoformat()},
            )
            assert completed_row is not None
            assert repository.mark_completed(str(run_id), 1, {}) is None
            assert repository.mark_failed(str(run_id), 1, {}) is None

            repository.record_ibm_job(
                str(run_id),
                1,
                "contract-ibm-job",
                primitive_type="EstimatorV2",
                backend_name="ibm_brisbane",
                status="DONE",
                submitted_at=now,
                completed_at=now,
                metadata={"shots": 128},
                now=now,
            )

            event_sequences = (
                connection.execute(
                    text(
                        "SELECT sequence FROM run_events WHERE run_id = :run_id ORDER BY sequence"
                    ),
                    {"run_id": run_id},
                )
                .scalars()
                .all()
            )
            assert event_sequences == list(range(1, len(event_sequences) + 1))

            result = connection.execute(
                text("SELECT energy, iterations FROM run_results WHERE run_id = :run_id"),
                {"run_id": run_id},
            ).one()
            assert result == (-1.2, 2)

            ibm_job = connection.execute(
                text(
                    "SELECT status, metadata->>'shots' FROM ibm_runtime_jobs "
                    "WHERE ibm_job_id = :ibm_job_id"
                ),
                {"ibm_job_id": "contract-ibm-job"},
            ).one()
            assert ibm_job == ("DONE", "128")
    finally:
        engine.dispose()


@pytest.mark.postgres
def test_repository_result_upsert_keeps_one_row_on_repeated_success() -> None:
    """Repeated callback persistence updates the migrated result row in place."""
    engine = create_engine(_database_url())
    molecule_id = uuid4()
    run_id = uuid4()
    now = datetime.now(UTC)
    try:
        with engine.begin() as connection:
            _insert_run(connection, molecule_id=molecule_id, run_id=run_id, now=now)
            repository = SqlRunRepository(connection)
            result_kwargs = {
                "final_energy": -1.0,
                "best_observed_energy": -1.2,
                "reported_energy": -1.1,
                "reported_energy_source": "final_energy",
                "reference_energy": -1.0,
                "reference_basis": "sto-3g",
                "signed_error": -0.1,
                "iterations": 3,
                "optimal_parameters": [0.1],
                "converged": True,
                "algorithm_metrics": {"objective_evaluations": 3},
                "raw_result": {"algorithm": "vqe"},
            }
            repository.save_result(str(run_id), energy=-1.1, **result_kwargs)
            repository.save_result(
                str(run_id),
                energy=-1.25,
                **{
                    **result_kwargs,
                    "iterations": 4,
                    "raw_result": {"algorithm": "vqe", "retry": 1},
                },
            )

            rows = connection.execute(
                text(
                    "SELECT energy, iterations, raw_result->>'retry' "
                    "FROM run_results WHERE run_id = :run_id"
                ),
                {"run_id": run_id},
            ).all()
            assert rows == [(-1.25, 4, "1")]
    finally:
        engine.dispose()


@pytest.mark.postgres
def test_repository_rejects_stale_execution_generation() -> None:
    """Generation-guarded writes do not mutate a run owned by a newer attempt."""
    engine = create_engine(_database_url())
    molecule_id = uuid4()
    run_id = uuid4()
    now = datetime.now(UTC)
    try:
        with engine.begin() as connection:
            _insert_run(connection, molecule_id=molecule_id, run_id=run_id, now=now)
            repository = SqlRunRepository(connection)

            assert repository.mark_running(str(run_id), 2, now.isoformat()) == 0
            assert repository.mark_completed(str(run_id), 2, {}) is None
            status, generation = repository.get_run_control_snapshot(str(run_id))
            assert status == "CREATED"
            assert generation == 1
    finally:
        engine.dispose()


@pytest.mark.postgres
def test_repository_writes_roll_back_with_caller_transaction() -> None:
    """Event/result writes disappear when the caller rolls back their unit of work."""
    engine = create_engine(_database_url())
    molecule_id = uuid4()
    run_id = uuid4()
    now = datetime.now(UTC)
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                _insert_run(connection, molecule_id=molecule_id, run_id=run_id, now=now)
                repository = SqlRunRepository(connection)
                repository.append_event(str(run_id), "status_changed", {"status": "RUNNING"})
                repository.save_result(
                    str(run_id),
                    energy=-1.1,
                    final_energy=-1.1,
                    best_observed_energy=-1.1,
                    reported_energy=-1.1,
                    reported_energy_source="final_energy",
                    reference_energy=None,
                    reference_basis=None,
                    signed_error=None,
                    iterations=1,
                    optimal_parameters=[],
                    converged=False,
                    algorithm_metrics={},
                    raw_result={"algorithm": "vqe"},
                )
                raise RuntimeError("simulated callback failure")
            except RuntimeError:
                transaction.rollback()

            assert (
                connection.execute(
                    text("SELECT COUNT(*) FROM run_events WHERE run_id = :run_id"),
                    {"run_id": run_id},
                ).scalar_one()
                == 0
            )
            assert (
                connection.execute(
                    text("SELECT COUNT(*) FROM run_results WHERE run_id = :run_id"),
                    {"run_id": run_id},
                ).scalar_one()
                == 0
            )
            assert (
                connection.execute(
                    text("SELECT COUNT(*) FROM runs WHERE id = :run_id"),
                    {"run_id": run_id},
                ).scalar_one()
                == 0
            )
    finally:
        engine.dispose()
