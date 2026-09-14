"""Pytest fixtures for worker tests."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from qiskit.quantum_info import SparsePauliOp


@pytest.fixture
def sample_run_id() -> str:
    """Return a deterministic sample run id."""
    return "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def mock_hamiltonian_bundle() -> SimpleNamespace:
    """Return a compact Hamiltonian bundle usable by dense and sampling solvers."""
    return SimpleNamespace(
        dense_operator_matrix=np.array(
            [
                [-1.0, 0.05, 0.0, 0.0],
                [0.05, -0.7, 0.02, 0.0],
                [0.0, 0.02, -0.4, 0.03],
                [0.0, 0.0, 0.03, -0.2],
            ],
            dtype=complex,
        ),
        pauli_hamiltonian=SparsePauliOp.from_list([("ZI", -0.5), ("IZ", -0.25)]),
        num_spatial_orbitals=1,
        num_qubits=2,
        num_electrons_alpha=1,
        num_electrons_beta=0,
        one_body_tensor=np.zeros((1, 1), dtype=float),
        two_body_tensor=np.zeros((1, 1, 1, 1), dtype=float),
        constant=0.0,
        metadata={"hf_energy": -1.0, "casci_energy": -1.05},
    )


@pytest.fixture
def mock_backend_adapter() -> SimpleNamespace:
    """Return a backend adapter that records primitive factory calls."""
    calls: list[str] = []

    def create_estimator() -> object:
        calls.append("estimator")
        return object()

    def create_sampler() -> object:
        calls.append("sampler")
        return object()

    return SimpleNamespace(
        calls=calls,
        create_estimator=create_estimator,
        create_sampler=create_sampler,
    )


@pytest.fixture
def capture_progress() -> tuple[list[dict[str, Any]], Callable[[dict[str, Any]], None]]:
    """Collect progress events from solver callbacks."""
    events: list[dict[str, Any]] = []
    return events, events.append
