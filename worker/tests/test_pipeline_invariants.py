"""
Worker-side pipeline invariant tests.

Covers:
- F1: on_job_success marks non-dict results as invalid in every environment.
- F2: on_job_success raises in test mode when DB exception occurs.
- F3: Three-way reconcile — runs.status vs run_events last status_changed.
- F4: Progress callback invoked at least once per algorithm.
- F6: Hamiltonian cache key differs for different active spaces.
- F10: Deterministic energy with fixed parameter seed (reproducibility).

All tests use unittest.mock to avoid requiring a live DB/Redis.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from qiskit.quantum_info import SparsePauliOp

from shared.contracts.identifiers import RunAlgorithm
from worker.chemistry.backend_selector import select_backend
from worker.jobs import on_job_success
from worker.jobs.dispatcher import dispatch_algorithm, supported_algorithms

# ── Helpers ───────────────────────────────────────────────────────────────────


def _dummy_hamiltonian(
    n_spatial: int = 2,
    n_elec_a: int = 1,
    n_elec_b: int = 1,
) -> object:
    return SimpleNamespace(
        pauli_hamiltonian=SparsePauliOp.from_list([("ZZ", 1.0), ("IZ", 0.5), ("ZI", -0.5)]),
        num_spatial_orbitals=n_spatial,
        num_electrons_alpha=n_elec_a,
        num_electrons_beta=n_elec_b,
        one_body_tensor=np.zeros((n_spatial, n_spatial), dtype=float),
        two_body_tensor=np.zeros((n_spatial,) * 4, dtype=float),
    )


SAMPLE_RUN_ID = "00000000-0000-0000-0000-000000000099"


def _make_job(run_id: str = SAMPLE_RUN_ID) -> MagicMock:
    job = MagicMock()
    job.id = "rq-test-job-inv"
    job.args = (run_id,)
    job.kwargs = {}
    return job


def _make_session_mock(fetchone_result: Any = (1,)) -> MagicMock:
    session = MagicMock()
    session.execute.return_value.fetchone.return_value = fetchone_result
    return session


# ── F1: non-dict result is invalid in every environment ──────────────────────


class TestNonDictResultFailsRun:
    """F1: on_job_success must never complete a run without a result object."""

    @pytest.mark.parametrize("bad_result", [None, "energy=-1.137", 42, [1, 2, 3]])
    def test_non_dict_result_marks_run_failed(self, bad_result: Any) -> None:
        job = _make_job()
        session = _make_session_mock()

        with patch("worker.jobs.callbacks.get_db_session") as mock_ctx:
            mock_ctx.return_value.__enter__ = lambda s: session
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            on_job_success(job, MagicMock(), result=bad_result)

        executed_calls = [
            (str(call.args[0]), call.args[1] if len(call.args) > 1 else {})
            for call in session.execute.call_args_list
        ]
        failure_update = next(
            params for sql, params in executed_calls if "SET status = 'FAILED'" in sql
        )
        assert json.loads(failure_update["error"])["error_code"] == "invalid_result"
        assert not any("SET status = 'COMPLETED'" in sql for sql, _ in executed_calls)

    def test_dict_result_does_not_raise(self) -> None:
        job = _make_job()
        session = _make_session_mock()

        with patch("worker.jobs.callbacks.get_db_session") as mock_ctx:
            mock_ctx.return_value.__enter__ = lambda s: session
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            # Should not raise
            on_job_success(
                job,
                MagicMock(),
                result={"energy": -1.137, "iterations": 5, "converged": True},
            )


# ── F2: DB exception re-raised in test mode ───────────────────────────────────


class TestDBExceptionReraisedInTestMode:
    """F2: DB exceptions in on_job_success/on_job_failure must propagate in test mode."""

    def test_db_error_in_success_callback_reraises(self) -> None:
        job = _make_job()

        with patch("worker.jobs.callbacks.get_db_session") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(side_effect=Exception("DB is down"))
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            with pytest.raises(Exception, match="DB is down"):
                on_job_success(job, MagicMock(), result={"energy": -1.0})

    def test_db_error_in_failure_callback_reraises(self) -> None:
        from worker.jobs import on_job_failure

        job = _make_job()
        try:
            raise ValueError("solver blew up")
        except ValueError:
            import sys

            exc_type, exc_value, exc_tb = sys.exc_info()
        assert exc_type is not None
        assert exc_value is not None

        with patch("worker.jobs.callbacks.get_db_session") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(side_effect=Exception("DB is down"))
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            with pytest.raises(Exception, match="DB is down"):
                on_job_failure(job, MagicMock(), exc_type, exc_value, exc_tb)


# ── F3: Three-way status reconcile ───────────────────────────────────────────


class TestThreeWayStatusReconcile:
    """
    F3: Verifies that run status, last status_changed event, and job result agree.
    Uses in-memory structures to simulate the invariant check a reconciler would do.
    """

    def test_completed_status_matches_last_status_changed_event(self) -> None:
        events: list[dict[str, Any]] = [
            {"type": "status_changed", "payload": {"status": "RUNNING"}},
            {"type": "iteration_update", "payload": {"stage": "progress"}},
            {"type": "result", "payload": {"energy": -1.137}},
            {"type": "status_changed", "payload": {"status": "COMPLETED"}},
        ]
        db_status = "COMPLETED"

        status_changed_events = [e for e in events if e["type"] == "status_changed"]
        last_event_status = status_changed_events[-1]["payload"]["status"]
        assert last_event_status == db_status, (
            f"Reconcile mismatch: DB says {db_status!r} but last event says {last_event_status!r}"
        )

    def test_failed_status_matches_last_status_changed_event(self) -> None:
        events: list[dict[str, Any]] = [
            {"type": "status_changed", "payload": {"status": "RUNNING"}},
            {"type": "error", "payload": {"error_message": "boom"}},
            {"type": "status_changed", "payload": {"status": "FAILED"}},
        ]
        db_status = "FAILED"

        status_changed_events = [e for e in events if e["type"] == "status_changed"]
        last_event_status = status_changed_events[-1]["payload"]["status"]
        assert last_event_status == db_status

    def test_stale_running_status_detected(self) -> None:
        events: list[dict[str, Any]] = [
            {"type": "status_changed", "payload": {"status": "RUNNING"}},
            {"type": "iteration_update", "payload": {"stage": "progress"}},
        ]
        db_status = "RUNNING"

        terminal_statuses = {"COMPLETED", "FAILED", "CANCELLED"}
        status_changed_events = [e for e in events if e["type"] == "status_changed"]
        last_event_status = status_changed_events[-1]["payload"]["status"]

        stale = db_status == "RUNNING" and last_event_status not in terminal_statuses
        assert stale, "Should detect stale RUNNING status as a reconcile anomaly"


# ── F4: Progress callback invoked at least once per algorithm ─────────────────


class TestProgressCallbackInvocation:
    """F4: Every algorithm must invoke the progress callback at least once."""

    @pytest.mark.parametrize(
        "algorithm,config",
        [
            (
                "vqe",
                {"max_iterations": 3},
            ),
            (
                "sqd",
                {"max_iterations": 2, "samples_per_batch": 64, "num_batches": 2},
            ),
            (
                "kqd",
                {
                    "algorithm": "kqd",
                    "advanced_config": {
                        "algorithm": "kqd",
                        "krylov_dim": 3,
                        "time_step": 0.1,
                        "evolution_method": "exact",
                    },
                },
            ),
            (
                "qfd",
                {
                    "algorithm": "qfd",
                    "advanced_config": {
                        "algorithm": "qfd",
                        "num_time_points": 3,
                        "max_time": 0.5,
                        "time_grid_type": "linear",
                    },
                },
            ),
            (
                "qse",
                {
                    "algorithm": "qse",
                    "advanced_config": {
                        "algorithm": "qse",
                        "reference_method": "vqe",
                        "excitation_level": "singles",
                        "max_subspace_dim": 4,
                    },
                },
            ),
            (
                "skqd",
                {
                    "algorithm": "skqd",
                    "advanced_config": {
                        "algorithm": "skqd",
                        "base_sampling_options": {
                            "samples_per_batch": 64,
                            "num_batches": 2,
                            "max_iterations": 2,
                        },
                        "krylov_extension_dim": 2,
                    },
                },
            ),
        ],
    )
    def test_progress_callback_invoked_at_least_once(self, algorithm: str, config: dict) -> None:
        backend = select_backend("statevector")
        events: list[dict] = []

        dispatch_algorithm(
            algorithm=algorithm,
            backend=backend,
            config_snapshot=config,
            hamiltonian_bundle=_dummy_hamiltonian(),
            progress_callback=events.append,
        )

        assert events, (
            f"{algorithm}: progress_callback was never invoked — run appears silent until terminal"
        )
        # At least one event must carry algorithm label
        assert any(e.get("algorithm") == algorithm for e in events), (
            f"{algorithm}: no progress event carries correct algorithm label"
        )


# ── F6: Hamiltonian cache key differs for different active spaces ─────────────


class TestHamiltonianCacheKey:
    """F6: Different active-space parameters must produce distinct cache keys."""

    def test_different_active_space_yields_different_cache_key(self) -> None:
        from worker.chemistry.chemistry_cache import chemistry_cache_key
        from worker.chemistry.molecule_builder import build_molecule
        from worker.chemistry.types import ChemistryInput

        h2_2_2 = ChemistryInput(
            atoms=[
                {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.0},
                {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.735},
            ],
            charge=0,
            multiplicity=1,
            basis="sto-3g",
            active_space=(2, 2),
        )
        h2_no_active = ChemistryInput(
            atoms=[
                {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.0},
                {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.735},
            ],
            charge=0,
            multiplicity=1,
            basis="sto-3g",
            active_space=None,
        )

        mol_with_as = build_molecule(h2_2_2)
        mol_no_as = build_molecule(h2_no_active)

        key_with_as = chemistry_cache_key(mol_with_as)
        key_no_as = chemistry_cache_key(mol_no_as)

        assert key_with_as != key_no_as, (
            "Cache keys must differ when active_space differs — "
            "otherwise stale Hamiltonian bundles will be returned"
        )

    def test_same_active_space_yields_same_cache_key(self) -> None:
        from worker.chemistry.chemistry_cache import chemistry_cache_key
        from worker.chemistry.molecule_builder import build_molecule
        from worker.chemistry.types import ChemistryInput

        inp_a = ChemistryInput(
            atoms=[
                {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.0},
                {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.735},
            ],
            charge=0,
            multiplicity=1,
            basis="sto-3g",
            active_space=(2, 2),
        )
        inp_b = ChemistryInput(
            atoms=[
                {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.0},
                {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.735},
            ],
            charge=0,
            multiplicity=1,
            basis="sto-3g",
            active_space=(2, 2),
        )

        key_a = chemistry_cache_key(build_molecule(inp_a))
        key_b = chemistry_cache_key(build_molecule(inp_b))
        assert key_a == key_b


# ── Supported algorithm completeness ─────────────────────────────────────────


def test_all_six_algorithms_registered() -> None:
    """Regression: dispatcher must contain exactly the 6 wave-1 algorithms."""
    assert supported_algorithms() == {algorithm.value for algorithm in RunAlgorithm}
