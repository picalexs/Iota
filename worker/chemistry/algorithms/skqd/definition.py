"""Registered SKQD execution entry point."""

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
from worker.chemistry.algorithms.skqd.workflow import run_skqd
from worker.chemistry.progress import ProgressCallback
from worker.chemistry.solver_utils import resolve_algorithm_config


def run_skqd_algorithm(
    backend: BackendAdapter,
    config: dict[str, Any],
    hamiltonian_bundle: object,
    progress_callback: ProgressCallback | None,
    backend_context: BackendExecutionContext | None,
) -> AlgorithmResult:
    sampler = backend.create_sampler(backend_context)
    return run_skqd(
        hamiltonian=hamiltonian_bundle,
        backend=sampler,
        config=config,
        progress_callback=progress_callback,
        backend_context=backend_context,
    )


ALGORITHM_DEFINITION = AlgorithmDefinition(
    algorithm=RunAlgorithm.SKQD.value,
    runner=run_skqd_algorithm,
    config_namespace=RunAlgorithm.SKQD.value,
    config_resolver=partial(resolve_algorithm_config, algorithm=RunAlgorithm.SKQD.value),
    primitive_requirement=PrimitiveRequirement.SAMPLER,
)
