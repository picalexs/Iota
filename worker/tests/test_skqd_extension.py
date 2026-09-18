from __future__ import annotations

import numpy as np
import pytest

from worker.chemistry.algorithms.skqd.extension import build_krylov_extension


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
