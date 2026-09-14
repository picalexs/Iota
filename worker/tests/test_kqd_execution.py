from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import numpy as np

from worker.chemistry.algorithms.kqd.execution import prepare_kqd_execution


def _prepare(
    *,
    branch: bool,
    sector: bool,
    resolve_operator: Any,
    build_action: Any,
):
    return prepare_kqd_execution(
        hamiltonian=SimpleNamespace(num_qubits=3),
        backend=None,
        backend_context=None,
        should_use_branch_matrix_elements_fn=lambda **_: branch,
        can_use_sector_action_fn=lambda *_: sector,
        build_hamiltonian_action_fn=build_action,
        resolve_operator_matrix_fn=resolve_operator,
        num_qubits_fn=lambda hamiltonian: hamiltonian.num_qubits,
        backend_label_fn=lambda **kwargs: (
            "branch"
            if kwargs["use_branch_matrix_elements"]
            else "sector"
            if kwargs["use_sector_action"]
            else "dense"
        ),
    )


def test_prepare_kqd_execution_resolves_dense_resources() -> None:
    operator = np.eye(8, dtype=complex)

    plan = _prepare(
        branch=False,
        sector=False,
        resolve_operator=lambda _hamiltonian: operator,
        build_action=lambda _hamiltonian: None,
    )

    assert plan.operator is operator
    assert plan.sector_action is None
    assert plan.dimension == 8
    assert plan.time_evolution_backend == "dense"
    assert plan.selection_reason == "problem_uses_dense_projected_matrices"


def test_prepare_kqd_execution_resolves_sector_resources_without_dense_matrix() -> None:
    action = SimpleNamespace(dimension=5)

    plan = _prepare(
        branch=False,
        sector=True,
        resolve_operator=lambda _hamiltonian: (_ for _ in ()).throw(
            AssertionError("sector execution must not resolve a dense matrix")
        ),
        build_action=lambda _hamiltonian: action,
    )

    assert plan.operator is None
    assert plan.sector_action is action
    assert plan.dimension == 5
    assert plan.time_evolution_backend == "sector"
    assert plan.selection_reason == "large_noiseless_problem_uses_sector_matrix_free_action"


def test_prepare_kqd_execution_keeps_branch_path_without_local_resources() -> None:
    plan = _prepare(
        branch=True,
        sector=True,
        resolve_operator=lambda _hamiltonian: (_ for _ in ()).throw(
            AssertionError("branch execution must not resolve a dense matrix")
        ),
        build_action=lambda _hamiltonian: (_ for _ in ()).throw(
            AssertionError("branch execution must not build a sector action")
        ),
    )

    assert plan.operator is None
    assert plan.sector_action is None
    assert plan.dimension == 8
    assert plan.time_evolution_backend == "branch"
    assert plan.selection_reason == "large_aer_problem_requires_branch_estimator"
