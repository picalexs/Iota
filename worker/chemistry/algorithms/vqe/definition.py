"""Registered VQE execution entry point."""

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
from worker.chemistry.algorithms.vqe.workflow import run_vqe
from worker.chemistry.progress import ProgressCallback
from worker.chemistry.solver_utils import resolve_algorithm_config


def run_vqe_algorithm(
    backend: BackendAdapter,
    config: dict[str, Any],
    hamiltonian_bundle: object,
    progress_callback: ProgressCallback | None,
    backend_context: BackendExecutionContext | None,
) -> AlgorithmResult:
    estimator = backend.create_estimator(backend_context)
    return run_vqe(
        hamiltonian=hamiltonian_bundle,
        backend=estimator,
        config=config,
        progress_callback=progress_callback,
        backend_context=backend_context,
    )


ALGORITHM_DEFINITION = AlgorithmDefinition(
    algorithm=RunAlgorithm.VQE.value,
    runner=run_vqe_algorithm,
    config_namespace=RunAlgorithm.VQE.value,
    config_resolver=partial(resolve_algorithm_config, algorithm=RunAlgorithm.VQE.value),
    primitive_requirement=PrimitiveRequirement.ESTIMATOR,
)
