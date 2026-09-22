"""Metrics schema for benchmark results."""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from typing import Any


@dataclass
class BenchmarkMetrics:
    """Metrics from a quantum diagonalization experiment.

    Attributes:
        final_energy: Final computed energy in Hartree.
        reference_energy: Reference energy (e.g., classical ground truth) in Hartree.
        energy_error: Absolute error = |final_energy - reference_energy|.
        iterations: Number of optimization iterations performed.
        wall_time_seconds: Total wall-clock time in seconds.
        converged: Whether the optimization converged.
        convergence_history: List of energy values at each iteration.
        shots_used: Total number of quantum shots used.
        warnings: Captured warning messages observed during execution.
        cobyla_maxfun_adjusted: Whether COBYLA max function evaluations were auto-adjusted.
        convergence_criterion: Human-readable convergence rule applied by the runner.
        diagnostics: Optional structured debug payload from the runner.
    """

    final_energy: float
    reference_energy: float
    energy_error: float
    iterations: int
    wall_time_seconds: float
    converged: bool
    convergence_history: list[float] = field(default_factory=list)
    shots_used: int = 0
    warnings: list[str] = field(default_factory=list)
    cobyla_maxfun_adjusted: bool = False
    chemistry_pipeline: str | None = None
    num_qubits: int | None = None
    hamiltonian_dimension: int | None = None
    active_space: tuple[int, int] | None = None
    convergence_criterion: str | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Export metrics to dictionary."""
        return asdict(self)

    def to_json(self) -> str:
        """Export metrics to JSON string."""
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_json(cls, json_str: str) -> BenchmarkMetrics:
        """Import metrics from JSON string."""
        data = json.loads(json_str)
        return cls(**data)
