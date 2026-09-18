"""Shared types for chemistry execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExecutionPlan:
    """Resolved backend path consumed by an algorithm workflow."""

    requested_backend_target: str | None
    actual_path: str
    primitive: str | None
    selection_reason: str

    @property
    def requires_estimator(self) -> bool:
        """Return whether the selected path needs an EstimatorV2 primitive."""
        return self.primitive == "EstimatorV2"


@dataclass(frozen=True)
class AlgorithmResult:
    """Base worker-internal solver result before API normalization."""

    algorithm: str
    primary_energy: float | None
    primary_iterations: int | None
    converged: bool | None


@dataclass(frozen=True)
class ChemistryInput:
    """Input data for chemistry preparation."""

    atoms: list[str | dict[str, Any]]
    coordinates: list[list[float]] | None = None
    charge: int = 0
    multiplicity: int = 1
    basis: str = "sto-3g"
    active_space: tuple[int, int] | None = None


@dataclass(frozen=True)
class PreparedMolecule:
    """Normalized molecular input ready for PySCF construction."""

    atom_spec: list[tuple[str, tuple[float, float, float]]]
    basis: str
    charge: int
    multiplicity: int
    active_space: tuple[int, int] | None = None


@dataclass(frozen=True)
class HamiltonianBundle:
    """Hamiltonian artifacts produced by the worker chemistry pipeline."""

    num_spatial_orbitals: int
    num_qubits: int
    num_electrons_alpha: int
    num_electrons_beta: int
    one_body_tensor: Any
    two_body_tensor: Any
    constant: float
    pauli_hamiltonian: Any
    metadata: dict[str, Any]


@dataclass(frozen=True)
class VQEResult(AlgorithmResult):
    """Worker-internal VQE result."""

    optimal_parameters: list[float]
    convergence_trace: list[float]
    optimizer_diagnostics: dict[str, Any] = field(default_factory=dict)
    bloch_vectors: list[list[float]] | None = None
    density_matrix_real: list[list[float]] | None = None
    density_matrix_imag: list[list[float]] | None = None
    circuit_artifacts: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class SQDResult(AlgorithmResult):
    """Worker-internal SQD result."""

    sci_energies: list[float]
    configuration_recovery_trace: list[dict[str, Any]]
    spin_diagnostics: dict[str, Any]
    postselection_summary: dict[str, Any] = field(default_factory=dict)
    subsampling_summary: dict[str, Any] = field(default_factory=dict)
    sci_result_package: dict[str, Any] = field(default_factory=dict)
    circuit_artifacts: list[dict[str, Any]] = field(default_factory=list)
    circuit_artifact_policy: dict[str, Any] = field(default_factory=dict)
    best_sci_state: Any | None = field(default=None, repr=False, compare=False)


@dataclass(frozen=True)
class KQDResult(AlgorithmResult):
    """Worker-internal KQD result."""

    ritz_values: list[float]
    krylov_rank: int
    orthogonality_metrics: dict[str, Any]
    matrix_element_summary: dict[str, Any] = field(default_factory=dict)
    raw_ritz_values: list[float] = field(default_factory=list)
    stability_summary: dict[str, Any] = field(default_factory=dict)
    circuit_artifacts: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class QFDResult(AlgorithmResult):
    """Worker-internal QFD result."""

    filter_eigenvalues: list[float]
    conditioning_summary: dict[str, Any]
    matrix_element_summary: dict[str, Any] = field(default_factory=dict)
    raw_filter_eigenvalues: list[float] = field(default_factory=list)
    stability_summary: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class QSEResult(AlgorithmResult):
    """Worker-internal QSE result."""

    eigenvalues: list[float]
    overlap_condition: float
    reference_state_energy: float
    residual_norm: float | None = None
    relative_residual: float | None = None
    convergence_threshold: float | None = None
    reference_circuit_artifacts: list[dict[str, Any]] = field(default_factory=list)
    reference_method: str = "unknown"
    execution_mode: str | None = None
    excitation_level: str = "unknown"
    regularization: float | None = None
    conditioning_summary: dict[str, Any] = field(default_factory=dict)
    matrix_element_summary: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SKQDResult(AlgorithmResult):
    """Worker-internal SKQD result."""

    sqd_core: dict[str, Any]
    krylov_extension_diagnostics: dict[str, Any]
    circuit_artifacts: list[dict[str, Any]] = field(default_factory=list)
    circuit_artifact_policy: dict[str, Any] = field(default_factory=dict)
