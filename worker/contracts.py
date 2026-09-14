"""Small structural contracts shared by worker orchestration boundaries."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from worker.persistence.run_repository import RunRepository as RunRepositoryContract


@runtime_checkable
class SolverResultContract(Protocol):
    """Minimum result fields consumed before algorithm-specific normalization."""

    algorithm: str
    primary_energy: float | None
    primary_iterations: int | None
    converged: bool | None


@runtime_checkable
class ProgressSink(Protocol):
    """Callable boundary for one solver progress event."""

    def __call__(self, payload: dict[str, Any]) -> None:
        """Accept one JSON-compatible progress payload."""


@runtime_checkable
class BackendAdapterContract(Protocol):
    """Backend behavior required by dispatcher and metadata assembly."""

    @property
    def capabilities(self) -> Any:
        """Return the adapter capability descriptor."""

    def create_estimator(self, context: Any = None) -> Any:
        """Create an estimator primitive."""

    def create_sampler(self, context: Any = None) -> Any:
        """Create a sampler primitive."""

    def execution_metadata(self, context: Any = None) -> dict[str, Any]:
        """Return metadata suitable for setup and result payloads."""


@runtime_checkable
class JobObserver(Protocol):
    """Callable boundary for enriching a primitive job after submission."""

    def __call__(self, job: Any, metadata: dict[str, Any]) -> Any | None:
        """Return the observed job wrapper or ``None`` to keep the original."""


@runtime_checkable
class ChemistryInputContract(Protocol):
    """Chemistry fields required by Hamiltonian preparation and metadata."""

    atoms: list[str | dict[str, Any]]
    coordinates: list[list[float]] | None
    charge: int
    multiplicity: int
    basis: str
    active_space: tuple[int, int] | None


@runtime_checkable
class HamiltonianBundleContract(Protocol):
    """Hamiltonian fields required by solvers and execution telemetry."""

    num_spatial_orbitals: int
    num_qubits: int
    num_electrons_alpha: int
    num_electrons_beta: int
    one_body_tensor: Any
    two_body_tensor: Any
    constant: float
    pauli_hamiltonian: Any
    metadata: dict[str, Any]


__all__ = [
    "BackendAdapterContract",
    "ChemistryInputContract",
    "HamiltonianBundleContract",
    "JobObserver",
    "ProgressSink",
    "RunRepositoryContract",
    "SolverResultContract",
]
