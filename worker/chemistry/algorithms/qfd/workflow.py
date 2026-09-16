"""QFD solver implementation for worker execution."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, replace
from typing import Any

import numpy as np

from worker.chemistry.algorithms.qfd.config import QFDConfig, resolve_qfd_config
from worker.chemistry.algorithms.qfd.execution import (
    QFDExecutionPlan,
    prepare_qfd_execution,
)
from worker.chemistry.algorithms.qfd.grid import (
    build_qfd_time_grid,
    qfd_grid_metadata,
    qfd_spectral_width_bound,
    resolve_qfd_symmetric_kappa,
)
from worker.chemistry.algorithms.qfd.results import (
    build_qfd_completion_payload,
    build_qfd_result,
    emit_qfd_completion,
)
from worker.chemistry.algorithms.qfd.states import (
    build_dense_qfd_states,
    build_sector_qfd_states,
    dense_qfd_partial_energy,
    emit_dense_qfd_progress,
    evolve_dense_qfd_state,
)
from worker.chemistry.eigensolver import (
    build_hf_reference_state,
    projected_ritz_diagnostics,
    resolve_operator_matrix,
    solve_exact_generalized_eigenproblem,
    solve_generalized_eigenproblem,
    solve_stabilized_generalized_eigenproblem,
)
from worker.chemistry.hamiltonian_action import (
    HamiltonianAction,
    build_hamiltonian_action,
)
from worker.chemistry.matrix_elements import (
    estimate_projected_matrices_with_branch_estimator,
    hardware_projected_dimension_limit,
)
from worker.chemistry.overlap import build_overlap_matrix, overlap_metrics
from worker.chemistry.progress import ProgressCallback
from worker.chemistry.projected_energy import generalized_projected_ground_energy
from worker.chemistry.projected_execution import (
    ProjectedExecutionPolicy,
    backend_label,
    can_use_sector_action,
    num_qubits,
    should_use_branch_matrix_elements,
    validate_branch_estimator_feasibility,
)
from worker.chemistry.projected_subspace import (
    projected_convergence_reason,
    projected_matrix_converged,
)
from worker.chemistry.reference_descriptor import build_reference_descriptor
from worker.chemistry.reference_states import hf_reference_source
from worker.chemistry.sector_basis import hartree_fock_sector_state
from worker.chemistry.solver_utils import resolve_algorithm_config
from worker.chemistry.state_vectors import normalize_state_vector
from worker.chemistry.time_evolution import (
    aer_pauli_time_evolution_state,
    build_time_grid,
    exact_time_evolution_state_from_spectrum,
    prepare_exact_time_evolution,
)
from worker.chemistry.types import QFDResult

logger = logging.getLogger(__name__)
_NO_QFD_FILTER_EIGENVALUES = "QFD projected solve produced no filter eigenvalues"


def _build_hf_reference_state_with_source(
    hamiltonian: object,
    *,
    fallback_dim: int | None = None,
) -> tuple[np.ndarray, str]:
    """Build the HF reference and preserve its source metadata."""
    return build_hf_reference_state(
        hamiltonian,
        fallback_dim=fallback_dim,
    ), hf_reference_source(hamiltonian)


@dataclass(frozen=True)
class _QFDDenseEvolutionContext:
    """Dense QFD state-evolution inputs shared across the time grid."""

    hamiltonian: object
    operator: np.ndarray
    reference_state: np.ndarray
    use_aer: bool
    trotter_steps: int
    eigenvalues: np.ndarray | None
    eigenvectors: np.ndarray | None
    reference_projection: np.ndarray | None
    backend_context: Any | None


def _validate_branch_estimator_feasibility(
    hamiltonian: object, backend_context: Any | None
) -> None:
    validate_branch_estimator_feasibility(
        hamiltonian,
        backend_context,
        algorithm="qfd",
    )


def _build_sector_qfd_states(
    action: HamiltonianAction,
    reference_state: np.ndarray,
    time_grid: np.ndarray,
    *,
    max_time: float,
    time_grid_type: str,
    progress_callback: ProgressCallback | None,
) -> list[np.ndarray]:
    """Adapt sector-state inputs to the state builder."""
    return build_sector_qfd_states(
        action,
        reference_state,
        time_grid,
        max_time=max_time,
        time_grid_type=time_grid_type,
        progress_callback=progress_callback,
        normalize_state_fn=normalize_state_vector,
        overlap_builder_fn=build_overlap_matrix,
        eigensolver_fn=solve_generalized_eigenproblem,
    )


def _prepare_qfd_execution(
    *,
    hamiltonian: object,
    backend: object | None,
    backend_context: Any | None,
    execution_policy: ProjectedExecutionPolicy | None = None,
) -> QFDExecutionPlan:
    """Resolve the QFD execution path and any reusable dense evolution data."""
    return prepare_qfd_execution(
        hamiltonian=hamiltonian,
        backend=backend,
        backend_context=backend_context,
        should_use_branch_matrix_elements_fn=should_use_branch_matrix_elements,
        can_use_sector_action_fn=can_use_sector_action,
        build_hamiltonian_action_fn=build_hamiltonian_action,
        resolve_operator_matrix_fn=resolve_operator_matrix,
        num_qubits_fn=num_qubits,
        backend_label_fn=backend_label,
        prepare_dense_spectrum_fn=_prepare_dense_qfd_spectrum,
        execution_policy=execution_policy,
    )


def _prepare_dense_qfd_spectrum(
    *,
    hamiltonian: object,
    operator: np.ndarray | None,
    use_aer: bool,
    use_branch_matrix_elements: bool,
    sector_action: HamiltonianAction | None,
) -> tuple[np.ndarray | None, np.ndarray | None, np.ndarray | None]:
    """Prepare the exact dense spectrum when QFD will reuse it across time points."""
    if use_branch_matrix_elements or use_aer or sector_action is not None:
        return None, None, None
    if operator is None:
        raise RuntimeError("QFD dense operator was not prepared")
    reference_state, _reference_source = _build_hf_reference_state_with_source(
        hamiltonian,
        fallback_dim=operator.shape[0],
    )
    eigenvalues, eigenvectors = prepare_exact_time_evolution(operator)
    return eigenvalues, eigenvectors, eigenvectors.conj().T @ reference_state


def _solve_qfd_branch_path(
    *,
    hamiltonian: object,
    backend: object | None,
    plan: QFDExecutionPlan,
    time_grid: np.ndarray,
    num_time_points: int,
    max_time: float,
    time_grid_type: str,
    trotter_steps: int,
    residual_tolerance: float,
    t_start: float,
    progress_callback: ProgressCallback | None,
    backend_context: Any | None,
    grid_metadata: dict[str, Any],
) -> QFDResult:
    """Solve QFD through branch-estimator projected matrix elements."""
    if backend is None:
        raise ValueError("QFD branch matrix-element execution requires an Estimator backend")
    _validate_branch_estimator_feasibility(hamiltonian, backend_context)
    estimate = estimate_projected_matrices_with_branch_estimator(
        hamiltonian=hamiltonian,
        estimator=backend,
        time_points=[float(value) for value in time_grid],
        trotter_steps=trotter_steps,
        algorithm="qfd",
        backend_context=backend_context,
        progress_callback=progress_callback,
    )
    projected_hamiltonian = estimate.projected_hamiltonian
    overlap = estimate.overlap
    reference_state, reference_source = _build_hf_reference_state_with_source(
        hamiltonian,
        fallback_dim=2 ** max(0, num_qubits(hamiltonian)),
    )
    reference_descriptor = build_reference_descriptor(
        state=reference_state,
        reference_source=reference_source,
        preparation_path="branch_circuit",
        execution_mode="trotterized_branch_estimator",
        target_sector={
            "alpha": getattr(hamiltonian, "num_electrons_alpha", None),
            "beta": getattr(hamiltonian, "num_electrons_beta", None),
        },
        backend_target=getattr(backend_context, "backend_target", None),
        ansatz_name="hartree_fock",
    )
    matrix_element_summary = {
        **estimate.summary,
        **grid_metadata,
        "time_grid_type": time_grid_type,
        "implemented_evolution_method": "pauli_lie_trotter",
        "projected_dimension": num_time_points,
        "projected_matrix_element_count": 2 * num_time_points**2,
        "reference_state_source": reference_source,
        "reference_descriptor": reference_descriptor,
    }
    projected_solve_started = time.monotonic()
    stabilized = solve_stabilized_generalized_eigenproblem(
        projected_hamiltonian,
        overlap,
        max_standard_error=estimate.summary.get("max_standard_error"),
    )
    if stabilized.eigenvalues.size == 0:
        raise ValueError(_NO_QFD_FILTER_EIGENVALUES)
    stabilized.diagnostics["diagnostic_only"] = not projected_matrix_converged(
        stabilized.diagnostics
    )
    if stabilized.diagnostics["diagnostic_only"]:
        stabilized.diagnostics["diagnostic_reason"] = projected_convergence_reason(
            stabilized.diagnostics,
            relative_residual=float(
                stabilized.diagnostics.get("relative_projected_ritz_residual", float("inf"))
            ),
            residual_tolerance=residual_tolerance,
        )
    filter_eigenvalues = stabilized.eigenvalues
    diagnostics = stabilized.diagnostics
    residual_diagnostics = {
        "ritz_residual_norm": float(stabilized.diagnostics["projected_ritz_residual_norm"]),
        "relative_ritz_residual": float(
            stabilized.diagnostics["relative_projected_ritz_residual"]
        ),
        "residual_convergence_threshold": residual_tolerance,
        "basis_numerical_rank": float(num_time_points),
    }
    conditioning_summary = {
        **overlap_metrics(overlap),
        **diagnostics,
        **grid_metadata,
        "time_points": float(num_time_points),
        "max_time": float(max_time),
    }
    projected_solver_converged = projected_matrix_converged(diagnostics) and (
        residual_diagnostics["relative_ritz_residual"] <= residual_tolerance
    )
    matrix_element_summary["projected_solver_converged"] = bool(projected_solver_converged)
    matrix_element_summary["convergence_basis"] = (
        "projected_solver_only_full_space_residual_unavailable"
    )
    matrix_element_summary["residual_kind"] = "projected_gevp_equation"
    converged = False
    qfd_elapsed = time.monotonic() - t_start
    matrix_element_summary["timing_breakdown"] = {
        "matrix_element_estimation_seconds": projected_solve_started - t_start,
        "projected_solve_seconds": time.monotonic() - projected_solve_started,
        "total_seconds": qfd_elapsed,
    }
    if filter_eigenvalues.size == 0:
        raise ValueError(_NO_QFD_FILTER_EIGENVALUES)
    primary_energy = float(filter_eigenvalues[0])
    _emit_qfd_completion(
        progress_callback=progress_callback,
        num_time_points=num_time_points,
        primary_energy=primary_energy,
        filter_eigenvalues=filter_eigenvalues,
        diagnostics=diagnostics,
        residual_diagnostics=residual_diagnostics,
        residual_tolerance=residual_tolerance,
        qfd_elapsed=qfd_elapsed,
        time_grid_type=time_grid_type,
        time_evolution_backend=plan.time_evolution_backend,
        aer_trotter_steps=trotter_steps if plan.use_aer else None,
        matrix_element_strategy=matrix_element_summary.get("matrix_element_strategy"),
        qfd_variant=str(grid_metadata["qfd_variant"]),
    )
    return build_qfd_result(
        filter_eigenvalues=filter_eigenvalues,
        raw_filter_eigenvalues=stabilized.raw_eigenvalues,
        num_time_points=num_time_points,
        conditioning_summary=conditioning_summary,
        residual_diagnostics=residual_diagnostics,
        diagnostics=diagnostics,
        converged=converged,
        matrix_element_summary=matrix_element_summary,
    )


def _solve_qfd_sector_path(
    *,
    sector_action: HamiltonianAction,
    time_grid: np.ndarray,
    max_time: float,
    time_grid_type: str,
    residual_tolerance: float,
    t_start: float,
    progress_callback: ProgressCallback | None,
    time_evolution_backend: str,
    grid_metadata: dict[str, Any],
) -> QFDResult:
    """Solve QFD in the fixed-particle sector without dense operators."""
    reference_state = hartree_fock_sector_state(sector_action.norb, sector_action.nelec)
    states = _build_sector_qfd_states(
        sector_action,
        reference_state,
        time_grid,
        max_time=max_time,
        time_grid_type=time_grid_type,
        progress_callback=progress_callback,
    )
    states_matrix = np.column_stack(states)
    overlap = build_overlap_matrix(states)
    projected_hamiltonian = sector_action.project(states_matrix)
    reference_energy = sector_action.expectation(reference_state)
    residual = sector_action.matvec(reference_state) - reference_energy * reference_state
    reference_descriptor = build_reference_descriptor(
        state=reference_state,
        reference_source="hartree_fock",
        preparation_path="sector_basis",
        execution_mode="sector_expm_multiply",
        target_sector={"alpha": sector_action.nelec[0], "beta": sector_action.nelec[1]},
        reference_energy=reference_energy,
        variance=float(np.vdot(residual, residual).real),
        ansatz_name="hartree_fock",
    )
    projected_solve_started = time.monotonic()
    filter_eigenvalues, diagnostics = solve_exact_generalized_eigenproblem(
        projected_hamiltonian,
        overlap,
    )
    conditioning_summary = {
        **overlap_metrics(overlap),
        **diagnostics,
        **grid_metadata,
        "time_points": float(len(states)),
        "max_time": float(max_time),
        "sector_dimension": float(sector_action.dimension),
    }
    residual_diagnostics, _ = sector_action.residual_diagnostics(
        states_matrix,
        residual_tolerance=residual_tolerance,
    )
    converged = projected_matrix_converged(diagnostics) and (
        residual_diagnostics["relative_ritz_residual"] <= residual_tolerance
    )
    matrix_element_summary = {
        "matrix_element_strategy": "sector_matrix_free",
        **grid_metadata,
        "time_grid_type": time_grid_type,
        "implemented_evolution_method": "sector_expm_multiply",
        "sector_dimension": sector_action.dimension,
        "num_spatial_orbitals": sector_action.norb,
        "projected_dimension": len(states),
        "projected_matrix_element_count": 2 * len(states) ** 2,
        "reference_state_source": "hartree_fock",
        "reference_descriptor": reference_descriptor,
        "residual_kind": "projected_generalized_eigenpair",
        "convergence_basis": "projected_generalized_residual",
    }
    if filter_eigenvalues.size == 0:
        raise ValueError(_NO_QFD_FILTER_EIGENVALUES)
    primary_energy = float(filter_eigenvalues[0])
    qfd_elapsed = time.monotonic() - t_start
    matrix_element_summary["timing_breakdown"] = {
        "state_evolution_seconds": projected_solve_started - t_start,
        "projected_solve_seconds": time.monotonic() - projected_solve_started,
        "total_seconds": qfd_elapsed,
    }
    logger.info(
        "QFD finished: energy=%.8f converged=%s time_points=%d "
        "relative_residual=%.2e elapsed=%.3fs",
        primary_energy,
        converged,
        len(states),
        residual_diagnostics["relative_ritz_residual"],
        qfd_elapsed,
    )
    _emit_qfd_completion(
        progress_callback=progress_callback,
        num_time_points=len(states),
        primary_energy=primary_energy,
        filter_eigenvalues=filter_eigenvalues,
        diagnostics=diagnostics,
        residual_diagnostics=residual_diagnostics,
        residual_tolerance=residual_tolerance,
        qfd_elapsed=qfd_elapsed,
        time_grid_type=time_grid_type,
        time_evolution_backend=time_evolution_backend,
        matrix_element_strategy=matrix_element_summary.get("matrix_element_strategy"),
        qfd_variant=str(grid_metadata["qfd_variant"]),
    )
    return build_qfd_result(
        filter_eigenvalues=filter_eigenvalues,
        raw_filter_eigenvalues=filter_eigenvalues,
        num_time_points=len(states),
        conditioning_summary=conditioning_summary,
        residual_diagnostics=residual_diagnostics,
        diagnostics=diagnostics,
        converged=converged,
        matrix_element_summary=matrix_element_summary,
    )


def _build_dense_qfd_states(
    *,
    evolution_context: _QFDDenseEvolutionContext,
    time_grid: np.ndarray,
    num_time_points: int,
    max_time: float,
    time_grid_type: str,
    progress_callback: ProgressCallback | None,
) -> list[np.ndarray]:
    """Adapt dense-state inputs to the state builder."""
    return build_dense_qfd_states(
        evolution_context=evolution_context,
        time_grid=time_grid,
        num_time_points=num_time_points,
        max_time=max_time,
        time_grid_type=time_grid_type,
        progress_callback=progress_callback,
        evolve_state_fn=_evolve_dense_qfd_state,
        partial_energy_fn=_dense_qfd_partial_energy,
        emit_progress_fn=_emit_dense_qfd_progress,
    )


def _evolve_dense_qfd_state(
    *,
    evolution_context: _QFDDenseEvolutionContext,
    time_point: float,
) -> np.ndarray:
    """Adapt dense evolution inputs to the state builder."""
    return evolve_dense_qfd_state(
        evolution_context=evolution_context,
        time_point=time_point,
        aer_time_evolution_fn=aer_pauli_time_evolution_state,
        exact_time_evolution_fn=exact_time_evolution_state_from_spectrum,
    )


def _dense_qfd_partial_energy(
    operator: np.ndarray,
    dense_states: list[np.ndarray],
) -> float | None:
    """Adapt dense partial-energy inputs to the state builder."""
    return dense_qfd_partial_energy(
        operator,
        dense_states,
        projected_ground_energy_fn=generalized_projected_ground_energy,
        overlap_builder_fn=build_overlap_matrix,
        eigensolver_fn=solve_generalized_eigenproblem,
    )


def _emit_dense_qfd_progress(
    *,
    progress_callback: ProgressCallback | None,
    index: int,
    total_iterations: int,
    partial_energy: float | None,
    time_point: float,
    max_time: float,
    time_grid_type: str,
    use_aer: bool,
    trotter_steps: int,
) -> None:
    """Adapt dense progress inputs to the state builder."""
    emit_dense_qfd_progress(
        progress_callback=progress_callback,
        index=index,
        total_iterations=total_iterations,
        partial_energy=partial_energy,
        time_point=time_point,
        max_time=max_time,
        time_grid_type=time_grid_type,
        use_aer=use_aer,
        trotter_steps=trotter_steps,
    )


def _solve_qfd_dense_path(
    *,
    hamiltonian: object,
    operator: np.ndarray,
    plan: QFDExecutionPlan,
    time_grid: np.ndarray,
    num_time_points: int,
    max_time: float,
    time_grid_type: str,
    trotter_steps: int,
    residual_tolerance: float,
    t_start: float,
    progress_callback: ProgressCallback | None,
    backend_context: Any | None,
    grid_metadata: dict[str, Any],
) -> QFDResult:
    """Solve QFD through dense state propagation and projected diagonalization."""
    reference_state, reference_source = _build_hf_reference_state_with_source(
        hamiltonian,
        fallback_dim=operator.shape[0],
    )
    dense_states = _build_dense_qfd_states(
        evolution_context=_QFDDenseEvolutionContext(
            hamiltonian=hamiltonian,
            operator=operator,
            reference_state=reference_state,
            use_aer=plan.use_aer,
            trotter_steps=trotter_steps,
            eigenvalues=plan.eigenvalues,
            eigenvectors=plan.eigenvectors,
            reference_projection=plan.reference_projection,
            backend_context=backend_context,
        ),
        time_grid=time_grid,
        num_time_points=num_time_points,
        max_time=max_time,
        time_grid_type=time_grid_type,
        progress_callback=progress_callback,
    )
    states_matrix = np.column_stack(dense_states)
    overlap = build_overlap_matrix(dense_states)
    projected_hamiltonian = states_matrix.conj().T @ operator @ states_matrix
    projected_solve_started = time.monotonic()
    filter_eigenvalues, diagnostics = solve_exact_generalized_eigenproblem(
        projected_hamiltonian,
        overlap,
    )
    conditioning_summary = {
        **overlap_metrics(overlap),
        **diagnostics,
        **grid_metadata,
        "time_points": float(num_time_points),
        "max_time": float(max_time),
    }
    residual_diagnostics = projected_ritz_diagnostics(
        operator,
        states_matrix,
        residual_tolerance=residual_tolerance,
    )
    converged = projected_matrix_converged(diagnostics) and (
        residual_diagnostics["relative_ritz_residual"] <= residual_tolerance
    )
    matrix_element_summary = {
        "matrix_element_strategy": "dense_classical",
        "reference_state_source": reference_source,
        **grid_metadata,
        "time_grid_type": time_grid_type,
        "implemented_evolution_method": (
            "aer_pauli_lie_trotter" if plan.use_aer else "exact_matrix_evolution"
        ),
        "projected_dimension": len(dense_states),
        "projected_matrix_element_count": 2 * len(dense_states) ** 2,
        "residual_kind": "projected_generalized_eigenpair",
        "convergence_basis": "projected_generalized_residual",
    }
    reference_energy = float(np.real(np.vdot(reference_state, operator @ reference_state)))
    residual = operator @ reference_state - reference_energy * reference_state
    matrix_element_summary["reference_descriptor"] = build_reference_descriptor(
        state=reference_state,
        reference_source=reference_source,
        preparation_path=(
            "hartree_fock_determinant"
            if reference_source == "hartree_fock"
            else "computational_basis_fallback"
        ),
        execution_mode=("aer_pauli_lie_trotter" if plan.use_aer else "exact_matrix_evolution"),
        target_sector={
            "alpha": getattr(hamiltonian, "num_electrons_alpha", None),
            "beta": getattr(hamiltonian, "num_electrons_beta", None),
        },
        reference_energy=reference_energy,
        variance=float(np.vdot(residual, residual).real),
        backend_target=getattr(backend_context, "backend_target", None),
        ansatz_name="hartree_fock",
    )
    if filter_eigenvalues.size == 0:
        raise ValueError(_NO_QFD_FILTER_EIGENVALUES)
    primary_energy = float(filter_eigenvalues[0])
    qfd_elapsed = time.monotonic() - t_start
    matrix_element_summary["timing_breakdown"] = {
        "state_evolution_seconds": projected_solve_started - t_start,
        "projected_solve_seconds": time.monotonic() - projected_solve_started,
        "total_seconds": qfd_elapsed,
    }
    logger.info(
        "QFD finished: energy=%.8f converged=%s time_points=%d "
        "relative_residual=%.2e elapsed=%.3fs",
        primary_energy,
        converged,
        num_time_points,
        residual_diagnostics["relative_ritz_residual"],
        qfd_elapsed,
    )
    _emit_qfd_completion(
        progress_callback=progress_callback,
        num_time_points=num_time_points,
        primary_energy=primary_energy,
        filter_eigenvalues=filter_eigenvalues,
        diagnostics=diagnostics,
        residual_diagnostics=residual_diagnostics,
        residual_tolerance=residual_tolerance,
        qfd_elapsed=qfd_elapsed,
        time_grid_type=time_grid_type,
        time_evolution_backend="aer_simulator" if plan.use_aer else "dense_matrix",
        aer_trotter_steps=trotter_steps if plan.use_aer else None,
        qfd_variant=str(grid_metadata["qfd_variant"]),
    )
    return build_qfd_result(
        filter_eigenvalues=filter_eigenvalues,
        raw_filter_eigenvalues=filter_eigenvalues,
        num_time_points=num_time_points,
        conditioning_summary=conditioning_summary,
        residual_diagnostics=residual_diagnostics,
        diagnostics=diagnostics,
        converged=converged,
        matrix_element_summary=matrix_element_summary,
    )


def run_qfd(
    *,
    hamiltonian: object,
    backend: object | None,
    config: dict[str, Any],
    progress_callback: ProgressCallback | None = None,
    backend_context: Any | None = None,
    execution_policy: ProjectedExecutionPolicy | None = None,
) -> QFDResult:
    """Run a deterministic filter-diagonalization workflow."""
    resolved = resolve_algorithm_config(config, "qfd")
    uses_branch_estimator = (
        execution_policy.actual_path == "branch_estimator"
        if execution_policy is not None
        else should_use_branch_matrix_elements(
            hamiltonian=hamiltonian,
            backend=backend,
            backend_context=backend_context,
        )
    )
    qfd_config: QFDConfig = resolve_qfd_config(
        resolved,
        default_num_time_points=7 if uses_branch_estimator else 16,
    )
    if uses_branch_estimator and qfd_config.num_time_points > hardware_projected_dimension_limit():
        raise ValueError(
            "QFD branch matrix-element execution supports at most "
            f"{hardware_projected_dimension_limit()} time points per run"
        )

    t_start = time.monotonic()
    plan = _prepare_qfd_execution(
        hamiltonian=hamiltonian,
        backend=backend,
        backend_context=backend_context,
        execution_policy=execution_policy,
    )
    kappa_diagnostics: dict[str, object] = {}
    if qfd_config.qfd_variant == "qfd_original_symmetric":
        raw_kappa = resolved.get("kappa")
        if raw_kappa is None:
            raw_kappa = resolved.get("spectral_scale")
        spectral_width_bound, bound_source = qfd_spectral_width_bound(
            operator_matrix=plan.operator,
            pauli_hamiltonian=getattr(hamiltonian, "pauli_hamiltonian", None),
            eigenvalues=plan.eigenvalues,
        )
        effective_kappa, kappa_diagnostics = resolve_qfd_symmetric_kappa(
            qfd_config.kappa if raw_kappa is not None else None,
            spectral_width_bound=spectral_width_bound,
            bound_source=bound_source,
        )
        qfd_config = replace(qfd_config, kappa=effective_kappa)
    logger.info(
        "QFD setup: hilbert_dim=%d num_time_points=%d max_time=%.4f grid=%s "
        "trotter_steps=%d time_evolution_backend=%s",
        plan.dimension,
        qfd_config.num_time_points,
        qfd_config.max_time,
        qfd_config.time_grid_type,
        qfd_config.trotter_steps,
        plan.time_evolution_backend,
    )
    if qfd_config.qfd_variant == "qfd_original_symmetric":
        time_grid = build_qfd_time_grid(
            qfd_variant=qfd_config.qfd_variant,
            num_time_points=qfd_config.num_time_points,
            max_time=qfd_config.max_time,
            time_grid_type=qfd_config.time_grid_type,
            kappa=qfd_config.kappa,
        )
    else:
        time_grid = build_time_grid(
            num_time_points=qfd_config.num_time_points,
            max_time=qfd_config.max_time,
            grid_type=qfd_config.time_grid_type,
        )
    grid_metadata = qfd_grid_metadata(
        time_grid,
        qfd_variant=qfd_config.qfd_variant,
        kappa=qfd_config.kappa,
    )
    grid_metadata.update(kappa_diagnostics)
    if plan.use_branch_matrix_elements:
        result = _solve_qfd_branch_path(
            hamiltonian=hamiltonian,
            backend=backend,
            plan=plan,
            time_grid=time_grid,
            num_time_points=qfd_config.num_time_points,
            max_time=qfd_config.max_time,
            time_grid_type=qfd_config.time_grid_type,
            trotter_steps=qfd_config.trotter_steps,
            residual_tolerance=qfd_config.residual_tolerance,
            t_start=t_start,
            progress_callback=progress_callback,
            backend_context=backend_context,
            grid_metadata=grid_metadata,
        )
    elif plan.sector_action is not None:
        result = _solve_qfd_sector_path(
            sector_action=plan.sector_action,
            time_grid=time_grid,
            max_time=qfd_config.max_time,
            time_grid_type=qfd_config.time_grid_type,
            residual_tolerance=qfd_config.residual_tolerance,
            t_start=t_start,
            progress_callback=progress_callback,
            time_evolution_backend=plan.time_evolution_backend,
            grid_metadata=grid_metadata,
        )
    else:
        if plan.operator is None:
            raise RuntimeError("QFD dense operator was not prepared")
        result = _solve_qfd_dense_path(
            hamiltonian=hamiltonian,
            operator=plan.operator,
            plan=plan,
            time_grid=time_grid,
            num_time_points=qfd_config.num_time_points,
            max_time=qfd_config.max_time,
            time_grid_type=qfd_config.time_grid_type,
            trotter_steps=qfd_config.trotter_steps,
            residual_tolerance=qfd_config.residual_tolerance,
            t_start=t_start,
            progress_callback=progress_callback,
            backend_context=backend_context,
            grid_metadata=grid_metadata,
        )
    return replace(
        result,
        matrix_element_summary={
            **result.matrix_element_summary,
            "execution_selection_reason": plan.selection_reason,
        },
    )


def _emit_qfd_completion(
    *,
    progress_callback: ProgressCallback | None,
    num_time_points: int,
    primary_energy: float,
    filter_eigenvalues: np.ndarray,
    diagnostics: dict[str, Any],
    residual_diagnostics: dict[str, float],
    residual_tolerance: float,
    qfd_elapsed: float,
    time_grid_type: str,
    time_evolution_backend: str,
    aer_trotter_steps: int | None = None,
    matrix_element_strategy: Any | None = None,
    qfd_variant: str = "qfd_chemistry_forward",
) -> None:
    emit_qfd_completion(
        progress_callback,
        build_qfd_completion_payload(
            num_time_points=num_time_points,
            primary_energy=primary_energy,
            filter_eigenvalues=filter_eigenvalues,
            diagnostics=diagnostics,
            residual_diagnostics=residual_diagnostics,
            residual_tolerance=residual_tolerance,
            qfd_elapsed=qfd_elapsed,
            time_grid_type=time_grid_type,
            time_evolution_backend=time_evolution_backend,
            aer_trotter_steps=aer_trotter_steps,
            matrix_element_strategy=matrix_element_strategy,
            qfd_variant=qfd_variant,
        ),
    )
