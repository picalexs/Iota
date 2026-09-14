"""Direct tests for QSE result and completion-payload helpers."""

from typing import Any

import numpy as np
import pytest

from worker.chemistry.algorithms.qse.results import (
    build_qse_completion_payload,
    build_qse_result,
    emit_qse_completion,
)


def _payload(*, sector: bool) -> Any:
    return build_qse_completion_payload(
        subspace_dim=3,
        primary_energy=-1.25,
        max_subspace_dim=8,
        reference_method="hf",
        excitation_level="singles",
        regularization=1e-8,
        diagnostics={"overlap_condition": 2.0},
        relative_residual=0.002,
        residual_tolerance=0.01,
        execution_mode="sector_matrix_free" if sector else None,
        sector_dimension=6 if sector else None,
        num_spatial_orbitals=3 if sector else None,
    )


def test_emit_qse_completion_keeps_dense_event_shape() -> None:
    events: list[dict[str, Any]] = []

    emit_qse_completion(events.append, _payload(sector=False))

    assert events == [
        {
            "algorithm": "qse",
            "stage": "completed",
            "step": "solve",
            "iteration": 3,
            "energy": -1.25,
            "completed_iterations": 3,
            "total_iterations": 3,
            "subspace_dim": 3,
            "max_subspace_dim": 8,
            "reference_method": "hf",
            "excitation_level": "singles",
            "regularization": 1e-8,
            "overlap_condition": 2.0,
            "relative_residual": 0.002,
            "residual_tolerance": 0.01,
        }
    ]


def test_emit_qse_completion_adds_sector_metadata() -> None:
    events: list[dict[str, Any]] = []

    emit_qse_completion(events.append, _payload(sector=True))

    assert events[0]["execution_mode"] == "sector_matrix_free"
    assert events[0]["sector_dimension"] == 6
    assert events[0]["num_spatial_orbitals"] == 3


def test_build_qse_result_normalizes_complex_numerical_residues() -> None:
    result = build_qse_result(
        eigenvalues=np.array([-1.25 + 1e-9j, 0.5]),
        basis_rank=2,
        converged=True,
        diagnostics={"overlap_condition": 1.5 + 1e-9j},
        reference_state_energy=-1.0 + 1e-9j,
        residual_diagnostics={
            "ritz_residual_norm": 0.002 + 1e-9j,
            "relative_ritz_residual": 0.001 + 1e-9j,
        },
        residual_tolerance=0.01,
        reference_circuit_artifacts=[],
        excitation_level="singles",
        regularization=1e-8,
    )

    assert result.primary_energy == -1.25
    assert result.eigenvalues == [-1.25, 0.5]
    assert result.overlap_condition == 1.5
    assert result.residual_norm == 0.002
    assert result.relative_residual == 0.001


def test_build_qse_result_rejects_empty_spectrum() -> None:
    with pytest.raises(ValueError, match="no eigenvalues"):
        build_qse_result(
            eigenvalues=np.array([]),
            basis_rank=0,
            converged=False,
            diagnostics={"overlap_condition": 1.0},
            reference_state_energy=-1.0,
            residual_diagnostics={
                "ritz_residual_norm": 0.0,
                "relative_ritz_residual": 0.0,
            },
            residual_tolerance=0.01,
            reference_circuit_artifacts=[],
        )
