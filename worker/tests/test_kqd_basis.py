"""Direct tests for KQD Krylov-basis helpers."""

import numpy as np
import pytest

from worker.chemistry.algorithms.kqd.basis import build_krylov_basis, build_sector_krylov_basis


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
