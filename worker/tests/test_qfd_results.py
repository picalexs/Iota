"""Direct tests for QFD result and completion-payload helpers."""

from typing import Any

import numpy as np
import pytest

from worker.chemistry.algorithms.qfd.results import (
    build_qfd_completion_payload,
    build_qfd_result,
    emit_qfd_completion,
)


def _completion_payload() -> Any:
    return build_qfd_completion_payload(
        num_time_points=3,
        primary_energy=-1.25,
        filter_eigenvalues=np.array([-1.25, 0.5]),
        diagnostics={
            "overlap_condition": 1.5,
            "overlap_min_eigenvalue": 1.0,
            "stability_state": "stable",
        },
        residual_diagnostics={
            "relative_ritz_residual": 0.002,
            "residual_convergence_threshold": 0.01,
        },
        residual_tolerance=0.01,
        qfd_elapsed=1.23456,
        time_grid_type="linear",
        time_evolution_backend="dense_matrix",
        aer_trotter_steps=None,
        matrix_element_strategy="dense",
    )


def test_build_qfd_completion_payload_preserves_filter_diagnostics() -> None:
    payload = _completion_payload()

    assert payload.num_time_points == 3
    assert payload.min_filter_eigenvalue == -1.25
    assert payload.max_filter_eigenvalue == 0.5
    assert payload.overlap_condition == 1.5
    assert payload.qfd_variant == "qfd_chemistry_forward"
    assert payload.wall_seconds == 1.2346


def test_emit_qfd_completion_writes_canonical_event() -> None:
    events: list[dict[str, Any]] = []

    emit_qfd_completion(events.append, _completion_payload())

    assert events == [
        {
            "algorithm": "qfd",
            "stage": "completed",
            "step": "solve",
            "iteration": 3,
            "energy": -1.25,
            "diagnostic_energy": None,
            "energy_state": "reportable",
            "convergence_iteration": 3,
            "completed_iterations": 3,
            "total_iterations": 3,
            "time_grid_type": "linear",
            "qfd_variant": "qfd_chemistry_forward",
            "time_evolution_backend": "dense_matrix",
            "aer_trotter_steps": None,
            "min_filter_eigenvalue": -1.25,
            "max_filter_eigenvalue": 0.5,
            "overlap_condition": 1.5,
            "stability_state": "stable",
            "relative_residual": 0.002,
            "residual_tolerance": 0.01,
            "termination_reason": "converged",
            "projected_solver_converged": True,
            "scientific_converged": None,
            "matrix_element_strategy": "dense",
            "wall_seconds": 1.2346,
        }
    ]


def test_build_qfd_result_normalizes_values_and_merges_diagnostics() -> None:
    result = build_qfd_result(
        filter_eigenvalues=np.array([-1.25, 0.5]),
        raw_filter_eigenvalues=np.array([-1.2, 0.6]),
        num_time_points=3,
        conditioning_summary={"overlap_condition": 1.5},
        residual_diagnostics={
            "relative_ritz_residual": 0.002,
            "residual_convergence_threshold": 0.01,
        },
        diagnostics={
            "stability_state": "stable",
            "overlap_condition": 1.5,
            "overlap_min_eigenvalue": 1.0,
        },
        converged=True,
        matrix_element_summary={"matrix_element_strategy": "dense"},
    )

    assert result.primary_energy == -1.25
    assert result.filter_eigenvalues == [-1.25, 0.5]
    assert result.raw_filter_eigenvalues == [-1.2, 0.6]
    assert result.conditioning_summary == {
        "overlap_condition": 1.5,
        "relative_ritz_residual": 0.002,
        "residual_convergence_threshold": 0.01,
        "termination_reason": "converged",
    }
    assert result.matrix_element_summary["matrix_element_strategy"] == "dense"


def test_build_qfd_result_rejects_empty_spectrum() -> None:
    with pytest.raises(ValueError, match="no filter eigenvalues"):
        build_qfd_result(
            filter_eigenvalues=np.array([]),
            raw_filter_eigenvalues=np.array([]),
            num_time_points=0,
            conditioning_summary={},
            residual_diagnostics={"relative_ritz_residual": 0.0},
            diagnostics={},
            converged=False,
        )
