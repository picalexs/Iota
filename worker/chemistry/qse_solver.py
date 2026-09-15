"""QSE solver implementation for worker execution."""

from __future__ import annotations

import logging
import time
from typing import Any

import numpy as np

from worker.chemistry.algorithms.qse.basis import (
    accept_basis_candidate,
    build_excitation_basis,
    build_sector_excitation_basis,
    real_scalar,
)
from worker.chemistry.algorithms.qse.config import resolve_qse_config
from worker.chemistry.algorithms.qse.excitations import (
    apply_fermionic_excitation,
    apply_fermionic_ladder,
    build_sector_excitation_candidates,
    double_excitation_specs,
    fermionic_excitation_specs,
    same_spin_count,
    single_excitation_specs,
)
from worker.chemistry.algorithms.qse.execution import (
    execute_dense_qse,
    execute_measured_qse,
    execute_sector_qse,
)
from worker.chemistry.algorithms.qse.reference import (
    normalize_reference_state_vector,
    parse_reference_scalar,
    string_option,
    vector_size_to_qubits,
)
from worker.chemistry.algorithms.qse.reference_policy import (
    build_vqe_reference_state,
    resolve_reference_state,
    resolve_sector_reference_state,
)
from worker.chemistry.algorithms.qse.results import (
    build_qse_completion_payload,
    build_qse_result,
    emit_qse_completion,
)
from worker.chemistry.algorithms.qse.sector import (
    dominant_sector_occupations,
    sector_excitation_coupling_score,
    sector_excitation_specs,
)
from worker.chemistry.ansatz_registry import build_ansatz
from worker.chemistry.circuit_artifacts import (
    build_hf_reference_circuit,
    serialize_circuit_artifact,
)
from worker.chemistry.eigensolver import (
    build_hf_reference_state,
    projected_ritz_diagnostics,
    resolve_operator_matrix,
    solve_exact_generalized_eigensystem,
    solve_generalized_eigenproblem,
    solve_stabilized_generalized_eigenproblem,
)
from worker.chemistry.hamiltonian_action import (
    HamiltonianAction,
    build_hamiltonian_action,
    can_build_hamiltonian_action,
)
from worker.chemistry.overlap import build_overlap_matrix
from worker.chemistry.progress import ProgressCallback
from worker.chemistry.projected_execution import (
    QSEExecutionPolicy,
    resolve_qse_execution_policy,
)
from worker.chemistry.projected_subspace import (
    projected_diagnostic_energy_is_reportable,
    solve_action_subspace,
)
from worker.chemistry.qse_measured import (
    estimate_measured_qse_matrices,
    measured_qse_dimension_limit,
)
from worker.chemistry.reference_descriptor import build_reference_descriptor
from worker.chemistry.reference_states import build_hf_reference_state_with_source
from worker.chemistry.sector_basis import (
    apply_fermionic_excitation_sector,
    hartree_fock_sector_state,
    state_from_sector_amplitudes,
)
from worker.chemistry.solver_utils import resolve_algorithm_config
from worker.chemistry.types import QSEResult
from worker.chemistry.vqe_solver import run_vqe

logger = logging.getLogger(__name__)


def _hf_reference_artifacts(hamiltonian: object) -> list[dict[str, Any]]:
    """Build a Hartree-Fock reference artifact when the reference is circuit-defined."""
    circuit = build_hf_reference_circuit(hamiltonian)
    if circuit is None:
        return []
    return [
        serialize_circuit_artifact(
            circuit,
            artifact_id="qse.reference.hf",
            algorithm="qse",
            role="reference",
            phase="reference",
            representative=True,
            label="Hartree-Fock reference",
            source="hf_reference",
            parameters={"reference_method": "hf"},
        )
    ]


_string_option = string_option
_parse_reference_scalar = parse_reference_scalar
_normalize_reference_state_vector = normalize_reference_state_vector
_vector_size_to_qubits = vector_size_to_qubits
_apply_fermionic_ladder = apply_fermionic_ladder
_apply_fermionic_excitation = apply_fermionic_excitation
_fermionic_excitation_specs = fermionic_excitation_specs
_single_excitation_specs = single_excitation_specs
_double_excitation_specs = double_excitation_specs
_same_spin_count = same_spin_count
_accept_basis_candidate = accept_basis_candidate
_build_sector_excitation_candidates = build_sector_excitation_candidates
_dominant_sector_occupations = dominant_sector_occupations
_sector_excitation_coupling_score = sector_excitation_coupling_score
_sector_excitation_specs = sector_excitation_specs
_real_scalar = real_scalar


def _build_vqe_reference_state(
    *,
    hamiltonian: object,
    backend: object,
    vector_size: int,
    resolved_config: dict[str, Any],
    progress_callback: ProgressCallback | None,
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    """Keep the legacy QSE VQE reference helper import-compatible."""
    return build_vqe_reference_state(
        hamiltonian=hamiltonian,
        backend=backend,
        vector_size=vector_size,
        resolved_config=resolved_config,
        progress_callback=progress_callback,
        run_vqe_fn=run_vqe,
        build_ansatz_fn=build_ansatz,
    )


def _resolve_reference_state(
    *,
    hamiltonian: object,
    backend: object,
    operator_matrix: np.ndarray,
    resolved_config: dict[str, Any],
    progress_callback: ProgressCallback | None,
) -> tuple[str, np.ndarray, list[dict[str, Any]]]:
    """Keep the legacy dense-reference helper import-compatible."""
    return resolve_reference_state(
        hamiltonian=hamiltonian,
        backend=backend,
        operator_matrix=operator_matrix,
        resolved_config=resolved_config,
        progress_callback=progress_callback,
        build_vqe_reference_state_fn=_build_vqe_reference_state,
        build_hf_reference_state_fn=build_hf_reference_state,
        hf_reference_artifacts_fn=_hf_reference_artifacts,
        normalize_reference_state_vector_fn=_normalize_reference_state_vector,
    )


def _resolve_sector_reference_state(
    *,
    hamiltonian: object,
    action: HamiltonianAction,
    resolved_config: dict[str, Any],
) -> tuple[str, np.ndarray, list[dict[str, Any]]]:
    """Keep the legacy sector-reference helper import-compatible."""
    return resolve_sector_reference_state(
        hamiltonian=hamiltonian,
        action=action,
        resolved_config=resolved_config,
        hf_reference_artifacts_fn=_hf_reference_artifacts,
        hartree_fock_sector_state_fn=hartree_fock_sector_state,
        state_from_sector_amplitudes_fn=state_from_sector_amplitudes,
    )


def _build_sector_excitation_basis(
    reference_state: np.ndarray,
    action: HamiltonianAction,
    *,
    excitation_level: str,
    target_rank: int,
    overlap_threshold: float,
    regularization: float,
    residual_tolerance: float,
    progress_callback: ProgressCallback | None,
) -> list[np.ndarray]:
    """Keep the legacy sector-basis helper import-compatible."""
    return build_sector_excitation_basis(
        reference_state,
        action,
        excitation_level=excitation_level,
        target_rank=target_rank,
        overlap_threshold=overlap_threshold,
        regularization=regularization,
        residual_tolerance=residual_tolerance,
        progress_callback=progress_callback,
        sector_excitation_specs_fn=_sector_excitation_specs,
        apply_fermionic_excitation_sector_fn=apply_fermionic_excitation_sector,
        accept_basis_candidate_fn=_accept_basis_candidate,
        solve_action_subspace_fn=solve_action_subspace,
    )


def _build_excitation_basis(
    reference_state: np.ndarray,
    operator_matrix: np.ndarray,
    *,
    excitation_level: str,
    target_rank: int,
    overlap_threshold: float,
    regularization: float,
    progress_callback: ProgressCallback | None,
) -> list[np.ndarray]:
    """Keep the legacy dense-basis helper import-compatible."""
    return build_excitation_basis(
        reference_state,
        operator_matrix,
        excitation_level=excitation_level,
        target_rank=target_rank,
        overlap_threshold=overlap_threshold,
        regularization=regularization,
        progress_callback=progress_callback,
        vector_size_to_qubits_fn=_vector_size_to_qubits,
        fermionic_excitation_specs_fn=_fermionic_excitation_specs,
        apply_fermionic_excitation_fn=_apply_fermionic_excitation,
        accept_basis_candidate_fn=_accept_basis_candidate,
        overlap_builder_fn=build_overlap_matrix,
        eigensolver_fn=solve_generalized_eigenproblem,
        real_scalar_fn=_real_scalar,
    )


def _use_measured_qse(backend_context: object | None) -> bool:
    """Return whether QSE should measure H/S through the backend estimator."""
    return resolve_qse_execution_policy(
        backend_context=backend_context,
        reference_method="hf",
    ).uses_measured_matrix_elements


def run_qse(
    *,
    hamiltonian: object,
    backend: object,
    config: dict[str, Any],
    progress_callback: ProgressCallback | None = None,
    backend_context: object | None = None,
    execution_policy: QSEExecutionPolicy | None = None,
) -> QSEResult:
    """Run a deterministic projected-subspace solve workflow."""
    resolved = resolve_algorithm_config(config, "qse")

    qse_config = resolve_qse_config(resolved)
    max_subspace_dim = qse_config.max_subspace_dim
    regularization = qse_config.regularization
    overlap_threshold = qse_config.overlap_threshold
    residual_tolerance = qse_config.residual_tolerance
    excitation_level = qse_config.excitation_level

    t_start = time.monotonic()
    reference_method_requested = qse_config.reference_method
    qse_policy = execution_policy or resolve_qse_execution_policy(
        backend_context=backend_context,
        reference_method=reference_method_requested,
    )
    if qse_policy.uses_measured_matrix_elements:
        measured_rank = min(max_subspace_dim, measured_qse_dimension_limit())
        logger.info(
            "QSE setup: max_subspace_dim=%d excitation=%s reference_method=%s "
            "execution_mode=measured_matrix_elements backend_target=%s",
            measured_rank,
            excitation_level,
            reference_method_requested,
            getattr(backend_context, "backend_target", None),
        )
        outcome = execute_measured_qse(
            hamiltonian=hamiltonian,
            estimator=backend,
            resolved_config=resolved,
            excitation_level=excitation_level,
            target_rank=measured_rank,
            regularization=regularization,
            residual_tolerance=residual_tolerance,
            progress_callback=progress_callback,
            backend_context=backend_context,
            estimate_matrices_fn=estimate_measured_qse_matrices,
            solve_stabilized_fn=solve_stabilized_generalized_eigenproblem,
            diagnostic_reportable_fn=projected_diagnostic_energy_is_reportable,
            build_reference_descriptor_fn=build_reference_descriptor,
            build_hf_reference_state_fn=build_hf_reference_state_with_source,
        )
    elif can_build_hamiltonian_action(hamiltonian) and (
        reference_method_requested == "provided_sector"
        or (
            reference_method_requested == "hf"
            and not hasattr(hamiltonian, "dense_operator_matrix")
        )
    ):
        action = build_hamiltonian_action(hamiltonian)
        logger.info(
            "QSE setup: sector_dim=%d max_subspace_dim=%d excitation=%s "
            "reference_method=%s execution_mode=sector_matrix_free",
            action.dimension,
            max_subspace_dim,
            excitation_level,
            reference_method_requested,
        )
        outcome = execute_sector_qse(
            hamiltonian=hamiltonian,
            action=action,
            resolved_config=resolved,
            excitation_level=excitation_level,
            target_rank=max_subspace_dim,
            overlap_threshold=overlap_threshold,
            regularization=regularization,
            residual_tolerance=residual_tolerance,
            progress_callback=progress_callback,
            resolve_reference_state_fn=_resolve_sector_reference_state,
            build_excitation_basis_fn=_build_sector_excitation_basis,
            solve_action_subspace_fn=solve_action_subspace,
            real_scalar_fn=_real_scalar,
        )
    else:
        operator = resolve_operator_matrix(hamiltonian)
        operator = 0.5 * (operator + operator.conj().T)
        dim = operator.shape[0]
        logger.info(
            "QSE setup: hilbert_dim=%d max_subspace_dim=%d excitation=%s reference_method=%s",
            dim,
            max_subspace_dim,
            excitation_level,
            str(resolved.get("reference_method", "vqe")),
        )
        outcome = execute_dense_qse(
            hamiltonian=hamiltonian,
            backend=backend,
            operator=operator,
            resolved_config=resolved,
            excitation_level=excitation_level,
            target_rank=max_subspace_dim,
            overlap_threshold=overlap_threshold,
            regularization=regularization,
            residual_tolerance=residual_tolerance,
            progress_callback=progress_callback,
            resolve_reference_state_fn=_resolve_reference_state,
            build_excitation_basis_fn=_build_excitation_basis,
            build_overlap_matrix_fn=build_overlap_matrix,
            solve_generalized_eigenproblem_fn=solve_generalized_eigenproblem,
            projected_ritz_diagnostics_fn=projected_ritz_diagnostics,
            real_scalar_fn=_real_scalar,
            solve_generalized_eigensystem_fn=solve_exact_generalized_eigensystem,
            execution_mode="dense_exact_emulation",
        )

    eigenvalues = outcome.eigenvalues
    if eigenvalues.size == 0:
        raise ValueError("QSE projected solve produced no eigenvalues")
    primary_energy = _real_scalar(eigenvalues[0], label="QSE primary energy")
    relative_residual = outcome.residual_diagnostics["relative_ritz_residual"]
    qse_elapsed = time.monotonic() - t_start
    if outcome.execution_mode is None:
        logger.info(
            "QSE finished: energy=%.8f converged=%s ref_energy=%.8f subspace_dim=%d "
            "relative_residual=%.2e elapsed=%.3fs",
            primary_energy,
            outcome.converged,
            outcome.reference_state_energy,
            outcome.basis_rank,
            relative_residual,
            qse_elapsed,
        )
    else:
        logger.info(
            "QSE finished: energy=%.8f converged=%s ref_energy=%.8f subspace_dim=%d "
            "relative_residual=%.2e elapsed=%.3fs execution_mode=%s",
            primary_energy,
            outcome.converged,
            outcome.reference_state_energy,
            outcome.basis_rank,
            relative_residual,
            qse_elapsed,
            outcome.execution_mode,
        )

    if progress_callback is not None:
        emit_qse_completion(
            progress_callback,
            build_qse_completion_payload(
                subspace_dim=outcome.basis_rank,
                primary_energy=primary_energy,
                max_subspace_dim=max_subspace_dim,
                reference_method=outcome.reference_method,
                excitation_level=excitation_level,
                regularization=regularization,
                diagnostics=outcome.diagnostics,
                relative_residual=relative_residual,
                residual_tolerance=residual_tolerance,
                execution_mode=outcome.execution_mode,
                sector_dimension=outcome.sector_dimension,
                num_spatial_orbitals=outcome.num_spatial_orbitals,
            ),
        )

    return build_qse_result(
        eigenvalues=eigenvalues,
        basis_rank=outcome.basis_rank,
        converged=outcome.converged,
        diagnostics=outcome.diagnostics,
        reference_state_energy=outcome.reference_state_energy,
        residual_diagnostics=outcome.residual_diagnostics,
        residual_tolerance=residual_tolerance,
        reference_circuit_artifacts=outcome.reference_circuit_artifacts,
        reference_method=outcome.reference_method,
        execution_mode=outcome.execution_mode,
        excitation_level=excitation_level,
        regularization=regularization,
        reference_state=outcome.reference_state,
        reference_variance=outcome.reference_variance,
        target_sector=(
            {
                "alpha": int(getattr(hamiltonian, "num_electrons_alpha")),
                "beta": int(getattr(hamiltonian, "num_electrons_beta")),
            }
            if all(
                isinstance(getattr(hamiltonian, name, None), int)
                for name in ("num_electrons_alpha", "num_electrons_beta")
            )
            else None
        ),
    )
