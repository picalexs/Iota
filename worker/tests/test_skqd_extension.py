from __future__ import annotations

import numpy as np
import pytest
from scipy.sparse.linalg import aslinearoperator

from worker.chemistry.algorithms.skqd.extension import (
    build_krylov_extension,
    build_sector_krylov_extension,
    emit_skqd_krylov_progress,
)
from worker.chemistry.hamiltonian_action import HamiltonianAction


def test_dense_krylov_extension_builds_projected_solution() -> None:
    operator = np.diag([-1.0, 0.5]).astype(complex)
    reference_state = np.array([1.0, 1.0], dtype=complex) / np.sqrt(2.0)

    eigenvalues, basis_rank, diagnostics, ground_state = build_krylov_extension(
        operator,
        reference_state=reference_state,
        seeded_from_sqd=False,
        target_rank=2,
        time_step=0.2,
        residual_tolerance=1e-8,
        progress_callback=None,
    )

    assert basis_rank == 2
    assert eigenvalues == pytest.approx([-1.0, 0.5])
    assert diagnostics["basis_numerical_rank"] == pytest.approx(2.0)
    assert ground_state is not None
    assert abs(ground_state[0]) == pytest.approx(1.0)
    assert abs(ground_state[1]) == pytest.approx(0.0)


def test_dense_krylov_extension_keeps_small_nonzero_time() -> None:
    operator = np.asarray([[0.0, 1e10], [1e10, 0.0]], dtype=complex)

    _eigenvalues, basis_rank, _diagnostics, _ground_state = build_krylov_extension(
        operator,
        reference_state=np.asarray([1.0, 0.0], dtype=complex),
        seeded_from_sqd=False,
        target_rank=2,
        time_step=7e-10,
        residual_tolerance=1e-8,
        progress_callback=None,
    )

    assert basis_rank == 2


def test_sector_krylov_extension_keeps_small_nonzero_time() -> None:
    action = HamiltonianAction(
        norb=2,
        nelec=(1, 0),
        dimension=2,
        linear_operator=aslinearoperator(
            np.asarray([[0.0, 1e10], [1e10, 0.0]], dtype=complex)
        ),
    )

    _eigenvalues, basis_rank, _diagnostics, _ground_state = build_sector_krylov_extension(
        action,
        reference_state=np.asarray([1.0, 0.0], dtype=complex),
        seeded_from_sqd=False,
        target_rank=2,
        time_step=7e-10,
        residual_tolerance=1e-8,
        progress_callback=None,
    )

    assert basis_rank == 2


def test_krylov_progress_distinguishes_sqd_seed_from_occupancy_seed() -> None:
    events = []

    emit_skqd_krylov_progress(
        progress_callback=events.append,
        iteration=1,
        completed_iterations=1,
        energy=-1.0,
        total_iterations=2,
        candidate_norm=1.0,
        seeded_from_sqd=True,
    )

    assert events[0]["seeded_from_sqd"] is True
    assert events[0]["seeded_from_sqd_occupancies"] is False
