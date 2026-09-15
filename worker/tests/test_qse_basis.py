"""Unit tests for pure QSE basis candidate acceptance."""

from __future__ import annotations

import numpy as np

from worker.chemistry.algorithms.qse import workflow as qse_solver
from worker.chemistry.algorithms.qse.basis import (
    accept_basis_candidate,
    build_excitation_basis,
)


def test_accept_basis_candidate_normalizes_and_reports_independence() -> None:
    basis: list[np.ndarray] = []
    orthonormal_basis: list[np.ndarray] = []

    independence = accept_basis_candidate(
        np.array([3.0, 4.0]),
        basis=basis,
        orthonormal_basis=orthonormal_basis,
        overlap_threshold=1e-8,
    )

    assert independence == 1.0
    np.testing.assert_allclose(basis, [np.array([0.6, 0.8])])
    np.testing.assert_allclose(orthonormal_basis, [np.array([0.6, 0.8])])


def test_accept_basis_candidate_rejects_zero_and_dependent_vectors() -> None:
    basis = [np.array([1.0, 0.0], dtype=complex)]
    orthonormal_basis = [np.array([1.0, 0.0], dtype=complex)]

    assert (
        accept_basis_candidate(
            np.zeros(2),
            basis=basis,
            orthonormal_basis=orthonormal_basis,
            overlap_threshold=1e-8,
        )
        is None
    )
    assert (
        accept_basis_candidate(
            np.array([2.0, 0.0]),
            basis=basis,
            orthonormal_basis=orthonormal_basis,
            overlap_threshold=1e-8,
        )
        is None
    )
    assert len(basis) == 1


def test_qse_solver_keeps_legacy_basis_alias() -> None:
    assert qse_solver._accept_basis_candidate is accept_basis_candidate


def test_build_excitation_basis_emits_basis_progress() -> None:
    events: list[dict[str, object]] = []
    reference = np.zeros(16, dtype=complex)
    reference[5] = 1.0

    basis = build_excitation_basis(
        reference,
        np.diag(np.linspace(-1.0, 1.0, 16)).astype(complex),
        excitation_level="singles",
        target_rank=2,
        overlap_threshold=1e-10,
        regularization=1e-8,
        progress_callback=events.append,
    )

    assert len(basis) == 2
    assert events[0]["step"] == "build_basis"
    assert events[0]["completed_iterations"] == 1
    assert events[0]["excitation_kind"] == "reference"
