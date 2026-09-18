"""Unit tests for the SKQD extension dispatch boundary."""

from types import SimpleNamespace

import numpy as np

from worker.chemistry.algorithms.skqd.execution import (
    SKQDExecutionPlan,
    execute_skqd_extension,
)


def test_execute_skqd_extension_dispatches_dense_seeded_path() -> None:
    operator = np.eye(2, dtype=complex)
    seed = np.array([1.0, 0.0], dtype=complex)
    plan = SKQDExecutionPlan(
        sector_action=None,
        operator=operator,
        operator_dimension=2,
        execution_mode="dense_matrix",
    )

    def build_dense(received_operator, **kwargs):
        assert received_operator is operator
        assert kwargs["seed_state"] is seed
        assert kwargs["seeded_from_sqd"] is True
        return np.array([-1.0]), 1, {"relative_ritz_residual": 0.0}, seed

    outcome = execute_skqd_extension(
        sqd_result=object(),
        plan=plan,
        hamiltonian=object(),
        krylov_extension_dim=3,
        sampling_time_step=0.2,
        residual_tolerance=1e-8,
        progress_callback=None,
        resolve_sector_seed_fn=lambda *args, **kwargs: (None, "unused"),
        resolve_dense_seed_fn=lambda *args, **kwargs: (seed, "sqd_statevector"),
        build_sector_krylov_fn=lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("sector path should not run")
        ),
        build_dense_krylov_fn=build_dense,
        build_sector_hf_reference_fn=lambda *args: seed,
        build_dense_hf_reference_fn=lambda *args, **kwargs: seed,
    )

    assert outcome.seed_source == "sqd_statevector"
    assert outcome.sqd_seed is seed
    assert outcome.krylov_seed is seed
    assert outcome.basis_rank == 1


def test_execute_skqd_extension_dispatches_sector_hf_fallback() -> None:
    action = SimpleNamespace(norb=2, nelec=(1, 1), dimension=4)
    plan = SKQDExecutionPlan(
        sector_action=action,
        operator=None,
        operator_dimension=4,
        execution_mode="sector_matrix_free",
    )
    hf_seed = np.array([1.0, 0.0, 0.0, 0.0], dtype=complex)

    def build_sector(received_action, **kwargs):
        assert received_action is action
        assert kwargs["seed_state"] is hf_seed
        assert kwargs["seeded_from_sqd"] is False
        return np.array([-2.0]), 1, {"relative_ritz_residual": 1e-4}, None

    outcome = execute_skqd_extension(
        sqd_result=object(),
        plan=plan,
        hamiltonian=object(),
        krylov_extension_dim=3,
        sampling_time_step=0.2,
        residual_tolerance=1e-8,
        progress_callback=None,
        resolve_sector_seed_fn=lambda *args, **kwargs: (None, "missing"),
        resolve_dense_seed_fn=lambda *args, **kwargs: (None, "unused"),
        build_sector_krylov_fn=build_sector,
        build_dense_krylov_fn=lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("dense path should not run")
        ),
        build_sector_hf_reference_fn=lambda norb, nelec: hf_seed,
        build_dense_hf_reference_fn=lambda *args, **kwargs: hf_seed,
    )

    assert outcome.seed_source == "hf_sector_reference"
    assert outcome.sqd_seed is None
    assert outcome.krylov_seed is hf_seed
    assert outcome.basis_rank == 1
