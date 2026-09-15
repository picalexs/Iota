"""Unit tests for shared projected-subspace numerical policies."""

import numpy as np
import pytest

from worker.chemistry.algorithms.kqd import workflow as kqd_solver
from worker.chemistry.algorithms.qfd import workflow as qfd_solver
from worker.chemistry.projected_subspace import (
    orthonormalize_candidate,
    projected_matrix_converged,
)


@pytest.mark.parametrize(
    ("diagnostics", "expected"),
    [
        (
            {"stability_state": "stable", "overlap_condition": 1.0, "overlap_min_eigenvalue": 1.0},
            True,
        ),
        (
            {
                "stability_state": "stable",
                "overlap_condition": 1e10,
                "overlap_min_eigenvalue": 1e-3,
            },
            True,
        ),
        (
            {
                "stability_state": "stable",
                "overlap_condition": 1e10 + 1,
                "overlap_min_eigenvalue": 1e-3,
            },
            False,
        ),
        (
            {"stability_state": "stable", "overlap_condition": 1.0, "overlap_min_eigenvalue": 0.0},
            False,
        ),
        (
            {
                "stability_state": "stabilized",
                "overlap_condition": 1.0,
                "overlap_min_eigenvalue": 1.0,
            },
            False,
        ),
    ],
)
def test_projected_matrix_converged_applies_the_shared_stability_gate(
    diagnostics: dict[str, object],
    expected: bool,
) -> None:
    assert projected_matrix_converged(diagnostics) is expected


def test_kqd_and_qfd_keep_legacy_convergence_aliases() -> None:
    assert kqd_solver._projected_matrix_converged is projected_matrix_converged
    assert qfd_solver._projected_matrix_converged is projected_matrix_converged


def test_orthonormalize_candidate_projects_and_normalizes() -> None:
    candidate, norm = orthonormalize_candidate(
        np.array([1.0, 1.0, 1.0], dtype=complex),
        [np.array([1.0, 0.0, 0.0], dtype=complex)],
    )

    assert norm == pytest.approx(np.sqrt(2.0))
    assert candidate is not None
    np.testing.assert_allclose(candidate, [0.0, 1 / np.sqrt(2), 1 / np.sqrt(2)])


def test_orthonormalize_candidate_rejects_dependent_vector() -> None:
    candidate, norm = orthonormalize_candidate(
        np.array([2.0, 0.0], dtype=complex),
        [np.array([1.0, 0.0], dtype=complex)],
    )

    assert candidate is None
    assert norm == pytest.approx(0.0)


def test_skqd_keeps_legacy_orthonormalization_alias() -> None:
    from worker.chemistry import skqd_solver

    assert skqd_solver._orthonormalize_krylov_candidate is orthonormalize_candidate
