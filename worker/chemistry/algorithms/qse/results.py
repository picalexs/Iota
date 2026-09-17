"""QSE result and completion-payload helpers for the algorithm package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from worker.chemistry.algorithms.qse.basis import real_scalar
from worker.chemistry.progress import ProgressCallback
from worker.chemistry.projected_subspace import projected_convergence_reason
from worker.chemistry.reference_descriptor import build_reference_descriptor
from worker.chemistry.types import QSEResult


@dataclass(frozen=True)
class QSECompletionPayload:
    """Completed QSE progress values."""

    subspace_dim: int
    primary_energy: float
    max_subspace_dim: int
    reference_method: str
    excitation_level: str
    regularization: float
    overlap_condition: float
    relative_residual: float
    residual_tolerance: float
    execution_mode: str | None = None
    sector_dimension: int | None = None
    num_spatial_orbitals: int | None = None


def build_qse_completion_payload(
    *,
    subspace_dim: int,
    primary_energy: float,
    max_subspace_dim: int,
    reference_method: str,
    excitation_level: str,
    regularization: float,
    diagnostics: dict[str, Any],
    relative_residual: float,
    residual_tolerance: float,
    execution_mode: str | None = None,
    sector_dimension: int | None = None,
    num_spatial_orbitals: int | None = None,
) -> QSECompletionPayload:
    """Build the completed QSE progress payload object."""
    return QSECompletionPayload(
        subspace_dim=subspace_dim,
        primary_energy=primary_energy,
        max_subspace_dim=max_subspace_dim,
        reference_method=reference_method,
        excitation_level=excitation_level,
        regularization=regularization,
        overlap_condition=float(diagnostics.get("overlap_condition", 0.0)),
        relative_residual=relative_residual,
        residual_tolerance=residual_tolerance,
        execution_mode=execution_mode,
        sector_dimension=sector_dimension,
        num_spatial_orbitals=num_spatial_orbitals,
    )


def emit_qse_completion(
    progress_callback: ProgressCallback | None,
    payload: QSECompletionPayload,
) -> None:
    """Emit a completed QSE progress event when a callback is configured."""
    if progress_callback is None:
        return
    event: dict[str, Any] = {
        "algorithm": "qse",
        "stage": "completed",
        "step": "solve",
        "iteration": payload.subspace_dim,
        "energy": payload.primary_energy,
        "completed_iterations": payload.subspace_dim,
        "total_iterations": payload.subspace_dim,
        "subspace_dim": payload.subspace_dim,
        "max_subspace_dim": payload.max_subspace_dim,
        "reference_method": payload.reference_method,
        "excitation_level": payload.excitation_level,
        "regularization": payload.regularization,
        "overlap_condition": payload.overlap_condition,
        "relative_residual": payload.relative_residual,
        "residual_tolerance": payload.residual_tolerance,
    }
    if payload.execution_mode is not None:
        event["execution_mode"] = payload.execution_mode
    if payload.sector_dimension is not None:
        event["sector_dimension"] = payload.sector_dimension
    if payload.num_spatial_orbitals is not None:
        event["num_spatial_orbitals"] = payload.num_spatial_orbitals
    progress_callback(event)


def build_qse_result(
    *,
    eigenvalues: np.ndarray,
    basis_rank: int,
    converged: bool,
    diagnostics: dict[str, Any],
    reference_state_energy: float,
    residual_diagnostics: dict[str, float],
    residual_tolerance: float,
    reference_circuit_artifacts: list[dict[str, Any]],
    **reference_data: Any,
) -> QSEResult:
    """Build the public QSE result from completed projected-solve data."""
    reference_method = reference_data.get("reference_method", "unknown")
    execution_mode = reference_data.get("execution_mode")
    excitation_level = reference_data.get("excitation_level", "unknown")
    regularization = reference_data.get("regularization")
    reference_state = reference_data.get("reference_state")
    reference_variance = reference_data.get("reference_variance")
    target_sector = reference_data.get("target_sector")
    normalized_eigenvalues = [
        real_scalar(value, label=f"QSE eigenvalue {index}")
        for index, value in enumerate(eigenvalues)
    ]
    if not normalized_eigenvalues:
        raise ValueError("QSE projected solve produced no eigenvalues")
    relative_residual = residual_diagnostics["relative_ritz_residual"]
    termination_reason = projected_convergence_reason(
        diagnostics,
        relative_residual=relative_residual,
        residual_tolerance=residual_tolerance,
    )
    if execution_mode == "measured_matrix_elements" and not converged:
        termination_reason = "measured_matrix_elements_diagnostic"
    if execution_mode == "measured_matrix_elements":
        matrix_element_summary = {
            "matrix_element_strategy": "branch_estimator",
            "measured_matrix_element_construction": diagnostics.get(
                "measured_matrix_element_construction",
                "fixed_pool_qse_nonorthogonal_eigensolver",
            ),
            "projected_dimension": basis_rank,
            "projected_matrix_element_count": 2 * basis_rank**2,
            "basis_construction_rule": (
                "jordan_wigner_fermionic_excitation_operators"
            ),
            "backend_target": diagnostics.get("backend_target"),
            "max_hamiltonian_standard_error": diagnostics.get(
                "max_hamiltonian_standard_error"
            ),
            "max_overlap_standard_error": diagnostics.get("max_overlap_standard_error"),
            "max_standard_error": diagnostics.get("max_standard_error"),
            "standard_error_units": diagnostics.get("standard_error_units"),
            "max_standard_error_compatibility": diagnostics.get(
                "max_standard_error_compatibility"
            ),
        }
    else:
        matrix_element_summary = {
            "matrix_element_strategy": (
                "sector_matrix_free"
                if execution_mode == "sector_matrix_free"
                else "dense_classical"
            ),
            "projected_dimension": basis_rank,
            "projected_matrix_element_count": 2 * basis_rank**2,
            "basis_construction_rule": "fermionic_excitation_basis",
        }
    basis_selection = diagnostics.get("basis_selection")
    if isinstance(basis_selection, dict):
        matrix_element_summary["basis_selection"] = basis_selection
    if reference_state is not None:
        matrix_element_summary["reference_descriptor"] = build_reference_descriptor(
            state=reference_state,
            reference_source=reference_method,
            preparation_path=(
                "sector_basis"
                if execution_mode == "sector_matrix_free"
                else {
                    "hf": "hartree_fock_determinant",
                    "vqe": "vqe_ansatz",
                    "provided_state": "provided_state_vector",
                }.get(reference_method, "reference_state_resolver")
            ),
            execution_mode=execution_mode or "unspecified",
            target_sector=target_sector,
            reference_energy=float(reference_state_energy),
            variance=reference_variance,
            circuit_metadata=reference_circuit_artifacts,
            ansatz_name=("hartree_fock" if reference_method == "hf" else reference_method),
        )
    conditioning_summary = {
        key: value for key, value in diagnostics.items() if key != "basis_selection"
    }
    conditioning_summary["termination_reason"] = termination_reason
    return QSEResult(
        algorithm="qse",
        primary_energy=normalized_eigenvalues[0],
        primary_iterations=basis_rank,
        converged=converged,
        eigenvalues=normalized_eigenvalues,
        overlap_condition=real_scalar(diagnostics["overlap_condition"], label="QSE overlap"),
        reference_state_energy=real_scalar(
            reference_state_energy,
            label="QSE reference state energy",
        ),
        residual_norm=real_scalar(
            residual_diagnostics["ritz_residual_norm"],
            label="QSE residual norm",
        ),
        relative_residual=real_scalar(relative_residual, label="QSE relative residual"),
        convergence_threshold=residual_tolerance,
        reference_circuit_artifacts=reference_circuit_artifacts,
        reference_method=reference_method,
        execution_mode=execution_mode,
        excitation_level=excitation_level,
        regularization=regularization,
        conditioning_summary=conditioning_summary,
        matrix_element_summary=matrix_element_summary,
    )


__all__ = [
    "QSECompletionPayload",
    "build_qse_completion_payload",
    "build_qse_result",
    "emit_qse_completion",
]
