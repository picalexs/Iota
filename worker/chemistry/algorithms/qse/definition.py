"""Registered QSE execution entry point."""

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
from worker.chemistry.algorithms.qse.workflow import run_qse
from worker.chemistry.progress import ProgressCallback
from worker.chemistry.projected_execution import (
    QSEExecutionPolicy,
    resolve_qse_execution_policy,
    validate_qse_reference_method,
)
from worker.chemistry.solver_utils import resolve_algorithm_config


def run_qse_algorithm(
    backend: BackendAdapter,
    config: dict[str, Any],
    hamiltonian_bundle: object,
    progress_callback: ProgressCallback | None,
    backend_context: BackendExecutionContext | None,
) -> AlgorithmResult:
    reference_method = str(config.get("reference_method", "vqe")).lower()
    execution_policy: QSEExecutionPolicy = resolve_qse_execution_policy(
        backend_context=backend_context,
        reference_method=reference_method,
    )
    validate_qse_reference_method(
        policy=execution_policy,
        reference_method=reference_method,
    )
    estimator = (
        backend.create_estimator(backend_context)
        if execution_policy.requires_estimator
        else None
    )
    return run_qse(
        hamiltonian=hamiltonian_bundle,
        backend=estimator,
        config=config,
        progress_callback=progress_callback,
        backend_context=backend_context,
        execution_policy=execution_policy,
    )


ALGORITHM_DEFINITION = AlgorithmDefinition(
    algorithm=RunAlgorithm.QSE.value,
    runner=run_qse_algorithm,
    config_namespace=RunAlgorithm.QSE.value,
    config_resolver=partial(resolve_algorithm_config, algorithm=RunAlgorithm.QSE.value),
    primitive_requirement=PrimitiveRequirement.OPTIONAL_ESTIMATOR,
)
