"""Tests for worker backend execution-context assembly."""

from __future__ import annotations

from typing import Any

from worker.adapters.base import BackendExecutionContext
from worker.jobs.backend_context import build_backend_context_for_run


def _guard_factory(run_id: str):
    return lambda: run_id


def _ibm_observer_factory(run_id: str, run_wall_start: float):
    return lambda _job, _metadata: (run_id, run_wall_start)


def _local_observer_factory(run_id: str):
    return lambda _job, _metadata: run_id


def _build_context(
    backend_target: str,
    *,
    backend_options: dict[str, Any] | None = None,
) -> BackendExecutionContext:
    return build_backend_context_for_run(
        run_id="run-1",
        backend_target=backend_target,
        backend_options_runtime=backend_options or {},
        config_snapshot={"noise_profile": {"readout_error": 0.02}},
        run_wall_start=12.5,
        run_guard_factory=_guard_factory,
        ibm_job_observer_factory=_ibm_observer_factory,
        local_job_observer_factory=_local_observer_factory,
    )


def test_statevector_context_keeps_backend_options_without_observers() -> None:
    context = _build_context("statevector", backend_options={"shots": 128})

    assert context.backend_target == "statevector"
    assert context.shots == 128
    assert context.noise_profile is None
    assert context.primitive_run_guard is None
    assert context.primitive_job_observer is None


def test_aer_context_attaches_local_observation_callbacks() -> None:
    context = _build_context(
        "aer_simulator",
        backend_options={
            "method": "matrix_product_state",
            "shots": 256,
            "estimator_precision": 0.125,
        },
    )

    assert context.backend_target == "aer_simulator"
    assert context.simulator_method == "matrix_product_state"
    assert context.requested_shots == 256
    assert context.shots == 256
    assert context.requested_estimator_precision == 0.125
    assert context.estimator_precision == 0.125
    assert context.primitive_run_guard is not None
    assert context.primitive_run_guard() == "run-1"
    assert context.primitive_job_observer is not None
    assert context.primitive_job_observer(None, {}) == "run-1"


def test_ibm_context_attaches_runtime_observer_and_preserves_selection_policy() -> None:
    context = build_backend_context_for_run(
        run_id="run-ibm",
        backend_target="ibm_runtime",
        backend_options_runtime={"shots": 256},
        config_snapshot={
            "backend_options": {"selection_policy": "least_busy"},
            "noise_profile": {"readout_error": 0.02},
        },
        run_wall_start=4.0,
        run_guard_factory=_guard_factory,
        ibm_job_observer_factory=_ibm_observer_factory,
        local_job_observer_factory=_local_observer_factory,
    )

    assert context.backend_target == "ibm_runtime"
    assert context.shots == 256
    assert context.selection_policy == "least_busy"
    assert context.primitive_run_guard is not None
    assert context.primitive_run_guard() == "run-ibm"
    assert context.primitive_job_observer is not None
    assert context.primitive_job_observer(None, {}) == ("run-ibm", 4.0)
