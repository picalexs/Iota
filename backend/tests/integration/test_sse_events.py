"""
Integration tests for the SSE events stream endpoint.

GET /api/runs/{run_id}/events/stream
"""

from __future__ import annotations

import asyncio
from typing import Any, cast
from uuid import uuid4

import pytest
from app.models.molecule import Molecule
from app.models.run import Run, RunStatus
from app.models.run_event import RunEvent
from sqlalchemy.orm import Session

from tests.conftest import ASGISyncTestClient


@pytest.fixture(autouse=True)
def reset_sse_app_status():
    """Reset sse_starlette's module-level Event before each test.

    sse_starlette uses a module-level asyncio.Event (AppStatus.should_exit_event).
    It binds permanently to the first event loop that awaits it. Because
    ASGISyncTestClient calls asyncio.run() for every request (a new loop each time),
    the event becomes stale after the first SSE call. Replacing it with a fresh
    instance ensures each test starts with an unbound event.
    """
    from sse_starlette.sse import AppStatus

    AppStatus.should_exit_event = cast("Any", asyncio.Event())
    yield


class TestStreamRunEvents:
    """Tests for GET /api/runs/{run_id}/events/stream."""

    def test_stream_not_found_returns_404(self, client: ASGISyncTestClient):
        """Test that connecting to a stream for a non-existent run returns 404."""
        fake_id = uuid4()
        response = client.get(f"/api/runs/{fake_id}/events/stream")
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "NOT_FOUND"

    def test_stream_cancelled_run_closes_with_stream_end(
        self, client: ASGISyncTestClient, test_db: Session, sample_molecule: Molecule
    ):
        """Test streaming a CANCELLED run: the generator emits stream_end and closes."""
        run = Run(
            molecule_id=sample_molecule.id,
            status=RunStatus.CANCELLED,
            config_json={
                "basis_set": "sto-3g",
                "ansatz": "UCC",
                "optimizer": "COBYLA",
                "max_iterations": 100,
                "backend": "aer_simulator",
            },
        )
        test_db.add(run)
        test_db.commit()

        response = client.get(f"/api/runs/{run.id}/events/stream")

        assert response.status_code == 200
        # SSE stream_end sentinel must be in the body
        assert "stream_end" in response.text
        assert "CANCELLED" in response.text

    def test_stream_completed_run_closes_with_stream_end(
        self, client: ASGISyncTestClient, test_db: Session, sample_molecule: Molecule
    ):
        """Test streaming a COMPLETED run: the generator emits stream_end and closes."""
        run = Run(
            molecule_id=sample_molecule.id,
            status=RunStatus.COMPLETED,
            config_json={
                "basis_set": "sto-3g",
                "ansatz": "UCCSD",
                "optimizer": "COBYLA",
                "max_iterations": 200,
                "backend": "aer_simulator",
            },
        )
        test_db.add(run)
        test_db.commit()

        response = client.get(f"/api/runs/{run.id}/events/stream")

        assert response.status_code == 200
        assert "stream_end" in response.text
        assert "COMPLETED" in response.text

    def test_stream_includes_existing_events(
        self, client: ASGISyncTestClient, test_db: Session, sample_molecule: Molecule
    ):
        """Test that pre-existing events are included in the stream body for a terminal run."""
        run = Run(
            molecule_id=sample_molecule.id,
            status=RunStatus.COMPLETED,
            config_json={
                "basis_set": "sto-3g",
                "ansatz": "UCCSD",
                "optimizer": "COBYLA",
                "max_iterations": 100,
                "backend": "aer_simulator",
            },
        )
        test_db.add(run)
        test_db.flush()

        event = RunEvent(
            run_id=run.id,
            sequence=1,
            type="status_changed",
            payload={"status": "RUNNING"},
        )
        test_db.add(event)
        test_db.commit()

        response = client.get(f"/api/runs/{run.id}/events/stream")

        assert response.status_code == 200
        assert "status_changed" in response.text
        assert "stream_end" in response.text

    def test_stream_last_event_id_skips_seen_events(
        self, client: ASGISyncTestClient, test_db: Session, sample_molecule: Molecule
    ):
        """Test that Last-Event-ID reconnect skips already-seen events."""
        run = Run(
            molecule_id=sample_molecule.id,
            status=RunStatus.CANCELLED,
            config_json={
                "basis_set": "sto-3g",
                "ansatz": "UCC",
                "optimizer": "COBYLA",
                "max_iterations": 100,
                "backend": "aer_simulator",
            },
        )
        test_db.add(run)
        test_db.flush()

        for seq in range(1, 4):
            test_db.add(
                RunEvent(
                    run_id=run.id,
                    sequence=seq,
                    type="iteration_update",
                    payload={"iteration": seq, "energy": -1.0 - seq * 0.01},
                )
            )
        test_db.commit()

        # Reconnect starting after sequence 2 — should only see sequence 3
        response = client.get(
            f"/api/runs/{run.id}/events/stream",
            headers={"Last-Event-ID": "2"},
        )

        assert response.status_code == 200
        body = response.text
        # sequence 3 present
        assert '"sequence":3' in body or "id: 3" in body
        # sequences 1 and 2 absent (skipped by Last-Event-ID)
        assert "id: 1\n" not in body
        assert "id: 2\n" not in body

    def test_stream_includes_estimate_updated_event_payload(
        self, client: ASGISyncTestClient, test_db: Session, sample_molecule: Molecule
    ):
        """Estimate telemetry events should stream with typed estimate fields."""
        run = Run(
            molecule_id=sample_molecule.id,
            status=RunStatus.CANCELLED,
            config_json={
                "basis_set": "sto-3g",
                "ansatz": "UCC",
                "optimizer": "COBYLA",
                "max_iterations": 100,
                "backend": "aer_simulator",
            },
        )
        test_db.add(run)
        test_db.flush()

        test_db.add(
            RunEvent(
                run_id=run.id,
                sequence=1,
                type="estimate_updated",
                payload={
                    "source": "telemetry",
                    "algorithm": "vqe",
                    "estimated_total_iterations": 100,
                    "estimated_remaining_iterations": 70,
                    "estimated_total_seconds": 100.0,
                    "estimated_remaining_seconds": 70.0,
                    "confidence": 0.6,
                    "updated_at": "2026-04-09T12:00:00+00:00",
                },
            )
        )
        test_db.commit()

        response = client.get(f"/api/runs/{run.id}/events/stream")
        assert response.status_code == 200
        assert "estimate_updated" in response.text
        assert "estimated_remaining_iterations" in response.text
        assert "estimated_remaining_seconds" in response.text
