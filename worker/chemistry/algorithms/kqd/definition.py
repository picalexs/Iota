"""Registered KQD execution entry point."""

from __future__ import annotations

from functools import partial
from typing import Any

from shared.contracts.identifiers import RunAlgorithm
from worker.adapters.base import BackendAdapter, BackendExecutionContext
from worker.chemistry.algorithm_contracts import (
    AlgorithmDefinition,
    AlgorithmResult,
    PrimitiveRequirement,
)
from worker.chemistry.algorithms.kqd.workflow import run_kqd
from worker.chemistry.progress import ProgressCallback
from worker.chemistry.projected_execution import (
    ProjectedExecutionPolicy,
    resolve_projected_execution_policy,
)
from worker.chemistry.solver_utils import resolve_algorithm_config


def run_kqd_algorithm(
    backend: BackendAdapter,
    config: dict[str, Any],
    hamiltonian_bundle: object,
    progress_callback: ProgressCallback | None,
    backend_context: BackendExecutionContext | None,
) -> AlgorithmResult:
    execution_policy: ProjectedExecutionPolicy = resolve_projected_execution_policy(
        hamiltonian=hamiltonian_bundle,
        backend_context=backend_context,
    )
    primitive = (
        backend.create_estimator(backend_context)
        if execution_policy.requires_estimator
        else None
    )
    return run_kqd(
        hamiltonian=hamiltonian_bundle,
        backend=primitive,
        config=config,
        progress_callback=progress_callback,
        backend_context=backend_context,
        execution_policy=execution_policy,
    )


ALGORITHM_DEFINITION = AlgorithmDefinition(
    algorithm=RunAlgorithm.KQD.value,
    runner=run_kqd_algorithm,
    config_namespace=RunAlgorithm.KQD.value,
    config_resolver=partial(resolve_algorithm_config, algorithm=RunAlgorithm.KQD.value),
    primitive_requirement=PrimitiveRequirement.OPTIONAL_ESTIMATOR,
)
