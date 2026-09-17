"""QSE dense and fixed-sector execution paths for the algorithm package."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

from worker.chemistry.algorithms.qse.basis import (
    ExcitationSpec,
    build_basis_selection_summary,
)
from worker.chemistry.algorithms.qse.sector import (
    DOMINANT_DETERMINANT_SELECTION_THRESHOLD,
    dominant_sector_occupations,
)
from worker.chemistry.hamiltonian_action import HamiltonianAction
from worker.chemistry.progress import ProgressCallback
from worker.chemistry.projected_subspace import (
    projected_convergence_reason,
    projected_matrix_converged,
)

ReferenceResolver = Callable[..., tuple[str, np.ndarray, list[dict[str, Any]]]]
BasisBuilder = Callable[..., list[np.ndarray]]
ActionSubspaceSolver = Callable[..., tuple[np.ndarray, Any, dict[str, Any], dict[str, float], Any]]
GeneralizedEigensystemSolver = Callable[..., tuple[np.ndarray, np.ndarray, dict[str, Any]]]
RealScalar = Callable[..., float]


def _record_regularization_scope(
    diagnostics: dict[str, Any],
    *,
    requested_regularization: float,
    scope: str,
    final_metric_diagonal_shift: float,
    may_change_reported_energy: bool,
) -> None:
    """Record how the requested QSE regularization affects this execution path."""
    diagnostics.update(
        {
            "requested_regularization": float(requested_regularization),
            "regularization_scope": scope,
            "final_metric_diagonal_shift": float(final_metric_diagonal_shift),
            "regularization_may_change_reported_energy": may_change_reported_energy,
        }
    )


def _basis_selection_observer(
) -> tuple[Callable[[ExcitationSpec], None], list[ExcitationSpec]]:
    """Capture accepted specifications without creating progress events."""
    selected_specs: list[ExcitationSpec] = []

    def observe(spec: ExcitationSpec) -> None:
        selected_specs.append(spec)

    return observe, selected_specs


@dataclass(frozen=True)
class QSEExecutionOutcome:
    """Numerical output shared by dense and fixed-sector QSE paths."""

    eigenvalues: np.ndarray
    basis_rank: int
    diagnostics: dict[str, Any]
    residual_diagnostics: dict[str, float]
    reference_state_energy: float
    converged: bool
    reference_method: str
    reference_circuit_artifacts: list[dict[str, Any]]
    execution_mode: str | None = None
    sector_dimension: int | None = None
    num_spatial_orbitals: int | None = None
    reference_state: np.ndarray | None = None
    reference_variance: float | None = None


def execute_sector_qse(
    *,
    hamiltonian: object,
    action: HamiltonianAction,
    resolved_config: dict[str, Any],
    excitation_level: str,
    target_rank: int,
    overlap_threshold: float,
    regularization: float,
    residual_tolerance: float,
    progress_callback: ProgressCallback | None,
    resolve_reference_state_fn: ReferenceResolver,
    build_excitation_basis_fn: BasisBuilder,
    solve_action_subspace_fn: ActionSubspaceSolver,
    real_scalar_fn: RealScalar,
) -> QSEExecutionOutcome:
    """Execute the QSE fixed-particle-sector path."""
    reference_method, reference_state, reference_artifacts = resolve_reference_state_fn(
        hamiltonian=hamiltonian,
        action=action,
        resolved_config=resolved_config,
    )
    basis_selection_callback, selected_specs = _basis_selection_observer()
    basis = build_excitation_basis_fn(
        reference_state,
        action,
        excitation_level=excitation_level,
        target_rank=target_rank,
        overlap_threshold=overlap_threshold,
        residual_tolerance=residual_tolerance,
        progress_callback=progress_callback,
        selection_callback=basis_selection_callback,
    )
    basis_matrix = np.column_stack(basis)
    eigenvalues, _, diagnostics, residual_diagnostics, _ = solve_action_subspace_fn(
        action,
        basis_matrix,
        residual_tolerance=residual_tolerance,
        regularization=0.0,
    )
    diagnostics["regularization"] = 0.0
    dominant_reference_used = (
        dominant_sector_occupations(reference_state, action) is not None
    )
    diagnostics["basis_selection"] = build_basis_selection_summary(
        selected_specs,
        candidate_selection_policy=(
            "reference_coupling_descending"
            if dominant_reference_used
            else "full_fermionic_generator_order"
        ),
        excitation_level=excitation_level,
        dimension_cap=target_rank,
        actual_dimension=int(basis_matrix.shape[1]),
        policy_details={
            "dominant_determinant_reference_used": dominant_reference_used,
            "dominant_determinant_probability_threshold": (
                DOMINANT_DETERMINANT_SELECTION_THRESHOLD
            ),
        },
    )
    _record_regularization_scope(
        diagnostics,
        requested_regularization=regularization,
        scope="not_applied_in_fixed_sector_path",
        final_metric_diagonal_shift=0.0,
        may_change_reported_energy=False,
    )
    relative_residual = residual_diagnostics["relative_ritz_residual"]
    reference_energy = real_scalar_fn(
        action.expectation(reference_state),
        label="QSE reference state energy",
    )
    matvec = getattr(action, "matvec", None)
    reference_variance = None
    if callable(matvec):
        residual = matvec(reference_state) - reference_energy * reference_state
        reference_variance = float(np.vdot(residual, residual).real)
    return QSEExecutionOutcome(
        eigenvalues=eigenvalues,
        basis_rank=basis_matrix.shape[1],
        diagnostics=diagnostics,
        residual_diagnostics=residual_diagnostics,
        reference_state_energy=reference_energy,
        converged=projected_matrix_converged(diagnostics)
        and relative_residual <= residual_tolerance,
        reference_method=reference_method,
        reference_circuit_artifacts=reference_artifacts,
        execution_mode="sector_matrix_free",
        sector_dimension=action.dimension,
        num_spatial_orbitals=action.norb,
        reference_state=reference_state,
        reference_variance=reference_variance,
    )


def execute_dense_qse(
    *,
    hamiltonian: object,
    backend: object,
    operator: np.ndarray,
    resolved_config: dict[str, Any],
    excitation_level: str,
    target_rank: int,
    overlap_threshold: float,
    regularization: float,
    residual_tolerance: float,
    progress_callback: ProgressCallback | None,
    resolve_reference_state_fn: ReferenceResolver,
    build_excitation_basis_fn: BasisBuilder,
    build_overlap_matrix_fn: Callable[[list[np.ndarray]], np.ndarray],
    solve_generalized_eigensystem_fn: GeneralizedEigensystemSolver,
    real_scalar_fn: RealScalar,
    execution_mode: str = "dense_exact_emulation",
) -> QSEExecutionOutcome:
    """Execute the dense QSE path with an exact projected eigensystem solve."""
    reference_method, reference_state, reference_artifacts = resolve_reference_state_fn(
        hamiltonian=hamiltonian,
        backend=backend,
        operator_matrix=operator,
        resolved_config=resolved_config,
        progress_callback=progress_callback,
    )
    basis_selection_callback, selected_specs = _basis_selection_observer()
    basis = build_excitation_basis_fn(
        reference_state,
        operator,
        excitation_level=excitation_level,
        target_rank=target_rank,
        overlap_threshold=overlap_threshold,
        regularization=regularization,
        progress_callback=progress_callback,
        selection_callback=basis_selection_callback,
    )
    basis_matrix = np.column_stack(basis)
    overlap = build_overlap_matrix_fn(basis)
    projected_hamiltonian = basis_matrix.conj().T @ operator @ basis_matrix
    eigenvalues, eigenvectors, diagnostics = solve_generalized_eigensystem_fn(
        projected_hamiltonian,
        overlap,
    )
    if eigenvalues.size:
        ritz_state = basis_matrix @ eigenvectors[:, 0]
        full_residual = operator @ ritz_state - eigenvalues[0] * ritz_state
        full_residual_norm = float(np.linalg.norm(full_residual))
        full_operator_state_norm = float(np.linalg.norm(operator @ ritz_state))
        full_relative_residual = full_residual_norm / max(
            1.0,
            abs(float(eigenvalues[0])),
            full_operator_state_norm,
        )
    else:
        full_residual_norm = float("nan")
        full_relative_residual = float("nan")
    generalized_residual_norm = diagnostics.get("generalized_residual_norm")
    relative_generalized_residual = diagnostics.get("relative_generalized_residual")
    metric_normalization_error = diagnostics.get("metric_normalization_error")
    residual_diagnostics = {
        "ritz_energy": float(eigenvalues[0]) if eigenvalues.size else float("nan"),
        "ritz_residual_norm": full_residual_norm,
        "relative_ritz_residual": full_relative_residual,
        "generalized_residual_norm": (
            float(generalized_residual_norm)
            if generalized_residual_norm is not None
            else float("nan")
        ),
        "relative_generalized_residual": (
            float(relative_generalized_residual)
            if relative_generalized_residual is not None
            else float("nan")
        ),
        "metric_normalization_error": (
            float(metric_normalization_error)
            if metric_normalization_error is not None
            else float("nan")
        ),
    }
    diagnostics["regularization"] = 0.0
    diagnostics["basis_selection"] = build_basis_selection_summary(
        selected_specs,
        candidate_selection_policy="fermionic_generator_order",
        excitation_level=excitation_level,
        dimension_cap=target_rank,
        actual_dimension=int(basis_matrix.shape[1]),
    )
    _record_regularization_scope(
        diagnostics,
        requested_regularization=regularization,
        scope="basis_progress_estimates_only",
        final_metric_diagonal_shift=0.0,
        may_change_reported_energy=False,
    )
    relative_residual = residual_diagnostics["relative_ritz_residual"]
    reference_energy = real_scalar_fn(
        np.vdot(reference_state, operator @ reference_state),
        label="QSE reference state energy",
    )
    residual = operator @ reference_state - reference_energy * reference_state
    diagnostics = {
        **diagnostics,
        "reference_state_execution": "exact_emulation",
        "matrix_element_source": "exact_operator_and_statevectors",
    }
    return QSEExecutionOutcome(
        eigenvalues=eigenvalues,
        basis_rank=basis_matrix.shape[1],
        diagnostics=diagnostics,
        residual_diagnostics=residual_diagnostics,
        reference_state_energy=reference_energy,
        converged=projected_matrix_converged(diagnostics)
        and relative_residual <= residual_tolerance,
        reference_method=reference_method,
        reference_circuit_artifacts=reference_artifacts,
        execution_mode=execution_mode,
        reference_state=reference_state,
        reference_variance=float(np.vdot(residual, residual).real),
    )


def execute_measured_qse(
    *,
    hamiltonian: object,
    estimator: object,
    resolved_config: dict[str, Any],
    excitation_level: str,
    target_rank: int,
    regularization: float,
    residual_tolerance: float,
    progress_callback: ProgressCallback | None,
    backend_context: Any,
    **execution_dependencies: Any,
) -> QSEExecutionOutcome:
    """Execute measured-matrix-element QSE for noisy or hardware targets.

    Assembles projected H/S matrices from Pauli expectation values measured on a
    single reference state, then solves the stabilized generalized eigenproblem.
    A rank-reduced (``stabilized``) solve becomes a non-converged diagnostic; a
    zero-rank or non-finite solve raises a hard failure inside the solver.
    """
    estimate_matrices_fn = execution_dependencies["estimate_matrices_fn"]
    solve_stabilized_fn = execution_dependencies["solve_stabilized_fn"]
    diagnostic_reportable_fn = execution_dependencies["diagnostic_reportable_fn"]
    build_reference_descriptor_fn = execution_dependencies["build_reference_descriptor_fn"]
    build_hf_reference_state_fn = execution_dependencies["build_hf_reference_state_fn"]

    estimate = estimate_matrices_fn(
        hamiltonian=hamiltonian,
        estimator=estimator,
        excitation_level=excitation_level,
        max_dimension=target_rank,
        backend_context=backend_context,
        progress_callback=progress_callback,
    )
    projected_hamiltonian = estimate.projected_hamiltonian
    overlap = estimate.overlap
    basis_rank = projected_hamiltonian.shape[0]

    stabilized = solve_stabilized_fn(
        projected_hamiltonian,
        overlap,
        regularization=regularization,
        max_standard_error=estimate.summary.get("max_overlap_standard_error"),
    )
    if stabilized.eigenvalues.size == 0:
        raise ValueError("Measured QSE projected solve produced no eigenvalues")

    diagnostics = dict(stabilized.diagnostics)
    reportable = diagnostic_reportable_fn(diagnostics)
    is_stable = projected_matrix_converged(diagnostics)
    diagnostics["diagnostic_only"] = True
    relative_residual = float(
        diagnostics.get("relative_projected_ritz_residual", float("inf"))
    )
    if not is_stable:
        diagnostics["diagnostic_reason"] = projected_convergence_reason(
            diagnostics,
            relative_residual=relative_residual,
            residual_tolerance=residual_tolerance,
        )
    else:
        diagnostics["diagnostic_reason"] = "measured_matrix_elements_diagnostic"
    # Measured QSE is a diagnostic construction: never converged, never
    # chemically accurate. Convergence stays False even when a stable subspace
    # remains, because the measured metric only yields a diagnostic energy.
    del reportable

    residual_diagnostics = {
        "ritz_energy": float(stabilized.eigenvalues[0]),
        "ritz_residual_norm": float(diagnostics["projected_ritz_residual_norm"]),
        "relative_ritz_residual": relative_residual,
        "residual_convergence_threshold": float(residual_tolerance),
        "basis_numerical_rank": float(diagnostics.get("retained_rank", basis_rank) or basis_rank),
    }

    reference_state, reference_source = build_hf_reference_state_fn(
        hamiltonian,
        fallback_dim=2**basis_rank,
    )
    reference_descriptor = build_reference_descriptor_fn(
        state=reference_state,
        reference_source=reference_source,
        preparation_path="measured_reference_circuit",
        execution_mode="measured_matrix_elements",
        target_sector={
            "alpha": getattr(hamiltonian, "num_electrons_alpha", None),
            "beta": getattr(hamiltonian, "num_electrons_beta", None),
        },
        backend_target=getattr(backend_context, "backend_target", None),
        ansatz_name="hartree_fock",
    )
    diagnostics = {
        **diagnostics,
        "reference_state_execution": "measured_backend_estimator",
        "matrix_element_source": "measured_pauli_expectations",
        "matrix_element_strategy": "branch_estimator",
        "measured_matrix_element_construction": (
            "fixed_pool_qse_nonorthogonal_eigensolver"
        ),
        "reference_descriptor": reference_descriptor,
        "backend_target": getattr(backend_context, "backend_target", None),
        **estimate.summary,
    }
    _record_regularization_scope(
        diagnostics,
        requested_regularization=regularization,
        scope="raw_metric_spectrum_and_overlap_mode_cutoff_floor",
        final_metric_diagonal_shift=0.0,
        may_change_reported_energy=True,
    )
    return QSEExecutionOutcome(
        eigenvalues=stabilized.eigenvalues,
        basis_rank=basis_rank,
        diagnostics=diagnostics,
        residual_diagnostics=residual_diagnostics,
        reference_state_energy=float(np.real(projected_hamiltonian[0, 0])),
        converged=False,
        reference_method=str(resolved_config.get("reference_method", "hf")).lower(),
        reference_circuit_artifacts=[],
        execution_mode="measured_matrix_elements",
        reference_state=reference_state,
        reference_variance=None,
    )


__all__ = [
    "QSEExecutionOutcome",
    "execute_dense_qse",
    "execute_measured_qse",
    "execute_sector_qse",
]
