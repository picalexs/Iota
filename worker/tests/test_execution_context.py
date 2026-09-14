"""Focused tests for the worker execution context records."""

from __future__ import annotations

from worker.adapters.base import BackendExecutionContext
from worker.jobs.execution_context import PreparedRunContext, StartedRunContext


def test_started_context_keeps_resolved_run_and_estimate_inputs() -> None:
    chemistry_input = object()
    context = StartedRunContext(
        expected_generation=3,
        algorithm="vqe",
        mode="advanced",
        backend_target="statevector",
        config_snapshot={"algorithm": "vqe"},
        algorithm_config={"max_iterations": 4},
        backend_options_runtime={},
        chemistry_input=chemistry_input,
        eta_seed_seconds_per_iteration=1.5,
        eta_seed_confidence=0.8,
    )

    assert context.expected_generation == 3
    assert context.chemistry_input is chemistry_input
    assert context.eta_seed_confidence == 0.8


def test_prepared_context_keeps_dispatch_dependencies_in_order() -> None:
    backend_adapter = object()
    backend_context = BackendExecutionContext(backend_target="statevector")
    hamiltonian_bundle = object()

    context = PreparedRunContext(backend_adapter, backend_context, hamiltonian_bundle)

    assert context.backend_adapter is backend_adapter
    assert context.backend_context is backend_context
    assert context.hamiltonian_bundle is hamiltonian_bundle
