"""Registered QFD execution entry point."""

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
from worker.chemistry.algorithms.qfd.config import resolve_qfd_config
from worker.chemistry.algorithms.qfd.workflow import run_qfd
from worker.chemistry.matrix_elements import hardware_projected_dimension_limit
from worker.chemistry.progress import ProgressCallback
from worker.chemistry.projected_execution import (
    ProjectedExecutionPolicy,
    resolve_projected_execution_policy,
)
from worker.chemistry.solver_utils import resolve_algorithm_config


def run_qfd_algorithm(
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
    resolved_config = resolve_algorithm_config(config, RunAlgorithm.QFD.value)
    uses_branch_estimator = execution_policy.actual_path == "branch_estimator"
    qfd_config = resolve_qfd_config(
        resolved_config,
        default_num_time_points=7 if uses_branch_estimator else 16,
    )
    if uses_branch_estimator and qfd_config.num_time_points > hardware_projected_dimension_limit():
        raise ValueError(
            "QFD branch matrix-element execution supports at most "
            f"{hardware_projected_dimension_limit()} time points per run"
        )
    primitive = (
        backend.create_estimator(backend_context)
        if execution_policy.requires_estimator
        else None
    )
    return run_qfd(
        hamiltonian=hamiltonian_bundle,
        backend=primitive,
        config=config,
        progress_callback=progress_callback,
        backend_context=backend_context,
        execution_policy=execution_policy,
    )


ALGORITHM_DEFINITION = AlgorithmDefinition(
    algorithm=RunAlgorithm.QFD.value,
    runner=run_qfd_algorithm,
    config_namespace=RunAlgorithm.QFD.value,
    config_resolver=partial(resolve_algorithm_config, algorithm=RunAlgorithm.QFD.value),
    primitive_requirement=PrimitiveRequirement.OPTIONAL_ESTIMATOR,
)
