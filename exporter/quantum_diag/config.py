"""Experiment specification and configuration management."""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import Any


# Valid enumeration values for experiment spec
VALID_METHODS = {"RHF", "VQE", "CASCI", "CASSCF", "KQD", "QFD", "SQD", "SKQD", "ADAPT-VQE", "QSE"}
VALID_ANSATZE = {"HEA", "EDA", "UCCSD", "TwoLocal", "RealAmplitudes", "LUCJ"}
VALID_OPTIMIZERS = {"COBYLA", "SLSQP", "SPSA"}


@dataclass
class ExperimentSpec:
    """Specification for a quantum diagonalization experiment.

    Attributes:
        molecule_name: Name of the molecule (e.g., "H2", "LiH").
        basis_set: Basis set name for quantum chemistry (e.g., "sto-3g").
        method: Quantum method to use (e.g., "VQE", "KQD", "QFD", etc., must be in VALID_METHODS).
        ansatz_type: Ansatz type for variational methods (must be in VALID_ANSATZE).
        optimizer: Classical optimizer (must be in VALID_OPTIMIZERS).
        max_iterations: Maximum number of optimization iterations.
        shots: Number of quantum measurement shots (>0).
        seed: Random seed for reproducibility.
        backend_name: Quantum backend name (e.g., "qasm_simulator").
    """

    molecule_name: str
    basis_set: str
    method: str
    ansatz_type: str
    optimizer: str
    max_iterations: int
    shots: int
    seed: int
    backend_name: str

    def __post_init__(self) -> None:
        """Validate fields after initialization."""
        if self.method not in VALID_METHODS:
            raise ValueError(
                f"method '{self.method}' not in {VALID_METHODS}"
            )
        if self.ansatz_type not in VALID_ANSATZE:
            raise ValueError(
                f"ansatz_type '{self.ansatz_type}' not in {VALID_ANSATZE}"
            )
        if self.optimizer not in VALID_OPTIMIZERS:
            raise ValueError(
                f"optimizer '{self.optimizer}' not in {VALID_OPTIMIZERS}"
            )
        if self.shots <= 0:
            raise ValueError(f"shots must be > 0, got {self.shots}")
        if self.max_iterations <= 0:
            raise ValueError(f"max_iterations must be > 0, got {self.max_iterations}")

    def to_dict(self) -> dict[str, Any]:
        """Export spec to dictionary."""
        return asdict(self)

    def to_json(self) -> str:
        """Export spec to JSON string."""
        return json.dumps(self.to_dict(),default=str)

    @classmethod
    def from_json(cls, json_str: str) -> ExperimentSpec:
        """Import spec from JSON string."""
        data = json.loads(json_str)
        return cls(**data)
