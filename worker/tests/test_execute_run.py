"""Tests for execute_run."""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from qiskit.quantum_info import SparsePauliOp

from worker.adapters.base import AdapterCapabilities, BackendExecutionContext
from worker.chemistry.types import VQEResult
from worker.jobs.execute_run import (
    execute_run,
)

from .execute_run_test_helpers import (
    DISPATCH_ALGORITHM_PATCH_TARGET,
    GET_DB_SESSION_PATCH_TARGET,
    INJECT_PROFILE_CREDENTIALS_PATCH_TARGET,
    MOLECULE_ROW,
    SAMPLE_RUN_ID,
    SELECT_BACKEND_PATCH_TARGET,
    SELECT_CONFIG_AND_METADATA_SQL,
    SELECT_MOLECULE_SQL,
    SELECT_RUN_CONTEXT_WITH_PROFILE_SQL,
    SELECT_STATUS_SQL,
    _all_event_payloads,
    _all_event_types,
    _make_session,
    _make_session_with_run_context,
)


# Patch time.sleep globally for all tests to avoid actual waits
@pytest.fixture(autouse=True)
def no_sleep(monkeypatch) -> None:
    monkeypatch.setattr("time.sleep", lambda _: None)


@pytest.fixture(autouse=True)
def stub_hamiltonian_build(monkeypatch) -> None:
    """Keep execute_run tests lightweight by stubbing chemistry-heavy build path."""
    execute_run_module = importlib.import_module("worker.jobs.execute_run")
    dummy_bundle = SimpleNamespace(
        num_qubits=4,
        num_spatial_orbitals=2,
        num_electrons_alpha=1,
        num_electrons_beta=1,
        constant=0.0,
        one_body_tensor=np.zeros((2, 2), dtype=float),
        two_body_tensor=np.zeros((2, 2, 2, 2), dtype=float),
        metadata={"active_space": [2, 2], "pipeline": "test"},
        pauli_hamiltonian=SparsePauliOp.from_list([("ZZZZ", 1.0)]),
    )
    monkeypatch.setattr(execute_run_module, "_build_hamiltonian_bundle", lambda **_: dummy_bundle)


class TestExecuteRunHappyPath:
    def _run_with_mock_sessions(self, run_id: str = SAMPLE_RUN_ID):
        """Run execute_run with all DB sessions mocked."""
        sessions = []

        def make_session():
            s = _make_session(status="RUNNING")
            sessions.append(s)
            return s

        ctx = MagicMock()
        ctx.__enter__ = lambda self: make_session()
        ctx.__exit__ = MagicMock(return_value=False)

        with patch(GET_DB_SESSION_PATCH_TARGET, return_value=ctx):
            result = execute_run(run_id)

        return result, sessions

    def test_returns_result_dict_with_expected_keys(self) -> None:
        result, _ = self._run_with_mock_sessions()
        assert "energy" in result
        assert "iterations" in result
        assert "optimal_parameters" in result
        assert "converged" in result

    def test_returns_positive_iterations(self) -> None:
        result, _ = self._run_with_mock_sessions()
        assert result["iterations"] >= 1

    def test_returns_converged_flag(self) -> None:
        result, _ = self._run_with_mock_sessions()
        assert isinstance(result["converged"], bool)

    def test_returns_numeric_final_energy(self) -> None:
        result, _ = self._run_with_mock_sessions()
        assert isinstance(result["energy"], float)
        assert np.isfinite(result["energy"])

    def test_emits_status_changed_running_at_start(self) -> None:
        _, sessions = self._run_with_mock_sessions()
        all_types = _all_event_types(sessions)
        # status_changed(RUNNING) must be the very first event
        assert all_types[0] == "status_changed"
        first_payloads = _all_event_payloads(sessions)
        assert first_payloads[0].get("status") == "RUNNING"

    def test_closes_completed_execution_segment(self) -> None:
        _, sessions = self._run_with_mock_sessions()

        segment_finishes = [
            call
            for session in sessions
            for call in session.execute.call_args_list
            if "UPDATE run_execution_segments SET status = :status" in str(call.args[0])
        ]
        assert len(segment_finishes) == 1
        assert segment_finishes[0].args[1]["status"] == "completed"
        assert segment_finishes[0].args[1]["duration_seconds"] >= 0.0

    def test_emits_iteration_update_events_for_setup_and_progress(self) -> None:
        result, sessions = self._run_with_mock_sessions()
        types = _all_event_types(sessions)
        # backend_selected, hamiltonian_building, final setup, then progress events
        assert types.count("iteration_update") == result["iterations"] + 3

    def test_emits_estimate_updated_events_with_remaining_work(self) -> None:
        result, sessions = self._run_with_mock_sessions()
        types = _all_event_types(sessions)
        assert types.count("estimate_updated") == result["iterations"] + 1

        estimate_payloads = [
            payload
            for payload in _all_event_payloads(sessions)
            if "estimated_remaining_iterations" in payload
        ]
        assert estimate_payloads
        assert estimate_payloads[0]["source"] == "telemetry"
        assert estimate_payloads[-1]["estimated_remaining_iterations"] >= 0
        assert (
            estimate_payloads[-1]["estimated_remaining_iterations"]
            <= estimate_payloads[0]["estimated_remaining_iterations"]
        )

    def test_emits_setup_event_before_progress(self) -> None:
        _, sessions = self._run_with_mock_sessions()
        payloads = _all_event_payloads(sessions)
        setup_events = [p for p in payloads if p.get("stage") == "setup"]
        assert setup_events, "Expected a setup event"
        assert setup_events[0]["algorithm"] == "vqe"
        assert setup_events[0]["backend_target"] == "statevector"
        assert [event.get("step") for event in setup_events[:2]] == [
            "backend_selected",
            "hamiltonian_building",
        ]

    def test_iteration_events_match_reported_iteration_count(self) -> None:
        result, sessions = self._run_with_mock_sessions()
        payloads = _all_event_payloads(sessions)
        iter_payloads = [p for p in payloads if "iteration" in p]
        assert len(iter_payloads) == result["iterations"]
        for i, p in enumerate(iter_payloads, start=1):
            assert p["iteration"] == i
            if "energy" in p:
                assert isinstance(p["energy"], float)

    def test_sqd_run_returns_sqd_metrics_and_setup_event(self) -> None:
        sessions = []

        def make_session():
            session = _make_session_with_run_context(
                config_snapshot={
                    "algorithm": "sqd",
                    "advanced_config": {
                        "algorithm": "sqd",
                        "max_iterations": 3,
                        "samples_per_batch": 128,
                        "num_batches": 8,
                    },
                },
                metadata={"algorithm": "sqd", "mode": "advanced", "backend_target": "statevector"},
            )
            sessions.append(session)
            return session

        ctx = MagicMock()
        ctx.__enter__ = lambda self: make_session()
        ctx.__exit__ = MagicMock(return_value=False)

        with patch(GET_DB_SESSION_PATCH_TARGET, return_value=ctx):
            result = execute_run(SAMPLE_RUN_ID)

        assert result["algorithm"] == "sqd"
        assert result["iterations"] >= 1
        assert "algorithm_metrics" in result
        assert "postselection_summary" in result["algorithm_metrics"]
        assert "subsampling_summary" in result["algorithm_metrics"]

        payloads = _all_event_payloads(sessions)
        setup_events = [p for p in payloads if p.get("stage") == "setup"]
        assert setup_events
        assert setup_events[0]["algorithm"] == "sqd"

    def test_kqd_run_returns_kqd_metrics_and_setup_event(self) -> None:
        sessions = []

        def make_session():
            session = _make_session_with_run_context(
                config_snapshot={
                    "algorithm": "kqd",
                    "advanced_config": {
                        "algorithm": "kqd",
                        "krylov_dim": 4,
                        "time_step": 0.1,
                        "evolution_method": "exact",
                    },
                },
                metadata={"algorithm": "kqd", "mode": "advanced", "backend_target": "statevector"},
            )
            sessions.append(session)
            return session

        ctx = MagicMock()
        ctx.__enter__ = lambda self: make_session()
        ctx.__exit__ = MagicMock(return_value=False)

        with patch(GET_DB_SESSION_PATCH_TARGET, return_value=ctx):
            result = execute_run(SAMPLE_RUN_ID)

        assert result["algorithm"] == "kqd"
        assert result["iterations"] >= 1
        assert "ritz_values" in result["algorithm_metrics"]
        assert result["backend_execution"]["execution_mode"] == "exact_matrix_evolution"
        assert result["backend_execution"]["backend_primitives_used"] is False

        payloads = _all_event_payloads(sessions)
        setup_events = [p for p in payloads if p.get("stage") == "setup"]
        assert setup_events
        assert setup_events[0]["algorithm"] == "kqd"
        assert setup_events[0]["execution_mode"] == "kqd_path_pending"
        assert setup_events[0]["backend_primitives_used"] is False

        kqd_progress_events = [
            p
            for p in payloads
            if p.get("algorithm") == "kqd" and p.get("stage") in {"progress", "completed"}
        ]
        assert kqd_progress_events
        assert any(
            p.get("stage") == "completed" and p.get("step") == "solve" for p in kqd_progress_events
        )
        assert any("iteration" in p for p in kqd_progress_events)

    def test_qfd_run_returns_qfd_metrics_and_setup_event(self) -> None:
        sessions = []

        def make_session():
            session = _make_session_with_run_context(
                config_snapshot={
                    "algorithm": "qfd",
                    "advanced_config": {
                        "algorithm": "qfd",
                        "num_time_points": 5,
                        "max_time": 0.8,
                        "time_grid_type": "linear",
                    },
                },
                metadata={"algorithm": "qfd", "mode": "advanced", "backend_target": "statevector"},
            )
            sessions.append(session)
            return session

        ctx = MagicMock()
        ctx.__enter__ = lambda self: make_session()
        ctx.__exit__ = MagicMock(return_value=False)

        with patch(GET_DB_SESSION_PATCH_TARGET, return_value=ctx):
            result = execute_run(SAMPLE_RUN_ID)

        assert result["algorithm"] == "qfd"
        assert result["iterations"] == result["algorithm_metrics"]["conditioning_summary"][
            "time_points"
        ]
        assert result["algorithm_metrics"]["conditioning_summary"][
            "requested_time_points"
        ] == pytest.approx(5.0)
        assert "filter_eigenvalues" in result["algorithm_metrics"]
        assert result["backend_execution"]["execution_mode"] == "dense_classical"
        assert result["backend_execution"]["backend_primitives_used"] is False

        payloads = _all_event_payloads(sessions)
        setup_events = [p for p in payloads if p.get("stage") == "setup"]
        assert setup_events
        assert setup_events[0]["algorithm"] == "qfd"
        assert setup_events[0]["execution_mode"] == "qfd_path_pending"
        assert setup_events[0]["backend_primitives_used"] is False

    def test_qse_run_returns_qse_metrics_and_setup_event(self) -> None:
        sessions = []

        def make_session():
            session = _make_session_with_run_context(
                config_snapshot={
                    "algorithm": "qse",
                    "advanced_config": {
                        "algorithm": "qse",
                        "reference_method": "vqe",
                        "excitation_level": "singles",
                        "max_subspace_dim": 4,
                    },
                },
                metadata={"algorithm": "qse", "mode": "advanced", "backend_target": "statevector"},
            )
            sessions.append(session)
            return session

        ctx = MagicMock()
        ctx.__enter__ = lambda self: make_session()
        ctx.__exit__ = MagicMock(return_value=False)

        with patch(GET_DB_SESSION_PATCH_TARGET, return_value=ctx):
            result = execute_run(SAMPLE_RUN_ID)

        assert result["algorithm"] == "qse"
        assert result["iterations"] >= 1
        assert "eigenvalues" in result["algorithm_metrics"]

        payloads = _all_event_payloads(sessions)
        progress_iterations = [
            int(p["iteration"])
            for p in payloads
            if p.get("algorithm") == "qse" and p.get("stage") != "setup" and "iteration" in p
        ]
        assert progress_iterations == sorted(progress_iterations)
        assert result["iterations"] == max(progress_iterations)
        assert any("phase_iteration" in p for p in payloads if p.get("algorithm") == "qse")
        setup_events = [p for p in payloads if p.get("stage") == "setup"]
        assert setup_events
        assert setup_events[0]["algorithm"] == "qse"

    def test_easy_mode_uses_expanded_snapshot_from_metadata(self) -> None:
        sessions = []
        captured_configs: list[dict] = []

        def make_session():
            session = _make_session_with_run_context(
                config_snapshot={
                    "algorithm": "vqe",
                    "mode": "easy",
                    "backend_target": "statevector",
                    "easy_options": {"goal": "balanced"},
                },
                metadata={
                    "algorithm": "vqe",
                    "mode": "easy",
                    "backend_target": "statevector",
                    "easy_mode": {
                        "catalog_version": "2026-04-09-v1",
                        "goal": "balanced",
                        "expanded_advanced_config": {
                            "algorithm": "vqe",
                            "ansatz_name": "EfficientSU2",
                            "optimizer_name": "COBYLA",
                            "max_iterations": 150,
                            "convergence_threshold": 1e-5,
                        },
                    },
                },
            )
            sessions.append(session)
            return session

        ctx = MagicMock()
        ctx.__enter__ = lambda self: make_session()
        ctx.__exit__ = MagicMock(return_value=False)

        def fake_dispatch_algorithm(
            *,
            algorithm,
            backend,
            config_snapshot,
            hamiltonian_bundle,
            progress_callback=None,
            backend_context=None,
        ):
            del algorithm, backend, hamiltonian_bundle, backend_context
            captured_configs.append(config_snapshot)
            if progress_callback is not None:
                progress_callback(
                    {
                        "algorithm": "vqe",
                        "stage": "progress",
                        "iteration": 1,
                        "completed_iterations": 1,
                        "energy": -1.0,
                    }
                )
            return VQEResult(
                algorithm="vqe",
                primary_energy=-1.0,
                primary_iterations=1,
                converged=True,
                optimal_parameters=[],
                convergence_trace=[-1.0],
            )

        with (
            patch(GET_DB_SESSION_PATCH_TARGET, return_value=ctx),
            patch(DISPATCH_ALGORITHM_PATCH_TARGET, side_effect=fake_dispatch_algorithm),
        ):
            result = execute_run(SAMPLE_RUN_ID)

        assert result["algorithm"] == "vqe"
        assert captured_configs == [
            {
                "algorithm": "vqe",
                "ansatz_name": "EfficientSU2",
                "optimizer_name": "COBYLA",
                "max_iterations": 150,
                "convergence_threshold": 1e-5,
            }
        ]

    def test_easy_mode_preserves_ibm_backend_options_for_execution(self) -> None:
        sessions = []
        captured_configs: list[dict[str, Any]] = []
        captured_contexts: list[BackendExecutionContext | None] = []

        def make_session():
            session = _make_session_with_run_context(
                config_snapshot={
                    "algorithm": "vqe",
                    "mode": "easy",
                    "backend_target": "ibm_runtime",
                    "backend_options": {
                        "backend_name": "ibm_brisbane",
                        "selection_policy": "manual",
                        "shots": 2048,
                        "credential_profile_id": "profile-123",
                    },
                    "easy_options": {"goal": "balanced"},
                },
                metadata={
                    "algorithm": "vqe",
                    "mode": "easy",
                    "backend_target": "ibm_runtime",
                    "easy_mode": {
                        "catalog_version": "2026-06-01-v3",
                        "goal": "balanced",
                        "expanded_advanced_config": {
                            "algorithm": "vqe",
                            "ansatz_name": "EfficientSU2",
                            "optimizer_name": "COBYLA",
                            "max_iterations": 150,
                        },
                    },
                },
            )
            sessions.append(session)
            return session

        ctx = MagicMock()
        ctx.__enter__ = lambda self: make_session()
        ctx.__exit__ = MagicMock(return_value=False)
        backend_adapter = MagicMock()
        backend_adapter.capabilities = AdapterCapabilities(
            backend_target="ibm_runtime",
            enabled=True,
            supports_noise_profile=False,
        )
        backend_adapter.execution_metadata.return_value = {
            "backend_target": "ibm_runtime",
            "resolved_backend_name": "ibm_brisbane",
        }

        def fake_dispatch_algorithm(
            *,
            algorithm,
            backend,
            config_snapshot,
            hamiltonian_bundle,
            progress_callback=None,
            backend_context=None,
        ):
            del algorithm, backend, hamiltonian_bundle, progress_callback
            captured_configs.append(config_snapshot)
            captured_contexts.append(backend_context)
            return VQEResult(
                algorithm="vqe",
                primary_energy=-1.0,
                primary_iterations=1,
                converged=True,
                optimal_parameters=[],
                convergence_trace=[-1.0],
            )

        with (
            patch(GET_DB_SESSION_PATCH_TARGET, return_value=ctx),
            patch(SELECT_BACKEND_PATCH_TARGET, return_value=backend_adapter),
            patch(DISPATCH_ALGORITHM_PATCH_TARGET, side_effect=fake_dispatch_algorithm),
            patch(
                INJECT_PROFILE_CREDENTIALS_PATCH_TARGET,
                side_effect=lambda session, options: {
                    **options,
                    "token": "decrypted-token",
                    "instance": "ibm-instance",
                    "channel": "ibm_quantum_platform",
                },
            ) as inject_profile_credentials,
        ):
            result = execute_run(SAMPLE_RUN_ID)

        assert result["backend_target"] == "ibm_runtime"
        assert captured_configs == [
            {
                "algorithm": "vqe",
                "ansatz_name": "EfficientSU2",
                "optimizer_name": "COBYLA",
                "max_iterations": 150,
            }
        ]
        inject_profile_credentials.assert_called_once()
        context = captured_contexts[0]
        assert context is not None
        assert context.backend_target == "ibm_runtime"
        assert context.backend_options["backend_name"] == "ibm_brisbane"
        assert context.backend_options["credential_profile_id"] == "profile-123"
        assert context.backend_options["token"] == "decrypted-token"
        assert context.backend_options["instance"] == "ibm-instance"
        assert context.backend_options["channel"] == "ibm_quantum_platform"

    def test_backend_options_threaded_separately_from_algorithm_config(self) -> None:
        sessions = []
        captured_configs: list[dict[str, Any]] = []
        captured_contexts: list[BackendExecutionContext | None] = []

        def make_session():
            session = _make_session_with_run_context(
                config_snapshot={
                    "algorithm": "vqe",
                    "mode": "advanced",
                    "backend_target": "aer_simulator",
                    "backend_options": {
                        "shots": 1234,
                        "method": "automatic",
                        "optimization_level": 1,
                    },
                    "noise_profile": {
                        "source": "custom_preset",
                        "preset": "readout_bias",
                        "p01": 0.02,
                        "p10": 0.04,
                    },
                    "advanced_config": {
                        "algorithm": "vqe",
                        "ansatz_name": "EfficientSU2",
                        "backend_options": {"shots": 99},
                        "max_iterations": 3,
                    },
                },
                metadata={
                    "algorithm": "vqe",
                    "mode": "advanced",
                    "backend_target": "aer_simulator",
                },
            )
            sessions.append(session)
            return session

        ctx = MagicMock()
        ctx.__enter__ = lambda self: make_session()
        ctx.__exit__ = MagicMock(return_value=False)

        def fake_dispatch_algorithm(
            *,
            algorithm,
            backend,
            config_snapshot,
            hamiltonian_bundle,
            progress_callback=None,
            backend_context=None,
        ):
            del algorithm, backend, hamiltonian_bundle
            captured_configs.append(config_snapshot)
            captured_contexts.append(backend_context)
            if progress_callback is not None:
                progress_callback(
                    {
                        "algorithm": "vqe",
                        "stage": "progress",
                        "iteration": 1,
                        "completed_iterations": 1,
                        "energy": -1.0,
                    }
                )
            return VQEResult(
                algorithm="vqe",
                primary_energy=-1.0,
                primary_iterations=1,
                converged=True,
                optimal_parameters=[],
                convergence_trace=[-1.0],
            )

        with (
            patch(GET_DB_SESSION_PATCH_TARGET, return_value=ctx),
            patch(DISPATCH_ALGORITHM_PATCH_TARGET, side_effect=fake_dispatch_algorithm),
        ):
            result = execute_run(SAMPLE_RUN_ID)

        assert result["backend_target"] == "aer_simulator"
        assert captured_configs == [
            {
                "algorithm": "vqe",
                "ansatz_name": "EfficientSU2",
                "max_iterations": 3,
            }
        ]
        context = captured_contexts[0]
        assert context is not None
        assert context.backend_target == "aer_simulator"
        assert context.shots == 1234
        assert context.noise_profile is not None
        assert context.noise_profile["preset"] == "readout_bias"
        assert result["backend_execution"]["shots"] is None
        assert result["backend_execution"]["requested_shots"] == 1234
        assert result["backend_execution"]["noise_summary"]["enabled"] is True

    def test_backend_derived_aer_runs_inject_saved_profile_credentials(self) -> None:
        sessions = []
        captured_contexts: list[BackendExecutionContext | None] = []

        def make_session():
            session = _make_session_with_run_context(
                config_snapshot={
                    "algorithm": "vqe",
                    "mode": "advanced",
                    "backend_target": "aer_simulator",
                    "backend_options": {
                        "backend_name": "aer_simulator",
                        "shots": 2048,
                        "credential_profile_id": "profile-123",
                    },
                    "noise_profile": {
                        "source": "backend_derived",
                        "reference_backend": "ibm_brisbane",
                    },
                    "advanced_config": {
                        "algorithm": "vqe",
                        "ansatz_name": "EfficientSU2",
                        "max_iterations": 2,
                    },
                },
                metadata={
                    "algorithm": "vqe",
                    "mode": "advanced",
                    "backend_target": "aer_simulator",
                },
            )
            sessions.append(session)
            return session

        ctx = MagicMock()
        ctx.__enter__ = lambda self: make_session()
        ctx.__exit__ = MagicMock(return_value=False)
        backend_adapter = MagicMock()
        backend_adapter.capabilities = AdapterCapabilities(
            backend_target="aer_simulator",
            enabled=True,
            supports_noise_profile=True,
        )
        backend_adapter.execution_metadata.return_value = {
            "backend_target": "aer_simulator",
            "resolved_backend_name": "aer_simulator",
            "noise_summary": {"enabled": True, "source": "backend_derived"},
        }

        def fake_dispatch_algorithm(
            *,
            algorithm,
            backend,
            config_snapshot,
            hamiltonian_bundle,
            progress_callback=None,
            backend_context=None,
        ):
            del algorithm, backend, config_snapshot, hamiltonian_bundle, progress_callback
            captured_contexts.append(backend_context)
            return VQEResult(
                algorithm="vqe",
                primary_energy=-1.0,
                primary_iterations=1,
                converged=True,
                optimal_parameters=[],
                convergence_trace=[-1.0],
            )

        with (
            patch(GET_DB_SESSION_PATCH_TARGET, return_value=ctx),
            patch(SELECT_BACKEND_PATCH_TARGET, return_value=backend_adapter),
            patch(DISPATCH_ALGORITHM_PATCH_TARGET, side_effect=fake_dispatch_algorithm),
            patch(
                INJECT_PROFILE_CREDENTIALS_PATCH_TARGET,
                side_effect=lambda session, options: {
                    **options,
                    "token": "decrypted-token",
                    "instance": "ibm-instance",
                    "channel": "ibm_quantum_platform",
                },
            ) as inject_profile_credentials,
        ):
            execute_run(SAMPLE_RUN_ID)

        inject_profile_credentials.assert_called_once()
        context = captured_contexts[0]
        assert context is not None
        assert context.backend_target == "aer_simulator"
        assert context.noise_profile is not None
        assert context.noise_profile["source"] == "backend_derived"
        assert context.backend_options["credential_profile_id"] == "profile-123"
        assert context.backend_options["token"] == "decrypted-token"
        assert context.backend_options["instance"] == "ibm-instance"
        assert context.backend_options["channel"] == "ibm_quantum_platform"

    def test_ibm_runtime_falls_back_to_persisted_credential_profile_id(self) -> None:
        sessions = []
        captured_contexts: list[BackendExecutionContext | None] = []

        def make_session():
            session = _make_session_with_run_context(
                config_snapshot={
                    "algorithm": "vqe",
                    "mode": "advanced",
                    "backend_target": "ibm_runtime",
                    "backend_options": {
                        "backend_name": "ibm_brisbane",
                        "shots": 2048,
                    },
                    "advanced_config": {
                        "algorithm": "vqe",
                        "ansatz_name": "EfficientSU2",
                        "max_iterations": 2,
                    },
                },
                metadata={
                    "algorithm": "vqe",
                    "mode": "advanced",
                    "backend_target": "ibm_runtime",
                },
                credential_profile_id="profile-123",
            )
            sessions.append(session)
            return session

        ctx = MagicMock()
        ctx.__enter__ = lambda self: make_session()
        ctx.__exit__ = MagicMock(return_value=False)
        backend_adapter = MagicMock()
        backend_adapter.capabilities = AdapterCapabilities(
            backend_target="ibm_runtime",
            enabled=True,
            supports_noise_profile=False,
        )
        backend_adapter.execution_metadata.return_value = {
            "backend_target": "ibm_runtime",
            "resolved_backend_name": "ibm_brisbane",
        }

        def fake_dispatch_algorithm(
            *,
            algorithm,
            backend,
            config_snapshot,
            hamiltonian_bundle,
            progress_callback=None,
            backend_context=None,
        ):
            del algorithm, backend, config_snapshot, hamiltonian_bundle, progress_callback
            captured_contexts.append(backend_context)
            return VQEResult(
                algorithm="vqe",
                primary_energy=-1.0,
                primary_iterations=1,
                converged=True,
                optimal_parameters=[],
                convergence_trace=[-1.0],
            )

        with (
            patch(GET_DB_SESSION_PATCH_TARGET, return_value=ctx),
            patch(SELECT_BACKEND_PATCH_TARGET, return_value=backend_adapter),
            patch(DISPATCH_ALGORITHM_PATCH_TARGET, side_effect=fake_dispatch_algorithm),
            patch(
                INJECT_PROFILE_CREDENTIALS_PATCH_TARGET,
                side_effect=lambda session, options: {
                    **options,
                    "token": "decrypted-token",
                    "instance": "ibm-instance",
                    "channel": "ibm_quantum_platform",
                },
            ) as inject_profile_credentials,
        ):
            execute_run(SAMPLE_RUN_ID)

        inject_profile_credentials.assert_called_once()
        context = captured_contexts[0]
        assert context is not None
        assert context.backend_target == "ibm_runtime"
        assert context.backend_options["credential_profile_id"] == "profile-123"
        assert context.backend_options["token"] == "decrypted-token"
        assert context.backend_options["instance"] == "ibm-instance"
        assert context.backend_options["channel"] == "ibm_quantum_platform"

    def test_skqd_run_returns_skqd_metrics_and_setup_event(self) -> None:
        sessions = []

        def make_session():
            session = _make_session_with_run_context(
                config_snapshot={
                    "algorithm": "skqd",
                    "advanced_config": {
                        "algorithm": "skqd",
                        "base_sampling_options": {
                            "samples_per_batch": 128,
                            "num_batches": 4,
                            "max_iterations": 3,
                            "num_elec_a": 1,
                            "num_elec_b": 1,
                        },
                        "krylov_extension_dim": 3,
                    },
                },
                metadata={"algorithm": "skqd", "mode": "advanced", "backend_target": "statevector"},
            )
            sessions.append(session)
            return session

        ctx = MagicMock()
        ctx.__enter__ = lambda self: make_session()
        ctx.__exit__ = MagicMock(return_value=False)

        with patch(GET_DB_SESSION_PATCH_TARGET, return_value=ctx):
            result = execute_run(SAMPLE_RUN_ID)

        assert result["algorithm"] == "skqd"
        assert result["iterations"] >= 1
        assert "sqd_core" in result["algorithm_metrics"]

        payloads = _all_event_payloads(sessions)
        setup_events = [p for p in payloads if p.get("stage") == "setup"]
        assert setup_events
        assert setup_events[0]["algorithm"] == "skqd"


class TestExecuteRunCancellation:
    def test_returns_early_when_cancelled(self) -> None:
        call_count = 0

        def make_session():
            nonlocal call_count
            status = "CANCELLED" if call_count >= 1 else "RUNNING"

            def execute_side_effect(query, params=None):
                sql = str(query)
                mock_result = MagicMock()
                if "COALESCE" in sql:
                    # _next_sequence query: must return an integer at index 0
                    mock_result.fetchone.return_value = (1,)
                elif SELECT_MOLECULE_SQL in sql:
                    mock_result.fetchone.return_value = MOLECULE_ROW
                elif SELECT_RUN_CONTEXT_WITH_PROFILE_SQL in sql:
                    mock_result.fetchone.return_value = ({}, {}, None, None, None)
                elif SELECT_CONFIG_AND_METADATA_SQL in sql:
                    mock_result.fetchone.return_value = ({}, {})
                elif SELECT_STATUS_SQL in sql:
                    # Cancellation check: return the status string at index 0
                    mock_result.fetchone.return_value = (status, 1)
                else:
                    # FOR UPDATE, UPDATE, INSERT: generic mock with integer at index 0
                    mock_result.fetchone.return_value = (1,)
                return mock_result

            s = MagicMock()
            s.execute.side_effect = execute_side_effect
            call_count += 1
            return s

        ctx = MagicMock()
        ctx.__enter__ = lambda self: make_session()
        ctx.__exit__ = MagicMock(return_value=False)

        with patch(GET_DB_SESSION_PATCH_TARGET, return_value=ctx):
            result = execute_run(SAMPLE_RUN_ID)

        assert result["converged"] is False
        assert result["iterations"] == 0  # cancelled before iteration 1 event


class TestExecuteRunLifecycleGuards:
    def test_returns_stale_result_before_marking_old_generation_running(self) -> None:
        session = MagicMock()
        session.execute.return_value.fetchone.return_value = (3,)
        ctx = MagicMock()
        ctx.__enter__ = lambda self: session
        ctx.__exit__ = MagicMock(return_value=False)

        with patch(GET_DB_SESSION_PATCH_TARGET, return_value=ctx):
            result = execute_run(SAMPLE_RUN_ID, execution_generation=2)

        assert result["status"] == "STALE"
        assert result["algorithm"] == "unknown"
        assert not any(
            "status = 'RUNNING'" in str(call.args[0]) for call in session.execute.call_args_list
        )

    def test_raises_clear_error_when_run_has_no_molecule(self) -> None:
        session = MagicMock()

        def execute_side_effect(query, params=None):
            del params
            sql = str(query)
            result = MagicMock()
            if "SELECT execution_generation" in sql:
                result.fetchone.return_value = (None,)
            elif "UPDATE runs" in sql:
                result.rowcount = 0
                result.fetchone.return_value = None
            else:
                result.fetchone.return_value = None
            return result

        session.execute.side_effect = execute_side_effect
        ctx = MagicMock()
        ctx.__enter__ = lambda self: session
        ctx.__exit__ = MagicMock(return_value=False)

        with patch(GET_DB_SESSION_PATCH_TARGET, return_value=ctx):
            with pytest.raises(RuntimeError, match="Unable to resolve molecule"):
                execute_run(SAMPLE_RUN_ID)


class TestExecuteRunErrorHandling:
    def test_raises_exception_on_db_failure(self) -> None:
        """execute_run re-raises exceptions so RQ routes to on_job_failure."""
        call_count = 0

        def make_session():
            nonlocal call_count
            s = MagicMock()
            if call_count == 0:
                # First session: initial RUNNING transition — succeeds
                s.execute.side_effect = _make_session(status="RUNNING").execute.side_effect
            else:
                # Second session (first cancellation check) — raises
                s.execute.side_effect = RuntimeError("DB explosion")
            call_count += 1
            return s

        ctx = MagicMock()
        ctx.__enter__ = lambda self: make_session()
        ctx.__exit__ = MagicMock(return_value=False)

        with patch(GET_DB_SESSION_PATCH_TARGET, return_value=ctx):
            with pytest.raises(RuntimeError, match="DB explosion"):
                execute_run(SAMPLE_RUN_ID)
