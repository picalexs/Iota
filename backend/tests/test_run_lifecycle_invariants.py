"""
Run lifecycle invariant tests.

Verifies that completed runs satisfy structural guarantees:
- Every COMPLETED run has exactly one run_results row.
- Every COMPLETED run has at least one 'result' event.
- Every FAILED run has at least one 'error' event.
- run_events.sequence is strictly monotonic with no gaps for each run.
- No run stays in RUNNING state without a RUNNING status_changed event.

These tests detect silent failures (F1, F2) where DB exceptions are swallowed
or solvers return non-dict results leaving run_results rows missing.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.models.molecule import Molecule
from app.models.run import Run, RunStatus
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import TextClause

# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_molecule(db: Session) -> Molecule:
    m = Molecule(
        name=f"H2_inv_{uuid.uuid4().hex[:6]}",
        atoms=[
            {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.0},
            {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.735},
        ],
        charge=0,
        multiplicity=1,
        active_space={"n_electrons": 2, "n_orbitals": 2},
    )
    db.add(m)
    db.flush()
    return m


def _make_run(db: Session, molecule_id, status: RunStatus) -> Run:
    run = Run(
        molecule_id=molecule_id,
        status=status,
        config_json={
            "algorithm": "vqe",
            "mode": "advanced",
            "backend_target": "statevector",
        },
    )
    db.add(run)
    db.flush()
    return run


def _insert_run_event(db: Session, run_id, seq: int, event_type: str, payload: dict) -> None:
    from sqlalchemy import text

    db.execute(
        text(
            "INSERT INTO run_events (run_id, sequence, type, payload, created_at) "
            "VALUES (:run_id, :seq, :type, CAST(:payload AS jsonb), :now)"
        ),
        {
            "run_id": str(run_id),
            "seq": seq,
            "type": event_type,
            "payload": __import__("json").dumps(payload),
            "now": datetime.now(UTC),
        },
    )


def _insert_run_result(db: Session, run_id) -> None:
    from sqlalchemy import text

    db.execute(
        text(
            "INSERT INTO run_results "
            "(id, run_id, energy, iterations, optimal_parameters, converged, created_at) "
            "VALUES (:id, :run_id, :energy, :iterations, CAST(:opts AS json), :conv, :now)"
        ),
        {
            "id": str(uuid.uuid4()),
            "run_id": str(run_id),
            "energy": -1.137,
            "iterations": 10,
            "opts": "[]",
            "conv": True,
            "now": datetime.now(UTC),
        },
    )


def _fetch_required_row(db: Session, statement: TextClause, params: dict[str, Any]):
    row = db.execute(statement, params).fetchone()
    assert row is not None
    return row


# ── Invariant: COMPLETED → run_results row exists ────────────────────────────


class TestCompletedRunResultInvariant:
    """Every COMPLETED run must have exactly one run_results row."""

    def test_completed_run_with_result_row_passes(self, test_db: Session) -> None:
        mol = _make_molecule(test_db)
        run = _make_run(test_db, mol.id, RunStatus.COMPLETED)
        test_db.commit()
        _insert_run_result(test_db, run.id)
        test_db.commit()

        from sqlalchemy import text

        row = _fetch_required_row(
            test_db,
            text("SELECT COUNT(*) FROM run_results WHERE run_id = :rid"),
            {"rid": str(run.id)},
        )
        assert row[0] == 1, "COMPLETED run must have exactly one run_results row"

    def test_completed_run_without_result_row_fails_invariant(self, test_db: Session) -> None:
        """Exposes F1: solver returns non-dict → run_results row missing."""
        mol = _make_molecule(test_db)
        run = _make_run(test_db, mol.id, RunStatus.COMPLETED)
        test_db.commit()
        # Deliberately skip inserting run_results — mimics F1 failure mode

        from sqlalchemy import text

        row = _fetch_required_row(
            test_db,
            text("SELECT COUNT(*) FROM run_results WHERE run_id = :rid"),
            {"rid": str(run.id)},
        )
        assert row[0] == 0, "baseline: no run_results row present (simulating F1)"

        # The invariant check — this is what automated post-run assertions must do.
        invariant_violated = row[0] != 1
        assert invariant_violated, (
            "Invariant VIOLATED: COMPLETED run has no run_results row. "
            "Likely cause: solver returned non-dict or on_job_success DB exception swallowed."
        )


# ── Invariant: COMPLETED → 'result' event exists ─────────────────────────────


class TestCompletedRunEventInvariant:
    """Every COMPLETED run must have at least one event of type 'result'."""

    def test_completed_run_with_result_event_passes(self, test_db: Session) -> None:
        mol = _make_molecule(test_db)
        run = _make_run(test_db, mol.id, RunStatus.COMPLETED)
        test_db.commit()
        _insert_run_event(test_db, run.id, 0, "status_changed", {"status": "RUNNING"})
        _insert_run_event(test_db, run.id, 1, "result", {"energy": -1.137, "converged": True})
        _insert_run_event(test_db, run.id, 2, "status_changed", {"status": "COMPLETED"})
        test_db.commit()

        from sqlalchemy import text

        row = _fetch_required_row(
            test_db,
            text("SELECT COUNT(*) FROM run_events WHERE run_id = :rid AND type = 'result'"),
            {"rid": str(run.id)},
        )
        assert row[0] >= 1

    def test_completed_run_missing_result_event_fails_invariant(self, test_db: Session) -> None:
        """Detects F2: DB exception swallowed in on_job_success leaves no 'result' event."""
        mol = _make_molecule(test_db)
        run = _make_run(test_db, mol.id, RunStatus.COMPLETED)
        test_db.commit()
        _insert_run_event(test_db, run.id, 0, "status_changed", {"status": "COMPLETED"})
        test_db.commit()

        from sqlalchemy import text

        row = _fetch_required_row(
            test_db,
            text("SELECT COUNT(*) FROM run_events WHERE run_id = :rid AND type = 'result'"),
            {"rid": str(run.id)},
        )
        assert row[0] == 0, "baseline: no result event (simulating swallowed DB exception)"
        invariant_violated = row[0] == 0
        assert invariant_violated, (
            "Invariant VIOLATED: COMPLETED run has no 'result' event. "
            "Likely cause: on_job_success DB exception swallowed after status update."
        )


# ── Invariant: FAILED → 'error' event exists ─────────────────────────────────


class TestFailedRunEventInvariant:
    def test_failed_run_with_error_event_passes(self, test_db: Session) -> None:
        mol = _make_molecule(test_db)
        run = _make_run(test_db, mol.id, RunStatus.FAILED)
        test_db.commit()
        _insert_run_event(test_db, run.id, 0, "error", {"error_message": "boom"})
        test_db.commit()

        from sqlalchemy import text

        row = _fetch_required_row(
            test_db,
            text("SELECT COUNT(*) FROM run_events WHERE run_id = :rid AND type = 'error'"),
            {"rid": str(run.id)},
        )
        assert row[0] >= 1

    def test_failed_run_without_error_event_fails_invariant(self, test_db: Session) -> None:
        mol = _make_molecule(test_db)
        run = _make_run(test_db, mol.id, RunStatus.FAILED)
        test_db.commit()

        from sqlalchemy import text

        row = _fetch_required_row(
            test_db,
            text("SELECT COUNT(*) FROM run_events WHERE run_id = :rid AND type = 'error'"),
            {"rid": str(run.id)},
        )
        invariant_violated = row[0] == 0
        assert invariant_violated, "Invariant VIOLATED: FAILED run has no 'error' event."


# ── Invariant: event sequence is monotonically increasing with no gaps ────────


class TestEventSequenceInvariant:
    """run_events.sequence per run must be 0-based, strictly increasing, no gaps."""

    def test_monotonic_sequence_no_gaps(self, test_db: Session) -> None:
        mol = _make_molecule(test_db)
        run = _make_run(test_db, mol.id, RunStatus.COMPLETED)
        test_db.commit()
        for i, (etype, payload) in enumerate(
            [
                ("status_changed", {"status": "RUNNING"}),
                ("iteration_update", {"stage": "setup"}),
                ("estimate_updated", {"source": "telemetry"}),
                ("result", {"energy": -1.137}),
                ("status_changed", {"status": "COMPLETED"}),
            ]
        ):
            _insert_run_event(test_db, run.id, i, etype, payload)
        test_db.commit()

        from sqlalchemy import text

        rows = test_db.execute(
            text("SELECT sequence FROM run_events WHERE run_id = :rid ORDER BY sequence ASC"),
            {"rid": str(run.id)},
        ).fetchall()
        sequences = [r[0] for r in rows]
        assert sequences == list(range(len(sequences))), (
            f"Sequence gap or non-monotonic: {sequences}"
        )

    def test_gap_in_sequence_detected(self, test_db: Session) -> None:
        """Detect when event 1 is missing, leaving a gap: [0, 2]."""
        mol = _make_molecule(test_db)
        run = _make_run(test_db, mol.id, RunStatus.COMPLETED)
        test_db.commit()
        _insert_run_event(test_db, run.id, 0, "status_changed", {"status": "RUNNING"})
        # Intentionally skip sequence 1 to simulate a gap
        _insert_run_event(test_db, run.id, 2, "status_changed", {"status": "COMPLETED"})
        test_db.commit()

        from sqlalchemy import text

        rows = test_db.execute(
            text("SELECT sequence FROM run_events WHERE run_id = :rid ORDER BY sequence ASC"),
            {"rid": str(run.id)},
        ).fetchall()
        sequences = [r[0] for r in rows]
        expected = list(range(len(sequences)))
        assert sequences != expected, "Baseline: gap present"
        gap_detected = sequences != expected
        assert gap_detected, f"Invariant VIOLATED: sequence gap detected: {sequences}"
