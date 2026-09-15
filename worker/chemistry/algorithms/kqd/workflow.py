"""KQD solver implementation for worker execution."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import numpy as np

from worker.chemistry.algorithms.kqd.basis import (
    build_krylov_basis,
    build_sector_krylov_basis,
    dense_krylov_partial_energy,
    emit_dense_krylov_progress,
    emit_sector_krylov_progress,
    evolve_dense_krylov_state,
    prepare_dense_krylov_spectrum,
    sector_krylov_partial_energy,
)
from worker.chemistry.algorithms.kqd.circuit_artifacts import (
    build_kqd_circuit_artifacts,
    build_representative_kqd_circuit,
)
from worker.chemistry.algorithms.kqd.config import KQDConfig, resolve_kqd_config
from worker.chemistry.algorithms.kqd.execution import (
    KQDExecutionPlan,
    prepare_kqd_execution,
)
from worker.chemistry.algorithms.kqd.results import (
    build_kqd_completion_payload,
    build_kqd_result,
    emit_kqd_completion,
)
from worker.chemistry.circuit_artifacts import (
    build_hf_reference_circuit,
    prepare_hf_reference_bits,
    serialize_circuit_artifact,
)
from worker.chemistry.eigensolver import (
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
)
from worker.chemistry.overlap import build_overlap_matrix
from worker.chemistry.progress import ProgressCallback
from worker.chemistry.projected_energy import generalized_projected_ground_energy
from worker.chemistry.projected_execution import (
    ProjectedExecutionPolicy,
    backend_label,
    can_use_sector_action,
    num_qubits,
    num_spatial_orbitals,
    should_use_branch_matrix_elements,
    validate_branch_estimator_feasibility,
)
from worker.chemistry.projected_subspace import (
    projected_convergence_reason,
    projected_matrix_converged,
    solve_action_subspace,
)
from worker.chemistry.reference_descriptor import build_reference_descriptor
from worker.chemistry.reference_states import build_hf_reference_state_with_source
from worker.chemistry.sector_basis import hartree_fock_sector_state
from worker.chemistry.solver_utils import resolve_algorithm_config
from worker.chemistry.state_vectors import normalize_state_vector
from worker.chemistry.time_evolution import (
    aer_pauli_time_evolution_state,
    exact_time_evolution_state_from_spectrum,
    prepare_exact_time_evolution,
    trotterized_time_evolution_state,
)
from worker.chemistry.types import KQDResult

logger = logging.getLogger(__name__)


# Re-export private names for existing solver tests and importers.
_num_qubits = num_qubits
_num_spatial_orbitals = num_spatial_orbitals
_can_use_sector_action = can_use_sector_action
_should_use_branch_matrix_elements = should_use_branch_matrix_elements
_backend_label = backend_label
_normalize_krylov_reference_state = normalize_state_vector


_KQDExecutionPlan = KQDExecutionPlan


@dataclass(frozen=True)
class _KQDSolveData:
    """Projected solve outputs shared across KQD execution paths."""

    projected_hamiltonian: np.ndarray
    overlap: np.ndarray
    basis_rank: int
    ritz_values: np.ndarray | None
    raw_ritz_values: np.ndarray | None
    diagnostics: dict[str, Any] | None
    residual_diagnostics: dict[str, float]
    matrix_element_summary: dict[str, Any]


def _build_kqd_circuit_artifacts(
    *,
    hamiltonian: object,
    time_step: float,
    trotter_steps: int,
    evolution_method: str,
    use_branch_matrix_elements: bool,
) -> list[dict[str, Any]]:
    """Keep the legacy KQD artifact helper import-compatible."""
    return build_kqd_circuit_artifacts(
        hamiltonian=hamiltonian,
        time_step=time_step,
        trotter_steps=trotter_steps,
        evolution_method=evolution_method,
        use_branch_matrix_elements=use_branch_matrix_elements,
        build_hf_reference_circuit_fn=build_hf_reference_circuit,
        build_representative_circuit_fn=_build_representative_kqd_circuit,
        serialize_circuit_artifact_fn=serialize_circuit_artifact,
    )


def _build_representative_kqd_circuit(
    *,
    hamiltonian: object,
    time_step: float,
    trotter_steps: int,
    evolution_method: str,
    use_branch_matrix_elements: bool,
) -> Any | None:
    """Keep the legacy KQD circuit helper import-compatible."""
    return build_representative_kqd_circuit(
        hamiltonian=hamiltonian,
        time_step=time_step,
        trotter_steps=trotter_steps,
        evolution_method=evolution_method,
        use_branch_matrix_elements=use_branch_matrix_elements,
        build_hf_reference_circuit_fn=build_hf_reference_circuit,
        prepare_hf_reference_bits_fn=prepare_hf_reference_bits,
        num_qubits_fn=_num_qubits,
    )


def _validate_branch_estimator_feasibility(
    hamiltonian: object, backend_context: Any | None
) -> None:
    validate_branch_estimator_feasibility(
        hamiltonian,
        backend_context,
        algorithm="kqd",
    )


def _build_krylov_basis(
    hamiltonian: object,
    operator_matrix: np.ndarray,
    reference_state: np.ndarray,
    *,
    target_rank: int,
    evolution_method: str,
    time_step: float,
    trotter_steps: int,
    progress_callback: ProgressCallback | None,
    backend_context: Any | None = None,
) -> list[np.ndarray]:
    """Keep the legacy dense KQD basis helper import-compatible."""
    return build_krylov_basis(
        hamiltonian,
        operator_matrix,
        reference_state,
        target_rank=target_rank,
        evolution_method=evolution_method,
        time_step=time_step,
        trotter_steps=trotter_steps,
        progress_callback=progress_callback,
        backend_context=backend_context,
        normalize_reference_fn=_normalize_krylov_reference_state,
        prepare_spectrum_fn=_prepare_dense_krylov_spectrum,
        evolve_state_fn=_evolve_dense_krylov_state,
        partial_energy_fn=_dense_krylov_partial_energy,
        emit_progress_fn=_emit_dense_krylov_progress,
    )


def _build_sector_krylov_basis(
    action: HamiltonianAction,
    reference_state: np.ndarray,
    *,
    target_rank: int,
    evolution_method: str,
    time_step: float,
    trotter_steps: int,
    progress_callback: ProgressCallback | None,
) -> list[np.ndarray]:
    """Keep the legacy sector KQD basis helper import-compatible."""
    return build_sector_krylov_basis(
        action,
        reference_state,
        target_rank=target_rank,
        evolution_method=evolution_method,
        time_step=time_step,
        trotter_steps=trotter_steps,
        progress_callback=progress_callback,
        normalize_reference_fn=_normalize_krylov_reference_state,
        partial_energy_fn=_sector_krylov_partial_energy,
        emit_progress_fn=_emit_sector_krylov_progress,
    )


def _prepare_dense_krylov_spectrum(
    *,
    operator_matrix: np.ndarray,
    reference: np.ndarray,
    evolution_method: str,
    use_aer: bool,
) -> tuple[np.ndarray | None, np.ndarray | None, np.ndarray | None]:
    """Keep the legacy dense-spectrum helper import-compatible."""
    return prepare_dense_krylov_spectrum(
        operator_matrix=operator_matrix,
        reference=reference,
        evolution_method=evolution_method,
        use_aer=use_aer,
        prepare_exact_time_evolution_fn=prepare_exact_time_evolution,
    )


def _evolve_dense_krylov_state(
    *,
    hamiltonian: object,
    operator_matrix: np.ndarray,
    reference: np.ndarray,
    time_point: float,
    evolution_method: str,
    use_aer: bool,
    trotter_steps: int,
    eigenvalues: np.ndarray | None,
    eigenvectors: np.ndarray | None,
    reference_projection: np.ndarray | None,
    backend_context: Any | None,
) -> np.ndarray:
    """Keep the legacy dense evolution helper import-compatible."""
    return evolve_dense_krylov_state(
        hamiltonian=hamiltonian,
        operator_matrix=operator_matrix,
        reference=reference,
        time_point=time_point,
        evolution_method=evolution_method,
        use_aer=use_aer,
        trotter_steps=trotter_steps,
        eigenvalues=eigenvalues,
        eigenvectors=eigenvectors,
        reference_projection=reference_projection,
        backend_context=backend_context,
        aer_time_evolution_fn=aer_pauli_time_evolution_state,
        exact_time_evolution_fn=exact_time_evolution_state_from_spectrum,
        trotterized_time_evolution_fn=trotterized_time_evolution_state,
    )


def _dense_krylov_partial_energy(
    operator_matrix: np.ndarray,
    basis: list[np.ndarray],
) -> float | None:
    """Keep the legacy dense partial-energy helper import-compatible."""
    return dense_krylov_partial_energy(
        operator_matrix,
        basis,
        projected_ground_energy_fn=generalized_projected_ground_energy,
        overlap_builder=build_overlap_matrix,
        eigensolver=solve_generalized_eigenproblem,
    )


def _sector_krylov_partial_energy(
    action: HamiltonianAction,
    basis: list[np.ndarray],
) -> float | None:
    """Keep the legacy sector partial-energy helper import-compatible."""
    return sector_krylov_partial_energy(
        action,
        basis,
        overlap_builder=build_overlap_matrix,
        eigensolver=solve_generalized_eigenproblem,
    )


def _emit_dense_krylov_progress(
    *,
    progress_callback: ProgressCallback | None,
    iteration: int,
    completed_iterations: int,
    total_iterations: int,
    partial_ground: float | None,
    candidate_norm: float,
    evolution_method: str,
    time_point: float,
    time_step: float,
    trotter_steps: int,
    use_aer: bool,
) -> None:
    """Keep the legacy dense progress helper import-compatible."""
    emit_dense_krylov_progress(
        progress_callback=progress_callback,
        iteration=iteration,
        completed_iterations=completed_iterations,
        total_iterations=total_iterations,
        partial_ground=partial_ground,
        candidate_norm=candidate_norm,
        evolution_method=evolution_method,
        time_point=time_point,
        time_step=time_step,
        trotter_steps=trotter_steps,
        use_aer=use_aer,
    )


def _emit_sector_krylov_progress(
    *,
    progress_callback: ProgressCallback | None,
    iteration: int,
    completed_iterations: int,
    total_iterations: int,
    partial_ground: float | None,
    candidate_norm: float,
    evolution_method: str,
    time_point: float,
    time_step: float,
    trotter_steps: int,
    sector_dimension: int,
    implemented_evolution_method: str = "sector_expm_multiply",
) -> None:
    """Keep the legacy sector progress helper import-compatible."""
    emit_sector_krylov_progress(
        progress_callback=progress_callback,
        iteration=iteration,
        completed_iterations=completed_iterations,
        total_iterations=total_iterations,
        partial_ground=partial_ground,
        candidate_norm=candidate_norm,
        evolution_method=evolution_method,
        time_point=time_point,
        time_step=time_step,
        trotter_steps=trotter_steps,
        sector_dimension=sector_dimension,
        implemented_evolution_method=implemented_evolution_method,
    )


def _prepare_kqd_execution(
    *,
    hamiltonian: object,
    backend: object | None,
    backend_context: Any | None,
    execution_policy: ProjectedExecutionPolicy | None = None,
) -> _KQDExecutionPlan:
    """Resolve the KQD execution path and base operator resources."""
    return prepare_kqd_execution(
        hamiltonian=hamiltonian,
        backend=backend,
        backend_context=backend_context,
        should_use_branch_matrix_elements_fn=_should_use_branch_matrix_elements,
        can_use_sector_action_fn=_can_use_sector_action,
        build_hamiltonian_action_fn=build_hamiltonian_action,
        resolve_operator_matrix_fn=resolve_operator_matrix,
        num_qubits_fn=_num_qubits,
        backend_label_fn=_backend_label,
        execution_policy=execution_policy,
    )


_KQDConfig = KQDConfig
_KRYLOV_BASIS_INDEX_CONVENTION = "k=0..krylov_dim-1"
_resolve_kqd_config = resolve_kqd_config


def _solve_kqd_branch_path(
    *,
    hamiltonian: object,
    backend: object | None,
    kqd_config: _KQDConfig,
    progress_callback: ProgressCallback | None,
    backend_context: Any | None,
) -> _KQDSolveData:
    """Build projected KQD matrices from branch-estimator matrix elements."""
    if backend is None:
        raise ValueError("KQD branch matrix-element execution requires an Estimator backend")
    if kqd_config.evolution_method != "trotter":
        raise ValueError(
            "KQD branch matrix-element execution supports evolution_method='trotter' only"
        )
    _validate_branch_estimator_feasibility(hamiltonian, backend_context)
    time_points = [float(step * kqd_config.time_step) for step in range(kqd_config.krylov_dim)]
    estimate = estimate_projected_matrices_with_branch_estimator(
        hamiltonian=hamiltonian,
        estimator=backend,
        time_points=time_points,
        trotter_steps=kqd_config.trotter_steps,
        algorithm="kqd",
        backend_context=backend_context,
        progress_callback=progress_callback,
    )
    projected_hamiltonian = estimate.projected_hamiltonian
    stabilized = solve_stabilized_generalized_eigenproblem(
        projected_hamiltonian,
        estimate.overlap,
        max_standard_error=estimate.summary.get("max_standard_error"),
    )
    if stabilized.eigenvalues.size == 0:
        raise ValueError("KQD projected solve produced no Ritz values")
    stabilized.diagnostics["diagnostic_only"] = not projected_matrix_converged(
        stabilized.diagnostics
    )
    if stabilized.diagnostics["diagnostic_only"]:
        stabilized.diagnostics["diagnostic_reason"] = projected_convergence_reason(
            stabilized.diagnostics,
            relative_residual=float(
                stabilized.diagnostics.get("relative_projected_ritz_residual", float("inf"))
            ),
            residual_tolerance=kqd_config.residual_tolerance,
        )
    basis_rank = projected_hamiltonian.shape[0]
    reference_state, reference_source = build_hf_reference_state_with_source(
        hamiltonian,
        fallback_dim=2 ** max(0, _num_qubits(hamiltonian)),
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
    return _KQDSolveData(
        projected_hamiltonian=projected_hamiltonian,
        overlap=estimate.overlap,
        basis_rank=basis_rank,
        ritz_values=stabilized.eigenvalues,
        raw_ritz_values=stabilized.raw_eigenvalues,
        diagnostics=stabilized.diagnostics,
        residual_diagnostics={
            "ritz_residual_norm": float(stabilized.diagnostics["projected_ritz_residual_norm"]),
            "relative_ritz_residual": float(
                stabilized.diagnostics["relative_projected_ritz_residual"]
            ),
            "residual_convergence_threshold": kqd_config.residual_tolerance,
            "basis_numerical_rank": float(basis_rank),
        },
        matrix_element_summary={
            **estimate.summary,
            "requested_evolution_method": kqd_config.evolution_method,
            "implemented_evolution_method": "pauli_lie_trotter",
            "time_step": kqd_config.time_step,
            "trotter_steps": kqd_config.trotter_steps,
            "projected_dimension": basis_rank,
            "projected_matrix_element_count": 2 * basis_rank * basis_rank,
            "residual_kind": "projected_generalized_eigenpair",
            "basis_index_convention": _KRYLOV_BASIS_INDEX_CONVENTION,
            "reference_state_source": reference_source,
            "reference_descriptor": reference_descriptor,
        },
    )


def _solve_kqd_sector_path(
    *,
    sector_action: HamiltonianAction,
    kqd_config: _KQDConfig,
    progress_callback: ProgressCallback | None,
) -> _KQDSolveData:
    """Solve KQD in the fixed-particle sector."""
    reference_state = hartree_fock_sector_state(sector_action.norb, sector_action.nelec)
    basis = _build_sector_krylov_basis(
        sector_action,
        reference_state,
        target_rank=kqd_config.krylov_dim,
        evolution_method=kqd_config.evolution_method,
        time_step=kqd_config.time_step,
        trotter_steps=kqd_config.trotter_steps,
        progress_callback=progress_callback,
    )
    basis_matrix = np.column_stack(basis)
    reference_energy = sector_action.expectation(reference_state)
    residual = sector_action.matvec(reference_state) - reference_energy * reference_state
    reference_descriptor = build_reference_descriptor(
        state=reference_state,
        reference_source="hartree_fock",
        preparation_path="sector_basis",
        execution_mode=(
            "sector_expm_multiply"
            if kqd_config.evolution_method == "exact"
            else "sector_diagonal_residual_trotter"
        ),
        target_sector={"alpha": sector_action.nelec[0], "beta": sector_action.nelec[1]},
        reference_energy=reference_energy,
        variance=float(np.vdot(residual, residual).real),
        ansatz_name="hartree_fock",
    )
    ritz_values, _, diagnostics, residual_diagnostics, _ = solve_action_subspace(
        sector_action,
        basis_matrix,
        residual_tolerance=kqd_config.residual_tolerance,
    )
    return _KQDSolveData(
        projected_hamiltonian=sector_action.project(basis_matrix),
        overlap=build_overlap_matrix(basis),
        basis_rank=basis_matrix.shape[1],
        ritz_values=ritz_values,
        raw_ritz_values=ritz_values,
        diagnostics=diagnostics,
        residual_diagnostics=residual_diagnostics,
        matrix_element_summary={
            "matrix_element_strategy": "sector_matrix_free",
            "requested_evolution_method": kqd_config.evolution_method,
            "implemented_evolution_method": (
                "sector_expm_multiply"
                if kqd_config.evolution_method == "exact"
                else "sector_diagonal_residual_trotter"
            ),
            "sector_dimension": sector_action.dimension,
            "num_spatial_orbitals": sector_action.norb,
            "projected_dimension": basis_matrix.shape[1],
            "projected_matrix_element_count": 2 * basis_matrix.shape[1] ** 2,
            "time_step": kqd_config.time_step,
            "trotter_steps": kqd_config.trotter_steps,
            "residual_kind": "projected_generalized_eigenpair",
            "time_points": [
                float(step * kqd_config.time_step) for step in range(kqd_config.krylov_dim)
            ],
            "basis_index_convention": _KRYLOV_BASIS_INDEX_CONVENTION,
            "reference_state_source": "hartree_fock_sector",
            "reference_descriptor": reference_descriptor,
        },
    )


def _solve_kqd_dense_path(
    *,
    hamiltonian: object,
    operator: np.ndarray,
    kqd_config: _KQDConfig,
    progress_callback: ProgressCallback | None,
    backend_context: Any | None,
) -> _KQDSolveData:
    """Solve KQD through dense Krylov basis construction."""
    reference_state, reference_source = build_hf_reference_state_with_source(
        hamiltonian,
        fallback_dim=operator.shape[0],
    )
    basis = _build_krylov_basis(
        hamiltonian,
        operator,
        reference_state,
        target_rank=kqd_config.krylov_dim,
        evolution_method=kqd_config.evolution_method,
        time_step=kqd_config.time_step,
        trotter_steps=kqd_config.trotter_steps,
        progress_callback=progress_callback,
        backend_context=backend_context,
    )
    basis_matrix = np.column_stack(basis)
    reference_energy = float(np.real(np.vdot(reference_state, operator @ reference_state)))
    residual = operator @ reference_state - reference_energy * reference_state
    implemented_evolution_method = (
        "aer_pauli_lie_trotter"
        if getattr(backend_context, "backend_target", None) == "aer_simulator"
        else "exact_matrix_evolution"
    )
    reference_descriptor = build_reference_descriptor(
        state=reference_state,
        reference_source=reference_source,
        preparation_path=(
            "hartree_fock_determinant"
            if reference_source == "hartree_fock"
            else "computational_basis_fallback"
        ),
        execution_mode=implemented_evolution_method,
        target_sector={
            "alpha": getattr(hamiltonian, "num_electrons_alpha", None),
            "beta": getattr(hamiltonian, "num_electrons_beta", None),
        },
        reference_energy=reference_energy,
        variance=float(np.vdot(residual, residual).real),
        backend_target=getattr(backend_context, "backend_target", None),
        ansatz_name="hartree_fock",
    )
    return _KQDSolveData(
        projected_hamiltonian=basis_matrix.conj().T @ operator @ basis_matrix,
        overlap=build_overlap_matrix(basis),
        basis_rank=basis_matrix.shape[1],
        ritz_values=None,
        raw_ritz_values=None,
        diagnostics=None,
        residual_diagnostics=projected_ritz_diagnostics(
            operator,
            basis_matrix,
            residual_tolerance=kqd_config.residual_tolerance,
        ),
        matrix_element_summary={
            "matrix_element_strategy": "dense_classical",
            "requested_evolution_method": kqd_config.evolution_method,
            "implemented_evolution_method": implemented_evolution_method,
            "projected_dimension": basis_matrix.shape[1],
            "projected_matrix_element_count": 2 * basis_matrix.shape[1] ** 2,
            "time_step": kqd_config.time_step,
            "trotter_steps": kqd_config.trotter_steps,
            "residual_kind": "projected_generalized_eigenpair",
            "time_points": [
                float(step * kqd_config.time_step) for step in range(kqd_config.krylov_dim)
            ],
            "basis_index_convention": _KRYLOV_BASIS_INDEX_CONVENTION,
            "reference_state_source": reference_source,
            "reference_descriptor": reference_descriptor,
        },
    )


def _run_kqd_solve_path(
    *,
    plan: _KQDExecutionPlan,
    hamiltonian: object,
    backend: object | None,
    kqd_config: _KQDConfig,
    progress_callback: ProgressCallback | None,
    backend_context: Any | None,
) -> _KQDSolveData:
    """Dispatch the prepared KQD execution path."""
    if plan.use_branch_matrix_elements:
        return _solve_kqd_branch_path(
            hamiltonian=hamiltonian,
            backend=backend,
            kqd_config=kqd_config,
            progress_callback=progress_callback,
            backend_context=backend_context,
        )
    if plan.sector_action is not None:
        return _solve_kqd_sector_path(
            sector_action=plan.sector_action,
            kqd_config=kqd_config,
            progress_callback=progress_callback,
        )
    if plan.operator is None:
        raise RuntimeError("KQD dense operator was not prepared")
    return _solve_kqd_dense_path(
        hamiltonian=hamiltonian,
        operator=plan.operator,
        kqd_config=kqd_config,
        progress_callback=progress_callback,
        backend_context=backend_context,
    )


def _emit_kqd_completion(
    *,
    progress_callback: ProgressCallback | None,
    solve_data: _KQDSolveData,
    ritz_values: np.ndarray,
    diagnostics: dict[str, Any],
    matrix_element_summary: dict[str, Any],
    kqd_config: _KQDConfig,
    primary_energy: float,
    time_evolution_backend: str,
    kqd_elapsed: float,
) -> None:
    """Emit the KQD completed progress payload."""
    emit_kqd_completion(
        progress_callback,
        build_kqd_completion_payload(
            solve_data=solve_data,
            ritz_values=ritz_values,
            diagnostics=diagnostics,
            matrix_element_summary=matrix_element_summary,
            kqd_config=kqd_config,
            primary_energy=primary_energy,
            time_evolution_backend=time_evolution_backend,
            kqd_elapsed=kqd_elapsed,
        ),
    )


def run_kqd(
    *,
    hamiltonian: object,
    backend: object | None,
    config: dict[str, Any],
    progress_callback: ProgressCallback | None = None,
    backend_context: Any | None = None,
    execution_policy: ProjectedExecutionPolicy | None = None,
) -> KQDResult:
    """Run a deterministic Krylov subspace diagonalization workflow."""
    resolved = resolve_algorithm_config(config, "kqd")
    kqd_config = _resolve_kqd_config(resolved)

    t_start = time.monotonic()
    plan = _prepare_kqd_execution(
        hamiltonian=hamiltonian,
        backend=backend,
        backend_context=backend_context,
        execution_policy=execution_policy,
    )
    logger.info(
        "KQD setup: hilbert_dim=%d krylov_dim=%d evolution=%s time_step=%.4f "
        "trotter_steps=%d time_evolution_backend=%s",
        plan.dimension,
        kqd_config.krylov_dim,
        kqd_config.evolution_method,
        kqd_config.time_step,
        kqd_config.trotter_steps,
        plan.time_evolution_backend,
    )

    solve_started = time.monotonic()
    solve_data = _run_kqd_solve_path(
        plan=plan,
        hamiltonian=hamiltonian,
        backend=backend,
        kqd_config=kqd_config,
        progress_callback=progress_callback,
        backend_context=backend_context,
    )

    ritz_values = solve_data.ritz_values
    diagnostics = solve_data.diagnostics
    if ritz_values is None or diagnostics is None:
        ritz_values, diagnostics = solve_exact_generalized_eigenproblem(
            solve_data.projected_hamiltonian,
            solve_data.overlap,
        )
        raw_ritz_values = ritz_values
    else:
        raw_ritz_values = (
            solve_data.raw_ritz_values if solve_data.raw_ritz_values is not None else ritz_values
        )
    matrix_element_summary = dict(solve_data.matrix_element_summary)
    matrix_element_summary["execution_selection_reason"] = plan.selection_reason
    matrix_element_summary.setdefault("projected_dimension", solve_data.basis_rank)
    matrix_element_summary.setdefault(
        "projected_matrix_element_count", 2 * solve_data.basis_rank**2
    )
    matrix_element_summary["timing_breakdown"] = {
        "preparation_seconds": solve_started - t_start,
        "solve_and_postprocess_seconds": time.monotonic() - solve_started,
    }
    if plan.use_branch_matrix_elements:
        projected_residual = solve_data.residual_diagnostics["relative_ritz_residual"]
        converged = _projected_matrix_converged(diagnostics) and (
            projected_residual <= kqd_config.residual_tolerance
        )
        matrix_element_summary["convergence_basis"] = (
            "projected_overlap_condition_and_generalized_residual"
        )
    else:
        converged = _projected_matrix_converged(diagnostics) and (
            solve_data.residual_diagnostics["relative_ritz_residual"]
            <= kqd_config.residual_tolerance
        )

    if ritz_values.size == 0:
        raise ValueError("KQD projected solve produced no Ritz values")
    primary_energy = float(ritz_values[0])
    kqd_elapsed = time.monotonic() - t_start
    matrix_element_summary["timing_breakdown"]["total_seconds"] = kqd_elapsed

    logger.info(
        "KQD finished: energy=%.8f converged=%s basis_rank=%d krylov_dim=%d "
        "relative_residual=%.2e elapsed=%.3fs",
        primary_energy,
        converged,
        solve_data.basis_rank,
        kqd_config.krylov_dim,
        solve_data.residual_diagnostics["relative_ritz_residual"],
        kqd_elapsed,
    )

    _emit_kqd_completion(
        progress_callback=progress_callback,
        solve_data=solve_data,
        ritz_values=ritz_values,
        diagnostics=diagnostics,
        matrix_element_summary=matrix_element_summary,
        kqd_config=kqd_config,
        primary_energy=primary_energy,
        time_evolution_backend=plan.time_evolution_backend,
        kqd_elapsed=kqd_elapsed,
    )

    return build_kqd_result(
        solve_data=solve_data,
        ritz_values=ritz_values,
        raw_ritz_values=raw_ritz_values,
        diagnostics=diagnostics,
        matrix_element_summary=matrix_element_summary,
        converged=converged,
        kqd_config=kqd_config,
        sector_dimension=(plan.sector_action.dimension if plan.sector_action is not None else None),
        circuit_artifacts=_build_kqd_circuit_artifacts(
            hamiltonian=hamiltonian,
            time_step=kqd_config.time_step,
            trotter_steps=kqd_config.trotter_steps,
            evolution_method=kqd_config.evolution_method,
            use_branch_matrix_elements=plan.use_branch_matrix_elements,
        ),
    )


_projected_matrix_converged = projected_matrix_converged
