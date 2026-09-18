"""Generic boundary for registered worker algorithm execution."""

from __future__ import annotations

from typing import Any

from worker.adapters.base import BackendAdapter, BackendExecutionContext
from worker.chemistry.algorithm_contracts import (
    AlgorithmDefinition,
    PrimitiveRequirement,
)
from worker.chemistry.algorithms.registry import algorithm_definitions as _algorithm_definitions
from worker.chemistry.progress import ProgressCallback
from worker.chemistry.types import AlgorithmResult
from worker.exceptions import BackendError


def dispatch_algorithm(
    *,
    algorithm: str,
    backend: BackendAdapter,
    config_snapshot: dict[str, Any],
    hamiltonian_bundle: object,
    progress_callback: ProgressCallback | None = None,
    backend_context: BackendExecutionContext | None = None,
) -> AlgorithmResult:
    """Resolve and execute one package-owned algorithm definition."""
    definitions = _algorithm_definitions()
    definition = definitions.get(algorithm)
    if definition is None:
        supported = ", ".join(sorted(definitions))
        raise BackendError(
            f"algorithm '{algorithm}' is not enabled in worker rollout (supported: {supported})"
        )
    resolved_config = definition.config_resolver(config_snapshot)
    return definition.runner(
        backend,
        resolved_config,
        hamiltonian_bundle,
        progress_callback,
        backend_context,
    )


def supported_algorithms() -> set[str]:
    """Return currently enabled algorithm identifiers."""
    return set(_algorithm_definitions())


def algorithm_definitions() -> dict[str, AlgorithmDefinition]:
    """Return a copy of package-owned algorithm registry metadata."""
    return _algorithm_definitions()


__all__ = [
    "AlgorithmDefinition",
    "PrimitiveRequirement",
    "algorithm_definitions",
    "dispatch_algorithm",
    "supported_algorithms",
]
