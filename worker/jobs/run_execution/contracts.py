"""Typed contracts shared by worker run-execution lifecycle stages."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any, NamedTuple, TypeAlias

from sqlalchemy.orm import Session

from worker.adapters.base import BackendExecutionContext
from worker.contracts import (
    BackendAdapterContract,
    ChemistryInputContract,
    HamiltonianBundleContract,
    RunRepositoryContract,
)

SessionFactory: TypeAlias = Callable[[], AbstractContextManager[Session]]
TransactionCommitter: TypeAlias = Callable[[Session], None]
RepositoryFactory: TypeAlias = Callable[[Session], RunRepositoryContract]
EventInserter: TypeAlias = Callable[[Session, str, str, dict[str, Any]], None]
StoppedRunResultFactory: TypeAlias = Callable[..., dict[str, Any]]


class StartedRunContext(NamedTuple):
    """Persisted run configuration resolved before backend preparation."""

    expected_generation: int
    algorithm: str
    mode: str
    backend_target: str
    config_snapshot: dict[str, Any]
    algorithm_config: dict[str, Any]
    backend_options_runtime: dict[str, Any]
    chemistry_input: ChemistryInputContract
    eta_seed_seconds_per_iteration: float | None
    eta_seed_confidence: float | None
    chemistry_options_runtime: dict[str, Any] | None = None


class PreparedRunContext(NamedTuple):
    """Backend and Hamiltonian artifacts ready for algorithm dispatch."""

    backend_adapter: BackendAdapterContract
    backend_context: BackendExecutionContext
    hamiltonian_bundle: HamiltonianBundleContract


__all__ = [
    "EventInserter",
    "PreparedRunContext",
    "RepositoryFactory",
    "SessionFactory",
    "StartedRunContext",
    "StoppedRunResultFactory",
    "TransactionCommitter",
]
