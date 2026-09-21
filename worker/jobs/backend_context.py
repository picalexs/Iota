"""Backend execution-context assembly for the worker run story."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from worker.adapters.base import (
    BackendExecutionContext,
    PrimitiveJobObserver,
    PrimitiveRunGuard,
)
from worker.chemistry.backend_selector import build_backend_execution_context
from worker.chemistry.aer_runtime import validate_aer_runtime

from .execution_config import (
    _chemistry_options_from_config,
    _noise_profile_from_config,
    _selection_policy_from_config,
)

IBMJobObserverFactory = Callable[..., PrimitiveJobObserver]
LocalJobObserverFactory = Callable[..., PrimitiveJobObserver]
RunGuardFactory = Callable[[str], PrimitiveRunGuard]


def build_backend_context_for_run(
    *,
    run_id: str,
    backend_target: str,
    backend_options_runtime: dict[str, Any],
    config_snapshot: dict[str, Any],
    run_wall_start: float,
    run_guard_factory: RunGuardFactory,
    ibm_job_observer_factory: IBMJobObserverFactory,
    local_job_observer_factory: LocalJobObserverFactory,
) -> BackendExecutionContext:
    """Build backend options and attach target-specific observation callbacks."""
    backend_context = build_backend_execution_context(
        backend_target=backend_target,
        backend_options=backend_options_runtime,
        noise_profile=_noise_profile_from_config(config_snapshot),
        selection_policy=_selection_policy_from_config(config_snapshot),
        chemistry_options=_chemistry_options_from_config(config_snapshot),
    )
    if backend_context.backend_target == "ibm_runtime":
        return BackendExecutionContext(
            backend_target=backend_context.backend_target,
            backend_options=backend_context.backend_options,
            noise_profile=backend_context.noise_profile,
            selection_policy=backend_context.selection_policy,
            shots=backend_context.shots,
            requested_shots=backend_context.requested_shots,
            estimator_precision=backend_context.estimator_precision,
            requested_estimator_precision=backend_context.requested_estimator_precision,
            optimization_level=backend_context.optimization_level,
            simulator_method=backend_context.simulator_method,
            chemistry_options=backend_context.chemistry_options,
            primitive_run_guard=run_guard_factory(run_id),
            primitive_job_observer=ibm_job_observer_factory(
                run_id=run_id,
                run_wall_start=run_wall_start,
            ),
        )

    if backend_context.backend_target != "aer_simulator":
        return backend_context

    validate_aer_runtime(backend_context)

    return BackendExecutionContext(
        backend_target=backend_context.backend_target,
        backend_options=backend_context.backend_options,
        noise_profile=backend_context.noise_profile,
        selection_policy=backend_context.selection_policy,
        shots=backend_context.shots,
        requested_shots=backend_context.requested_shots,
        estimator_precision=backend_context.estimator_precision,
        requested_estimator_precision=backend_context.requested_estimator_precision,
        optimization_level=backend_context.optimization_level,
        simulator_method=backend_context.simulator_method,
        chemistry_options=backend_context.chemistry_options,
        primitive_run_guard=run_guard_factory(run_id),
        primitive_job_observer=local_job_observer_factory(run_id=run_id),
    )


__all__ = ["build_backend_context_for_run"]
