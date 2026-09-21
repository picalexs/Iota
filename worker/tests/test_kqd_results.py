"""Direct tests for KQD result and completion-payload helpers."""

from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from worker.chemistry.algorithms.kqd.results import (
    build_kqd_completion_payload,
    build_kqd_result,
    emit_kqd_completion,
)


def _solve_data() -> SimpleNamespace:
    return SimpleNamespace(
        overlap=np.eye(2),
        basis_rank=2,
        residual_diagnostics={
            "relative_ritz_residual": 0.001,
            "ritz_residual_norm": 0.002,
        },
    )


def _config() -> SimpleNamespace:
    return SimpleNamespace(
        krylov_dim=4,
        evolution_method="exact",
        time_step=0.2,
        trotter_steps=3,
        residual_tolerance=0.01,
    )


def test_build_kqd_completion_payload_preserves_completion_fields() -> None:
    payload = build_kqd_completion_payload(
        solve_data=_solve_data(),
        ritz_values=np.array([-1.5, 0.25]),
        diagnostics={"overlap_condition": 1.2, "stability_state": "stable"},
        matrix_element_summary={"matrix_element_strategy": "dense"},
        kqd_config=_config(),
        primary_energy=-1.5,
        time_evolution_backend="exact_matrix",
        kqd_elapsed=1.23456,
    )

    assert payload.basis_rank == 2
    assert payload.min_ritz == -1.5
    assert payload.max_ritz == 0.25
    assert payload.time_evolution_backend == "exact_matrix"
    assert payload.wall_seconds == 1.2346


def test_emit_kqd_completion_writes_canonical_event() -> None:
    events: list[dict[str, Any]] = []
    payload = build_kqd_completion_payload(
        solve_data=_solve_data(),
        ritz_values=np.array([-1.5]),
        diagnostics={
            "overlap_condition": 1.2,
            "overlap_min_eigenvalue": 1.0,
            "stability_state": "stable",
        },
        matrix_element_summary={},
        kqd_config=_config(),
        primary_energy=-1.5,
        time_evolution_backend="exact_matrix",
        kqd_elapsed=0.1,
    )

    emit_kqd_completion(events.append, payload)

    assert events == [
        {
            "algorithm": "kqd",
            "stage": "completed",
            "step": "solve",
            "iteration": 2,
            "energy": -1.5,
            "diagnostic_energy": None,
            "energy_state": "reportable",
            "convergence_iteration": 2,
            "completed_iterations": 2,
            "total_iterations": 2,
            "krylov_dim": 4,
            "basis_rank": 2,
            "evolution_method": "exact",
            "time_evolution_backend": "exact_matrix",
            "time_step": 0.2,
            "trotter_steps": 3,
            "min_ritz": -1.5,
            "max_ritz": -1.5,
            "overlap_condition": 1.2,
            "stability_state": "stable",
            "relative_residual": 0.001,
            "residual_tolerance": 0.01,
            "termination_reason": "converged",
            "projected_solver_converged": True,
            "scientific_converged": None,
            "matrix_element_strategy": None,
            "wall_seconds": 0.1,
        }
    ]


def test_build_kqd_result_adds_overlap_and_sector_metrics() -> None:
    result = build_kqd_result(
        solve_data=_solve_data(),
        ritz_values=np.array([-1.5, 0.25]),
        raw_ritz_values=np.array([-1.4, 0.3]),
        diagnostics={
            "stability_state": "stable",
            "overlap_condition": 1.2,
            "overlap_min_eigenvalue": 1.0,
        },
        matrix_element_summary={"matrix_element_strategy": "sector_matrix_free"},
        converged=True,
        kqd_config=_config(),
        sector_dimension=6,
        circuit_artifacts=[{"artifact_id": "kqd.evolution"}],
    )

    assert result.primary_energy == -1.5
    assert result.primary_iterations == 2
    assert result.raw_ritz_values == [-1.4, 0.3]
    assert result.orthogonality_metrics["basis_rank"] == 2.0
    assert result.orthogonality_metrics["sector_dimension"] == 6.0
    assert result.stability_summary == {
        "stability_state": "stable",
        "overlap_condition": 1.2,
        "overlap_min_eigenvalue": 1.0,
        "diagnostic_only": False,
        "energy_state": "reportable",
        "termination_reason": "converged",
    }


def test_build_kqd_result_rejects_empty_spectrum() -> None:
    with pytest.raises(ValueError, match="no Ritz values"):
        build_kqd_result(
            solve_data=_solve_data(),
            ritz_values=np.array([]),
            raw_ritz_values=np.array([]),
            diagnostics={},
            matrix_element_summary={},
            converged=False,
            kqd_config=_config(),
            sector_dimension=None,
            circuit_artifacts=[],
        )
