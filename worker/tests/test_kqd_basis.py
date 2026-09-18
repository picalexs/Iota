"""Direct tests for KQD Krylov-basis helpers."""

from types import SimpleNamespace

import numpy as np
import pytest
from qiskit.quantum_info import SparsePauliOp
from scipy.sparse.linalg import aslinearoperator

from worker.adapters.base import BackendExecutionContext
from worker.chemistry.algorithms.kqd.basis import build_krylov_basis, build_sector_krylov_basis
from worker.chemistry.hamiltonian_action import HamiltonianAction


def test_build_krylov_basis_emits_dense_time_evolution_progress() -> None:
    events: list[dict[str, object]] = []
    operator = np.diag([0.0, 1.0]).astype(complex)
    reference = np.array([1.0, 1.0], dtype=complex) / np.sqrt(2.0)

    basis = build_krylov_basis(
        object(),
        operator,
        reference,
        target_rank=2,
        evolution_method="exact",
        time_step=0.2,
        trotter_steps=1,
        progress_callback=events.append,
    )

    assert len(basis) == 2
    assert events[0]["step"] == "time_evolution"
    assert events[0]["time_evolution_backend"] == "dense_matrix"
    assert events[-1]["completed_iterations"] == 2


def test_aer_context_honors_exact_kqd_evolution() -> None:
    hamiltonian = SimpleNamespace(
        pauli_hamiltonian=SparsePauliOp.from_list([("X", 1.0), ("Z", 0.7)])
    )
    operator = hamiltonian.pauli_hamiltonian.to_matrix()
    reference = np.array([1.0, 0.0], dtype=complex)
    time_step = 0.4
    events: list[dict[str, object]] = []

    basis = build_krylov_basis(
        hamiltonian,
        operator,
        reference,
        target_rank=2,
        evolution_method="exact",
        time_step=time_step,
        trotter_steps=1,
        progress_callback=events.append,
        backend_context=BackendExecutionContext(backend_target="aer_simulator"),
    )
    eigenvalues, eigenvectors = np.linalg.eigh(operator)
    expected = eigenvectors @ (np.exp(-1j * eigenvalues * time_step) * (eigenvectors.conj().T @ reference))
    expected /= np.linalg.norm(expected)

    assert basis[1] == pytest.approx(expected)
    assert events[1]["time_evolution_backend"] == "dense_matrix"


def test_build_sector_krylov_basis_keeps_sector_progress_metadata() -> None:
    operator = np.diag([0.0, 1.0]).astype(complex)

    class _Action:
        dimension = 2

        def time_evolve(self, state: np.ndarray, *, time_point: float) -> np.ndarray:
            return np.array([state[0], np.exp(-1j * time_point) * state[1]])

        def project(self, basis: np.ndarray) -> np.ndarray:
            return basis.conj().T @ operator @ basis

    events: list[dict[str, object]] = []
    reference = np.array([1.0, 1.0], dtype=complex) / np.sqrt(2.0)

    basis = build_sector_krylov_basis(
        _Action(),
        reference,
        target_rank=2,
        evolution_method="exact",
        time_step=0.2,
        trotter_steps=1,
        progress_callback=events.append,
    )

    assert len(basis) == 2
    assert events[0]["time_evolution_backend"] == "sector_matrix_free"
    assert events[0]["sector_dimension"] == 2
    assert events[1]["implemented_evolution_method"] == "sector_expm_multiply"


def test_build_sector_krylov_basis_honors_trotter_evolution() -> None:
    operator = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=complex)

    class _Action:
        dimension = 2

        def time_evolve(self, state: np.ndarray, *, time_point: float) -> np.ndarray:
            del time_point
            return state

        def to_matrix(self) -> np.ndarray:
            return operator

        def project(self, basis: np.ndarray) -> np.ndarray:
            return basis.conj().T @ operator @ basis

    events: list[dict[str, object]] = []
    reference = np.array([1.0, 0.0], dtype=complex)
    basis = build_sector_krylov_basis(
        _Action(),
        reference,
        target_rank=2,
        evolution_method="trotter",
        time_step=0.2,
        trotter_steps=1,
        progress_callback=events.append,
    )

    assert not np.allclose(basis[1], reference)
    assert events[-1]["implemented_evolution_method"] == "sector_diagonal_residual_trotter"


def test_kqd_dense_and_sector_paths_evolve_small_nonzero_times() -> None:
    time_step = 7e-10
    operator = np.diag([1e10, -1e10]).astype(complex)
    reference = np.array([1.0, 1.0], dtype=complex) / np.sqrt(2.0)
    hamiltonian = SimpleNamespace()

    dense_basis = build_krylov_basis(
        hamiltonian,
        operator,
        reference,
        target_rank=2,
        evolution_method="exact",
        time_step=time_step,
        trotter_steps=1,
        progress_callback=None,
    )

    class _Action:
        dimension = 2

        def __init__(self) -> None:
            self._action = HamiltonianAction(
                norb=2,
                nelec=(1, 0),
                dimension=2,
                linear_operator=aslinearoperator(operator),
            )

        def time_evolve(self, state: np.ndarray, *, time_point: float) -> np.ndarray:
            return self._action.time_evolve(state, time_point=time_point)

        def project(self, basis_matrix: np.ndarray) -> np.ndarray:
            return self._action.project(basis_matrix)

        def expectation(self, state: np.ndarray) -> float:
            return self._action.expectation(state)

    sector_basis = build_sector_krylov_basis(
        _Action(),
        reference,
        target_rank=2,
        evolution_method="exact",
        time_step=time_step,
        trotter_steps=1,
        progress_callback=None,
    )
    expected = np.array(
        [np.exp(-1j * 1e10 * time_step), np.exp(1j * 1e10 * time_step)],
        dtype=complex,
    ) / np.sqrt(2.0)

    assert dense_basis[1] == pytest.approx(expected)
    assert sector_basis[1] == pytest.approx(expected)


def test_build_krylov_basis_rejects_zero_reference() -> None:
    with pytest.raises(ValueError, match="KQD reference state must be non-zero"):
        build_krylov_basis(
            object(),
            np.eye(2, dtype=complex),
            np.zeros(2, dtype=complex),
            target_rank=1,
            evolution_method="exact",
            time_step=0.2,
            trotter_steps=1,
            progress_callback=None,
        )
