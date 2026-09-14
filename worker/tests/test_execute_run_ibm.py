"""Tests for IBM Runtime and primitive job observation."""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from qiskit.quantum_info import SparsePauliOp

from worker.adapters.base import AdapterCapabilities, BackendExecutionContext, TrackingPrimitive
from worker.jobs.execute_run import (
    _build_ibm_primitive_job_observer,
    _build_local_primitive_job_observer,
    execute_run,
)

from .execute_run_test_helpers import (
    DISPATCH_ALGORITHM_PATCH_TARGET,
    GET_DB_SESSION_PATCH_TARGET,
    SAMPLE_RUN_ID,
    SELECT_BACKEND_PATCH_TARGET,
    SELECT_STATUS_WITH_GENERATION_SQL,
    _build_pause_after_ibm_job_execute_side_effect,
    _collected_event_payloads,
    _collected_event_types,
    _make_session,
)


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch) -> None:
    monkeypatch.setattr("time.sleep", lambda _: None)


@pytest.fixture(autouse=True)
def stub_hamiltonian_build(monkeypatch) -> None:
    """Keep IBM observer tests lightweight when they execute a full run."""
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


class TestIbmRuntimeSubmissionStatus:
    def test_marks_run_submitted_when_runtime_job_id_is_observed(self) -> None:
        session = _make_session(status="RUNNING")
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=session)
        ctx.__exit__ = MagicMock(return_value=False)
        job = SimpleNamespace(
            status=lambda: "QUEUED",
            queue_info=lambda: SimpleNamespace(position=4),
        )

        with patch(GET_DB_SESSION_PATCH_TARGET, return_value=ctx):
            observer = _build_ibm_primitive_job_observer(
                run_id=SAMPLE_RUN_ID,
                run_wall_start=0.0,
            )
            observer(job, {"job_id": "runtime-job-123", "backend": "ibm_brisbane"})

        update_params = [
            call.args[1]
            for call in session.execute.call_args_list
            if len(call.args) > 1
            and isinstance(call.args[1], dict)
            and call.args[1].get("ibm_job_id") == "runtime-job-123"
        ]
        assert update_params
        types = _collected_event_types(session)
        payloads = _collected_event_payloads(session)
        assert "status_changed" in types
        assert "ibm_job_submitted" in types
        assert "ibm_status_poll" in types
        assert any(payload.get("status") == "SUBMITTED_TO_IBM" for payload in payloads)
        assert any(
            payload.get("ibm_status") == "QUEUED" and payload.get("queued_count") == 4
            for payload in payloads
        )

    def test_runtime_job_wrapper_records_completion_timing_metrics(self) -> None:
        session = _make_session(status="SUBMITTED_TO_IBM")
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=session)
        ctx.__exit__ = MagicMock(return_value=False)

        class RuntimeJob:
            statuses = ["QUEUED", "RUNNING", "DONE", "DONE"]

            def status(self):
                if len(self.statuses) > 1:
                    return self.statuses.pop(0)
                return self.statuses[0]

            def queue_info(self):
                return None

            def metrics(self):
                return {
                    "timestamps": {
                        "created": "2026-05-18T19:50:00Z",
                        "running": "2026-05-18T20:16:50Z",
                        "finished": "2026-05-18T20:18:32Z",
                    },
                    "usage": {"quantum_seconds": 101.0},
                }

            def result(self, *args, **kwargs):
                return {"ok": True}

        with patch(GET_DB_SESSION_PATCH_TARGET, return_value=ctx):
            observer = _build_ibm_primitive_job_observer(
                run_id=SAMPLE_RUN_ID,
                run_wall_start=0.0,
            )
            observed_job = observer(
                RuntimeJob(),
                {
                    "job_id": "runtime-job-123",
                    "backend": "ibm_miami",
                    "pub_count": 1,
                    "shots": 556,
                },
            )
            assert observed_job is not None
            assert observed_job.result() == {"ok": True}

        payloads = _collected_event_payloads(session)
        completion_events = [
            payload
            for payload in payloads
            if payload.get("phase") == "complete" and isinstance(payload.get("ibm_timing"), dict)
        ]
        assert completion_events
        timing = completion_events[-1]["ibm_timing"]
        assert timing["pending_seconds"] == pytest.approx(1610.0)
        assert timing["usage_seconds"] == pytest.approx(101.0)
        assert timing["total_seconds"] == pytest.approx(1712.0)
        assert completion_events[-1]["pub_count"] == 1
        assert completion_events[-1]["shots"] == 556

    def test_runtime_job_wrapper_marks_remote_cancellation_as_cancelled(self) -> None:
        session = _make_session(status="RUNNING")
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=session)
        ctx.__exit__ = MagicMock(return_value=False)

        class RuntimeJob:
            def __init__(self) -> None:
                self._statuses = ["QUEUED", "CANCELLED"]
                self.result_calls = 0

            def status(self):
                if len(self._statuses) > 1:
                    return self._statuses.pop(0)
                return self._statuses[0]

            def queue_info(self):
                return None

            def result(self, *args, **kwargs):
                self.result_calls += 1
                return {"unexpected": True}

        job = RuntimeJob()

        with patch(GET_DB_SESSION_PATCH_TARGET, return_value=ctx):
            observer = _build_ibm_primitive_job_observer(
                run_id=SAMPLE_RUN_ID,
                run_wall_start=0.0,
            )
            observed_job = observer(
                job,
                {
                    "job_id": "runtime-job-123",
                    "backend": "ibm_pittsburgh",
                    "pub_count": 1,
                    "shots": 556,
                },
            )
            assert observed_job is not None
            with pytest.raises(RuntimeError, match="runtime-job-123"):
                observed_job.result()

        payloads = _collected_event_payloads(session)
        assert any(payload.get("status") == "SUBMITTED_TO_IBM" for payload in payloads)
        assert any(
            payload.get("status") == "CANCELLED" and payload.get("reason") == "ibm_job_cancelled"
            for payload in payloads
        )
        assert any(
            payload.get("ibm_status") == "CANCELLED" and payload.get("phase") == "poll"
            for payload in payloads
        )
        assert job.result_calls == 0

    def test_runtime_job_wrapper_requests_remote_cancel_when_local_run_is_cancelled(self) -> None:
        session = MagicMock()
        status_rows = [("RUNNING", 1), ("CANCELLED", 1)]

        def execute_side_effect(query, params=None):
            sql = str(query)
            mock_result = MagicMock()
            if "COALESCE" in sql:
                mock_result.fetchone.return_value = (1,)
            elif SELECT_STATUS_WITH_GENERATION_SQL in sql:
                row = status_rows.pop(0) if status_rows else ("CANCELLED", 1)
                mock_result.fetchone.return_value = row
            else:
                mock_result.fetchone.return_value = (1,)
            return mock_result

        session.execute.side_effect = execute_side_effect
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=session)
        ctx.__exit__ = MagicMock(return_value=False)

        class RuntimeJob:
            def __init__(self) -> None:
                self.cancel_calls = 0

            def status(self):
                return "QUEUED"

            def queue_info(self):
                return None

            def cancel(self):
                self.cancel_calls += 1

            def result(self, *args, **kwargs):
                return {"unexpected": True}

        job = RuntimeJob()

        with patch(GET_DB_SESSION_PATCH_TARGET, return_value=ctx):
            observer = _build_ibm_primitive_job_observer(
                run_id=SAMPLE_RUN_ID,
                run_wall_start=0.0,
            )
            observed_job = observer(
                job,
                {
                    "job_id": "runtime-job-123",
                    "backend": "ibm_miami",
                    "pub_count": 4,
                    "shots": 8192,
                },
            )
            assert observed_job is not None
            with pytest.raises(RuntimeError, match=SAMPLE_RUN_ID):
                observed_job.result()

        payloads = _collected_event_payloads(session)
        assert any(payload.get("phase") == "submitted" for payload in payloads)
        assert any(payload.get("phase") == "poll" for payload in payloads)
        assert job.cancel_calls == 1

    def test_local_primitive_job_wrapper_cancels_when_run_is_cancelled(self) -> None:
        call_count = 0

        def make_session():
            nonlocal call_count
            status = "RUNNING" if call_count == 0 else "CANCELLED"
            call_count += 1
            session = MagicMock()
            result = MagicMock()
            result.fetchone.return_value = (status,)
            session.execute.return_value = result
            context = MagicMock()
            context.__enter__ = MagicMock(return_value=session)
            context.__exit__ = MagicMock(return_value=False)
            return context

        class LocalJob:
            def __init__(self) -> None:
                self.cancel_calls = 0

            def done(self) -> bool:
                return False

            def in_final_state(self) -> bool:
                return False

            def cancel(self) -> None:
                self.cancel_calls += 1

            def result(self, *args, **kwargs):
                return {"unexpected": True}

        job = LocalJob()
        observer = _build_local_primitive_job_observer(run_id=SAMPLE_RUN_ID)

        with (
            patch(GET_DB_SESSION_PATCH_TARGET, side_effect=make_session),
            patch("worker.jobs.local_observation.time.sleep"),
        ):
            observed_job = observer(job, {"backend": "aer_simulator"})
            assert observed_job is not None
            with pytest.raises(RuntimeError, match=SAMPLE_RUN_ID):
                observed_job.result()

        assert job.cancel_calls == 1

    def test_execute_run_pauses_after_active_ibm_job_finishes_before_next_submission(self) -> None:
        session = MagicMock()
        session.get_bind.return_value.dialect.name = "postgresql"
        status_rows = [
            ("RUNNING", 1),
            ("RUNNING", 1),
            ("RUNNING", 1),
            ("PAUSING", 1),
            ("PAUSING", 1),
        ]
        status_generation_rows = [
            ("RUNNING", 1),
            ("PAUSING", 1),
            ("PAUSING", 1),
        ]
        config_snapshot = {
            "algorithm": "vqe",
            "mode": "advanced",
            "backend_target": "ibm_runtime",
            "backend_options": {
                "backend_name": "ibm_miami",
                "token": "fake-token",
                "instance": "fake-instance",
            },
            "advanced_config": {"algorithm": "vqe"},
        }
        metadata = {
            "algorithm": "vqe",
            "mode": "advanced",
            "backend_target": "ibm_runtime",
        }

        session.execute.side_effect = _build_pause_after_ibm_job_execute_side_effect(
            status_rows=status_rows,
            status_generation_rows=status_generation_rows,
            config_snapshot=config_snapshot,
            metadata=metadata,
        )
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=session)
        ctx.__exit__ = MagicMock(return_value=False)

        class RuntimeJob:
            def __init__(self) -> None:
                self._statuses = ["QUEUED", "DONE", "DONE"]
                self.cancel_calls = 0

            def status(self):
                if len(self._statuses) > 1:
                    return self._statuses.pop(0)
                return self._statuses[0]

            def queue_info(self):
                return None

            def cancel(self):
                self.cancel_calls += 1

            def result(self, *args, **kwargs):
                return {"ok": True}

        job = RuntimeJob()
        primitive_run_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

        def primitive_run(*args, **kwargs):
            primitive_run_calls.append((args, kwargs))
            return job

        primitive = SimpleNamespace(run=primitive_run)

        class FakeIbmAdapter:
            @property
            def capabilities(self) -> AdapterCapabilities:
                return AdapterCapabilities(
                    backend_target="ibm_runtime",
                    enabled=True,
                    supports_noise_profile=False,
                )

            def create_estimator(
                self,
                context: BackendExecutionContext | None = None,
            ) -> TrackingPrimitive:
                assert context is not None
                return TrackingPrimitive(
                    primitive,
                    job_ids=[],
                    run_guard=context.primitive_run_guard,
                    job_observer=context.primitive_job_observer,
                    job_metadata={
                        "backend": "ibm_miami",
                        "backend_target": "ibm_runtime",
                        "selection_policy": "requested",
                    },
                )

            def create_sampler(
                self,
                context: BackendExecutionContext | None = None,
            ) -> TrackingPrimitive:
                return self.create_estimator(context)

            def execution_metadata(
                self,
                context: BackendExecutionContext | None = None,
            ) -> dict[str, Any]:
                del context
                return {
                    "resolved_backend_name": "ibm_miami",
                    "primitive_family": "qiskit_ibm_runtime.EstimatorV2",
                }

        def fake_dispatch_algorithm(**kwargs):
            backend = kwargs["backend"]
            backend_context = kwargs["backend_context"]
            estimator = backend.create_estimator(backend_context)
            assert estimator.run([(object(), object())]).result() == {"ok": True}
            estimator.run([(object(), object())]).result()
            raise AssertionError("expected pause before second IBM submission")

        with (
            patch(GET_DB_SESSION_PATCH_TARGET, return_value=ctx),
            patch(SELECT_BACKEND_PATCH_TARGET, return_value=FakeIbmAdapter()),
            patch(DISPATCH_ALGORITHM_PATCH_TARGET, side_effect=fake_dispatch_algorithm),
        ):
            result = execute_run(SAMPLE_RUN_ID)

        payloads = _collected_event_payloads(session)
        assert result["status"] == "PAUSED"
        assert len(primitive_run_calls) == 1
        assert job.cancel_calls == 0
        assert any(payload.get("phase") == "complete" for payload in payloads)
        assert any(payload.get("status") == "PAUSED" for payload in payloads)
