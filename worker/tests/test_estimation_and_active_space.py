"""Unit tests for smart estimation, active space auto-reduction, and SSE commit behaviour."""

from __future__ import annotations

import importlib
import time
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from qiskit.quantum_info import SparsePauliOp

from worker.chemistry.hamiltonian_builder import _select_frontier_active_space
from worker.chemistry.types import HamiltonianBundle
from worker.jobs.execute_run import (
    _build_telemetry_estimate,
    _compute_elapsed_seconds,
    _estimate_total_iterations,
)

# ── Elapsed time helper ───────────────────────────────────────────────────────


class TestComputeElapsedSeconds:
    def test_returns_none_when_no_start_time(self) -> None:
        state: dict = {"count": 0, "start_time": None}
        assert _compute_elapsed_seconds(state) is None

    def test_returns_positive_elapsed(self) -> None:
        state: dict = {"count": 0, "start_time": time.monotonic() - 1.0}
        elapsed = _compute_elapsed_seconds(state)
        assert elapsed is not None
        assert elapsed >= 1.0

    def test_missing_key_returns_none(self) -> None:
        assert _compute_elapsed_seconds({}) is None


# ── Smart estimate builder ────────────────────────────────────────────────────


class TestBuildTelemetryEstimate:
    def _bundle(self, num_qubits: int = 4) -> HamiltonianBundle:
        return cast(HamiltonianBundle, SimpleNamespace(num_qubits=num_qubits))

    def test_initial_estimate_without_seed_omits_eta(self) -> None:
        state: dict = {"count": 0, "start_time": None, "ema_cost": None}
        est = _build_telemetry_estimate(
            algorithm="vqe",
            total_iterations=100,
            completed_iterations=0,
            hamiltonian_bundle=self._bundle(4),
            backend_target="statevector",
            elapsed_seconds=None,
            ema_state=state,
        )
        assert est["estimated_total_seconds"] is None
        assert est["estimated_remaining_seconds"] is None
        assert est["confidence"] is None

    def test_initial_estimate_uses_seeded_history_cost_when_available(self) -> None:
        est = _build_telemetry_estimate(
            algorithm="vqe",
            total_iterations=20,
            completed_iterations=0,
            hamiltonian_bundle=self._bundle(4),
            backend_target="statevector",
            elapsed_seconds=None,
            ema_state={"count": 0, "start_time": None, "ema_cost": None},
            seed_seconds_per_iteration=18.0,
            seed_confidence=0.78,
        )

        assert est["estimated_seconds_per_iteration"] == pytest.approx(18.0)
        assert est["estimated_total_seconds"] == pytest.approx(360.0)
        assert est["confidence"] == pytest.approx(0.78)

    def test_ema_updates_after_first_call(self) -> None:
        state: dict = {"count": 1, "start_time": None, "ema_cost": None}
        est = _build_telemetry_estimate(
            algorithm="vqe",
            total_iterations=100,
            completed_iterations=5,
            hamiltonian_bundle=self._bundle(4),
            backend_target="statevector",
            elapsed_seconds=5.0,
            ema_state=state,
        )
        assert state["ema_cost"] is not None
        assert state["ema_cost"] > 0.0
        assert est["confidence"] > 0.35

    def test_early_ema_samples_produce_live_eta_without_seed(self) -> None:
        state: dict = {"count": 1, "start_time": None, "ema_cost": None}
        est = _build_telemetry_estimate(
            algorithm="vqe",
            total_iterations=100,
            completed_iterations=1,
            hamiltonian_bundle=self._bundle(4),
            backend_target="statevector",
            elapsed_seconds=0.02,
            ema_state=state,
        )

        assert est["estimated_seconds_per_iteration"] == pytest.approx(state["ema_cost"])
        assert est["estimated_seconds_per_iteration"] == pytest.approx(0.02)
        assert est["estimated_remaining_seconds"] is not None
        assert est["estimated_remaining_seconds"] > 0.0
        assert est["confidence"] is not None
        assert est["confidence"] < 0.65

    def test_confidence_increases_with_more_iterations(self) -> None:
        state3: dict = {"count": 0, "start_time": None, "ema_cost": None}
        state5: dict = {"count": 0, "start_time": None, "ema_cost": None}
        est3 = _build_telemetry_estimate(
            algorithm="vqe",
            total_iterations=100,
            completed_iterations=3,
            hamiltonian_bundle=self._bundle(4),
            backend_target="statevector",
            elapsed_seconds=3.0,
            ema_state=state3,
        )
        est5 = _build_telemetry_estimate(
            algorithm="vqe",
            total_iterations=100,
            completed_iterations=5,
            hamiltonian_bundle=self._bundle(4),
            backend_target="statevector",
            elapsed_seconds=5.0,
            ema_state=state5,
        )
        assert est5["confidence"] >= est3["confidence"]

    def test_remaining_decreases_as_iterations_complete(self) -> None:
        state: dict = {"count": 0, "start_time": None, "ema_cost": None}
        est = _build_telemetry_estimate(
            algorithm="vqe",
            total_iterations=100,
            completed_iterations=50,
            hamiltonian_bundle=self._bundle(4),
            backend_target="statevector",
            elapsed_seconds=None,
            ema_state=state,
        )
        assert est["estimated_remaining_iterations"] == 50
        assert est["estimated_total_iterations"] == 100

    def test_no_bundle_defaults_to_small_qubit_count(self) -> None:
        _state: dict = {"count": 0, "start_time": None, "ema_cost": None}
        est = _build_telemetry_estimate(
            algorithm="vqe",
            total_iterations=10,
            completed_iterations=0,
            hamiltonian_bundle=None,
            backend_target="statevector",
            elapsed_seconds=None,
            ema_state=None,
        )
        assert est["estimated_total_seconds"] is None

    def test_ema_smoothing_blends_previous(self) -> None:
        state: dict = {
            "count": 0,
            "start_time": None,
            "ema_cost": 1.0,
            "last_eta_elapsed_seconds": 4.0,
            "last_eta_completed_iterations": 4,
        }
        _build_telemetry_estimate(
            algorithm="vqe",
            total_iterations=10,
            completed_iterations=5,
            hamiltonian_bundle=self._bundle(4),
            backend_target="statevector",
            elapsed_seconds=6.0,
            ema_state=state,
        )
        assert 1.0 < state["ema_cost"] < 2.0

    def test_eta_blends_seeded_history_with_live_runtime_during_warmup(self) -> None:
        state: dict = {"count": 0, "start_time": None, "ema_cost": None}
        est = _build_telemetry_estimate(
            algorithm="vqe",
            total_iterations=10,
            completed_iterations=5,
            hamiltonian_bundle=self._bundle(4),
            backend_target="statevector",
            elapsed_seconds=20.0,
            ema_state=state,
            seed_seconds_per_iteration=1.0,
            seed_confidence=0.78,
        )

        assert 1.0 < est["estimated_seconds_per_iteration"] < 4.0
        assert est["estimated_remaining_seconds"] > 10.0
        assert est["estimated_total_seconds"] > 30.0

    def test_total_iterations_expand_when_progress_exceeds_initial_estimate(self) -> None:
        est = _build_telemetry_estimate(
            algorithm="qse",
            total_iterations=3,
            completed_iterations=5,
            hamiltonian_bundle=self._bundle(4),
            backend_target="statevector",
            elapsed_seconds=10.0,
            ema_state={},
        )

        assert est["estimated_total_iterations"] == 5
        assert est["estimated_remaining_iterations"] == 0


class TestEstimateTotalIterations:
    def test_vqe_spsa_counts_objective_evaluations(self) -> None:
        estimate = _estimate_total_iterations(
            "vqe",
            {
                "algorithm": "vqe",
                "optimizer_name": "SPSA",
                "max_iterations": 12,
            },
        )

        assert estimate == 40

    def test_vqe_lbfgsb_estimates_function_evaluations_not_optimizer_iterations(self) -> None:
        estimate = _estimate_total_iterations(
            "vqe",
            {
                "algorithm": "vqe",
                "optimizer_name": "L_BFGS_B",
                "max_iterations": 100,
                "initial_point_candidates": 1,
            },
        )

        assert estimate == 500

    def test_vqe_explicit_function_evaluation_cap_drives_total_estimate(self) -> None:
        estimate = _estimate_total_iterations(
            "vqe",
            {
                "algorithm": "vqe",
                "optimizer_name": "L_BFGS_B",
                "max_iterations": 100,
                "max_function_evaluations": 42,
            },
        )

        assert estimate == 42

    def test_qse_vqe_reference_includes_reference_solve(self) -> None:
        estimate = _estimate_total_iterations(
            "qse",
            {
                "algorithm": "qse",
                "reference_method": "vqe",
                "max_subspace_dim": 6,
                "vqe_reference_max_iterations": 80,
            },
        )

        assert estimate == 88

    def test_ideal_aer_projected_estimate_uses_local_progress_axis(self) -> None:
        estimate = _estimate_total_iterations(
            "kqd",
            {"algorithm": "kqd", "krylov_dim": 8},
            backend_target="aer_simulator",
        )

        assert estimate == 8

    def test_noisy_aer_projected_estimate_includes_matrix_pairs_and_solve(self) -> None:
        estimate = _estimate_total_iterations(
            "kqd",
            {"algorithm": "kqd", "krylov_dim": 8},
            backend_target="aer_simulator",
            noise_profile_enabled=True,
        )

        assert estimate == 44

    def test_resolved_ideal_aer_branch_path_includes_matrix_work(self) -> None:
        estimate = _estimate_total_iterations(
            "kqd",
            {"algorithm": "kqd", "krylov_dim": 8},
            backend_target="aer_simulator",
            projected_branch_path=True,
        )

        assert estimate == 44


# ── Active space frontier selection ──────────────────────────────────────────


class TestSelectFrontierActiveSpace:
    def _rhf_occ(self, n_occ: int, n_virt: int) -> np.ndarray:
        """Build an idealised RHF occupancy array."""
        return np.concatenate([np.full(n_occ, 2.0), np.zeros(n_virt)])

    def test_caps_at_max_safe_orbitals(self) -> None:
        occ = self._rhf_occ(10, 40)
        _, n_o = _select_frontier_active_space(occ, total_electrons=20, total_orbitals=50)
        from worker.chemistry.hamiltonian_builder import _MAX_SAFE_ACTIVE_ORBITALS

        assert n_o <= _MAX_SAFE_ACTIVE_ORBITALS

    def test_returns_positive_orbitals(self) -> None:
        occ = self._rhf_occ(5, 20)
        _, n_o = _select_frontier_active_space(occ, total_electrons=10, total_orbitals=25)
        assert n_o >= 1

    def test_electrons_not_exceed_total(self) -> None:
        occ = self._rhf_occ(3, 10)
        n_e, _ = _select_frontier_active_space(occ, total_electrons=6, total_orbitals=13)
        assert n_e <= 6

    def test_electrons_even_for_closed_shell(self) -> None:
        occ = self._rhf_occ(4, 15)
        n_e, _ = _select_frontier_active_space(occ, total_electrons=8, total_orbitals=19)
        assert n_e % 2 == 0

    def test_electrons_bounded_by_two_times_orbitals(self) -> None:
        occ = self._rhf_occ(7, 30)
        n_e, n_o = _select_frontier_active_space(occ, total_electrons=14, total_orbitals=37)
        assert n_e <= 2 * n_o

    def test_frontier_partial_occupancy(self) -> None:
        occ = np.array([2.0, 2.0, 1.5, 0.5, 0.0, 0.0])
        n_e, n_o = _select_frontier_active_space(occ, total_electrons=4, total_orbitals=6)
        assert n_o >= 1
        assert n_e >= 2


# ── SSE commit called per event batch ────────────────────────────────────────


class TestSSECommitCalledPerIteration:
    """Verify that db.commit() is called after each progress event batch."""

    def test_commit_called_for_each_iteration(self) -> None:
        from worker.chemistry.types import VQEResult
        from worker.jobs.execute_run import execute_run

        commit_calls: list[int] = []
        sessions_created: list[MagicMock] = []

        def make_session():
            s = MagicMock()
            _commit_calls_for_session: list[int] = []

            def execute_side_effect(query, params=None):
                sql = str(query)
                r = MagicMock()
                if "COALESCE" in sql:
                    r.fetchone.return_value = (len(sessions_created),)
                elif "SELECT m.atoms" in sql:
                    r.fetchone.return_value = (
                        [{"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.0}],
                        0,
                        1,
                        {"n_electrons": 2, "n_orbitals": 2},
                        "sto-3g",
                    )
                elif "SELECT config_json, metadata" in sql:
                    r.fetchone.return_value = ({}, {})
                elif "SELECT status" in sql:
                    r.fetchone.return_value = ("RUNNING",)
                else:
                    r.fetchone.return_value = (1,)
                return r

            s.execute.side_effect = execute_side_effect

            def _track_commit():
                commit_calls.append(1)

            s.commit.side_effect = _track_commit
            sessions_created.append(s)
            return s

        ctx = MagicMock()
        ctx.__enter__ = lambda self: make_session()
        ctx.__exit__ = MagicMock(return_value=False)

        execute_run_module = importlib.import_module("worker.jobs.execute_run")
        dummy_bundle = SimpleNamespace(
            num_qubits=4,
            num_spatial_orbitals=2,
            num_electrons_alpha=1,
            num_electrons_beta=1,
            metadata={"active_space": [2, 2], "pipeline": "test"},
            pauli_hamiltonian=SparsePauliOp.from_list([("ZZ", 1.0)]),
        )

        n_iterations = 3
        call_count = 0

        def mock_dispatch(**kwargs):
            cb = kwargs.get("progress_callback")
            nonlocal call_count
            for i in range(1, n_iterations + 1):
                call_count += 1
                if cb:
                    cb(
                        {
                            "algorithm": "vqe",
                            "iteration": i,
                            "completed_iterations": i,
                            "energy": -1.0 + i * 0.01,
                        }
                    )
            return VQEResult(
                algorithm="vqe",
                primary_energy=-1.0,
                primary_iterations=n_iterations,
                converged=True,
                optimal_parameters=[],
                convergence_trace=[-1.0],
            )

        with (
            patch("worker.jobs.execute_run.get_db_session", return_value=ctx),
            patch.object(
                execute_run_module, "_build_hamiltonian_bundle", return_value=dummy_bundle
            ),
            patch("worker.jobs.execute_run.dispatch_algorithm", side_effect=mock_dispatch),
        ):
            execute_run("00000000-0000-0000-0000-000000000099")

        assert len(commit_calls) >= n_iterations, (
            f"Expected at least {n_iterations} commit calls, got {len(commit_calls)}"
        )
