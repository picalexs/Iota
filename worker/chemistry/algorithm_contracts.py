"""Shared contracts for registered chemistry algorithms."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from worker.adapters.base import BackendAdapter, BackendExecutionContext
from worker.chemistry.progress import ProgressCallback
from worker.chemistry.types import AlgorithmResult

AlgorithmRunner = Callable[
    [
        BackendAdapter,
        dict[str, Any],
        object,
        ProgressCallback | None,
        BackendExecutionContext | None,
    ],
    AlgorithmResult,
]
ConfigResolver = Callable[[dict[str, Any]], dict[str, Any]]


class PrimitiveRequirement(StrEnum):
    """Primitive contract declared by a registered algorithm."""

    ESTIMATOR = "estimator"
    SAMPLER = "sampler"
    OPTIONAL_ESTIMATOR = "optional_estimator"
    SAMPLER_AND_OPTIONAL_ESTIMATOR = "sampler_and_optional_estimator"


@dataclass(frozen=True, slots=True)
class AlgorithmDefinition:
    """Runtime metadata and package-owned entry point for one algorithm."""

    algorithm: str
    runner: AlgorithmRunner
    config_namespace: str
    config_resolver: ConfigResolver
    primitive_requirement: PrimitiveRequirement


__all__ = [
    "AlgorithmDefinition",
    "AlgorithmRunner",
    "ConfigResolver",
    "PrimitiveRequirement",
    "AlgorithmResult",
]
