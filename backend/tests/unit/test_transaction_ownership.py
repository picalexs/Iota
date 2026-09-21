"""Unit tests for service transaction boundaries."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from app.exceptions import ConflictError
from app.services.benchmark import BenchmarkRunService
from app.services.molecule import MoleculeService
from app.services.run import RunService, _enqueue_created_run


def test_run_delete_can_join_an_outer_transaction() -> None:
    db = MagicMock()
    run_id = uuid4()
    run = MagicMock(id=run_id, run_metadata={})
    db.scalar.return_value = run
    db.scalars.return_value = []

    RunService(db).delete(run_id, commit=False)

    db.delete.assert_called_once_with(run)
    db.flush.assert_called_once_with()
    db.commit.assert_not_called()


def test_benchmark_delete_keeps_associated_run_delete_in_outer_transaction() -> None:
    db = MagicMock()
    benchmark_id = uuid4()
    run_id = uuid4()
    benchmark = MagicMock(entries=[{"runId": str(run_id)}])
    service = BenchmarkRunService(db)
    service.get_by_id = MagicMock(return_value=benchmark)
    db.scalars.return_value = [run_id]
    redis = MagicMock()

    with patch("app.services.benchmark.RunService") as run_service_class:
        service.delete(
            benchmark_id,
            delete_associated_runs=True,
            redis_client=redis,
        )

    run_service_class.assert_called_once_with(db)
    run_service_class.return_value.delete.assert_called_once_with(
        run_id,
        redis_client=redis,
        commit=False,
    )
    db.delete.assert_called_once_with(benchmark)
    db.commit.assert_called_once_with()


def test_molecule_delete_keeps_associated_run_delete_in_outer_transaction() -> None:
    db = MagicMock()
    molecule_id = uuid4()
    run_id = uuid4()
    molecule = MagicMock(runs=[MagicMock(id=run_id)])
    reloaded_molecule = MagicMock(runs=[])
    service = MoleculeService(db)
    service.get_by_id = MagicMock(side_effect=[molecule, reloaded_molecule])
    redis = MagicMock()

    with patch("app.services.molecule.RunService") as run_service_class:
        service.delete(
            molecule_id,
            delete_associated_runs=True,
            redis_client=redis,
        )

    run_service_class.assert_called_once_with(db)
    run_service_class.return_value.delete.assert_called_once_with(
        run_id,
        redis_client=redis,
        commit=False,
    )
    db.expire.assert_called_once_with(molecule, ["runs"])
    db.delete.assert_called_once_with(reloaded_molecule)
    db.commit.assert_called_once_with()


def test_created_run_enqueue_rolls_back_and_cancels_orphan_job() -> None:
    db = MagicMock()
    db.commit.side_effect = RuntimeError("database unavailable")
    run_id = uuid4()
    run = MagicMock(id=run_id, execution_generation=3, run_metadata={})
    redis = MagicMock()

    with (
        patch("app.services.run.queue_service.enqueue_run", return_value="rq-job-id") as enqueue,
        patch("app.services.run.queue_service.cancel_queued_job") as cancel,
    ):
        _enqueue_created_run(db, run=run, redis_client=redis)

    enqueue.assert_called_once_with(
        run_id,
        redis,
        execution_generation=3,
        queue_name="quantum",
    )
    db.rollback.assert_called_once_with()
    cancel.assert_called_once_with("rq-job-id", redis)
    db.refresh.assert_not_called()


@pytest.mark.asyncio
async def test_pubchem_import_rolls_back_and_sanitizes_persistence_error() -> None:
    db = MagicMock()
    db.commit.side_effect = RuntimeError("database details must stay server-side")
    service = MoleculeService(db)
    service._find_existing_import_target = MagicMock(return_value=None)
    service._find_existing_pubchem_cid = MagicMock(return_value=None)
    service._recover_pubchem_import_conflict = MagicMock(return_value=None)
    molecule_data = {
        "atoms": [{"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.0}],
        "charge": 0,
        "multiplicity": 1,
        "active_space": None,
    }

    with patch(
        "app.services.pubchem_sync.fetch_molecule_from_pubchem",
        new=AsyncMock(return_value=molecule_data),
    ):
        with pytest.raises(ConflictError) as raised:
            await service.import_from_pubchem("hydrogen")

    assert raised.value.message == "Failed to save molecule"
    assert "database details" not in raised.value.message
    db.rollback.assert_called_once_with()
