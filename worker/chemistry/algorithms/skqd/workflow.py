"""SKQD solver implementation for worker execution."""

from __future__ import annotations

import logging
import time
from typing import Any

import numpy as np

from worker.chemistry.accelerators import normalize_chemistry_device
from worker.chemistry.algorithms.skqd.config import SKQDConfig, resolve_skqd_config
from worker.chemistry.algorithms.skqd.convergence import (
    evaluate_sample_union_convergence,
)
from worker.chemistry.algorithms.skqd.diagnostics import build_skqd_prefix_summaries
from worker.chemistry.algorithms.skqd.distributions import (
    statevector_bitstring_distribution,
    time_evolved_bitstring_distribution,
)
from worker.chemistry.algorithms.skqd.execution import (
    SKQDExecutionPlan as _SKQDExecutionPlan,
)
from worker.chemistry.algorithms.skqd.execution import (
    SKQDExtensionOutcome as _SKQDExtensionOutcome,
)
from worker.chemistry.algorithms.skqd.execution import execute_skqd_extension
from worker.chemistry.algorithms.skqd.extension import (
    build_krylov_extension as _build_krylov_extension_kernel,
)
from worker.chemistry.algorithms.skqd.extension import (
    build_sector_krylov_extension as _build_sector_krylov_extension_kernel,
)
from worker.chemistry.algorithms.skqd.extension import emit_skqd_krylov_progress
from worker.chemistry.algorithms.skqd.results import (
    SKQDCompletionPayload as _SKQDCompletionPayload,
)
from worker.chemistry.algorithms.skqd.results import (
    add_skqd_solution_diagnostics as _add_skqd_solution_diagnostics,
)
from worker.chemistry.algorithms.skqd.results import (
    add_skqd_state_diagnostics as _add_skqd_state_diagnostics,
)
from worker.chemistry.algorithms.skqd.results import (
    build_not_run_sqd_core_summary as _build_not_run_sqd_core_summary,
)
from worker.chemistry.algorithms.skqd.results import (
    build_skqd_circuit_artifacts as _build_skqd_circuit_artifacts,
)
from worker.chemistry.algorithms.skqd.results import (
    build_skqd_completion_payload as _build_skqd_completion_payload,
)
from worker.chemistry.algorithms.skqd.results import (
    build_skqd_extension_diagnostics as _build_skqd_extension_diagnostics,
)
from worker.chemistry.algorithms.skqd.results import (
    build_sqd_core_summary as _build_sqd_core_summary,
)
from worker.chemistry.algorithms.skqd.results import (
    select_skqd_primary_solution as _select_skqd_primary_solution,
)
from worker.chemistry.algorithms.skqd.sample_union import (
    execute_sample_union_workflow,
    execute_sampler_sample_union_workflow,
)
from worker.chemistry.algorithms.skqd.seed import (
    sector_seed_state_from_sqd_result_with_source,
    seed_state_from_sqd_result,
    seed_state_from_sqd_result_with_source,
)
from worker.chemistry.algorithms.skqd.selected_ci import solve_sample_union_selected_ci
from worker.chemistry.algorithms.skqd.spectral_width import (
    estimate_action_spectral_width,
    estimate_dense_spectral_width,
    paper_time_step,
)
from worker.chemistry.algorithms.sqd.config import resolve_sqd_options
from worker.chemistry.algorithms.sqd.state import import_sqd_dependencies
from worker.chemistry.algorithms.sqd.workflow import run_sqd
from worker.chemistry.eigensolver import (
    build_hf_reference_state,
    build_reference_state,
    projected_ritz_diagnostics,
    resolve_operator_matrix,
)
from worker.chemistry.hamiltonian_action import (
    HamiltonianAction,
    build_hamiltonian_action,
    can_build_hamiltonian_action,
)
from worker.chemistry.progress import ProgressCallback
from worker.chemistry.projected_energy import (
    matrix_free_projected_ground_energy,
    orthonormal_projected_ground_energy,
)
from worker.chemistry.projected_subspace import (
    orthonormalize_candidate,
    solve_action_subspace,
)
from worker.chemistry.sector_basis import (
    hartree_fock_sector_state,
)
from worker.chemistry.solver_utils import resolve_algorithm_config
from worker.chemistry.state_vectors import normalize_state_vector
from worker.chemistry.time_evolution import (
    exact_time_evolution_state_from_spectrum,
    prepare_exact_time_evolution,
)
from worker.chemistry.types import SKQDResult

logger = logging.getLogger(__name__)

# Re-export private names for existing solver tests and importers.
_seed_state_from_sqd_result = seed_state_from_sqd_result
_seed_state_from_sqd_result_with_source = seed_state_from_sqd_result_with_source
_sector_seed_state_from_sqd_result_with_source = sector_seed_state_from_sqd_result_with_source
_statevector_bitstring_distribution = statevector_bitstring_distribution
_time_evolved_bitstring_distribution = time_evolved_bitstring_distribution
_dense_skqd_partial_energy = orthonormal_projected_ground_energy
_sector_skqd_partial_energy = matrix_free_projected_ground_energy
_emit_skqd_krylov_progress = emit_skqd_krylov_progress


def _build_krylov_extension(
    operator: np.ndarray,
    *,
    seed_state: np.ndarray | None,
    seeded_from_sqd: bool,
    target_rank: int,
    time_step: float,
    residual_tolerance: float,
    progress_callback: ProgressCallback | None,
) -> tuple[np.ndarray, int, dict[str, float], np.ndarray | None]:
    """Adapt dense SKQD inputs to the extension module."""
    return _build_krylov_extension_kernel(
        operator,
        reference_state=_resolve_dense_krylov_seed(
            operator=operator,
            seed_state=seed_state,
        ),
        seeded_from_sqd=seeded_from_sqd,
        target_rank=target_rank,
        time_step=time_step,
        residual_tolerance=residual_tolerance,
        progress_callback=progress_callback,
        orthonormalize_fn=orthonormalize_candidate,
        partial_energy_fn=_dense_skqd_partial_energy,
        prepare_spectrum_fn=prepare_exact_time_evolution,
        evolve_state_fn=exact_time_evolution_state_from_spectrum,
        emit_progress_fn=_emit_skqd_krylov_progress,
        projected_ritz_diagnostics_fn=projected_ritz_diagnostics,
    )


def _build_sector_krylov_extension(
    action: HamiltonianAction,
    *,
    seed_state: np.ndarray,
    seeded_from_sqd: bool,
    target_rank: int,
    time_step: float,
    residual_tolerance: float,
    progress_callback: ProgressCallback | None,
) -> tuple[np.ndarray, int, dict[str, float], np.ndarray | None]:
    """Adapt sector SKQD inputs to the extension module."""
    return _build_sector_krylov_extension_kernel(
        action,
        reference_state=_resolve_sector_krylov_seed(action, seed_state),
        seeded_from_sqd=seeded_from_sqd,
        target_rank=target_rank,
        time_step=time_step,
        residual_tolerance=residual_tolerance,
        progress_callback=progress_callback,
        orthonormalize_fn=orthonormalize_candidate,
        partial_energy_fn=_sector_skqd_partial_energy,
        solve_action_subspace_fn=solve_action_subspace,
        emit_progress_fn=_emit_skqd_krylov_progress,
    )


def _resolve_dense_krylov_seed(
    *,
    operator: np.ndarray,
    seed_state: np.ndarray | None,
) -> np.ndarray:
    """Resolve and normalize the dense SKQD Krylov seed state."""
    if seed_state is None:
        return build_reference_state(operator.shape[0])
    return normalize_state_vector(
        seed_state,
        error_message="SKQD seed state must be non-zero",
        expected_size=operator.shape[0],
    )


def _resolve_sector_krylov_seed(
    action: HamiltonianAction,
    seed_state: np.ndarray,
) -> np.ndarray:
    """Resolve and normalize the sector SKQD Krylov seed state."""
    return normalize_state_vector(
        seed_state,
        error_message="SKQD sector seed state must be non-zero",
        expected_size=action.dimension,
    )


def _prepare_skqd_execution(hamiltonian: object) -> _SKQDExecutionPlan:
    """Resolve the SKQD execution mode and underlying operator resources."""
    sector_action = (
        build_hamiltonian_action(hamiltonian)
        if can_build_hamiltonian_action(hamiltonian)
        and not hasattr(hamiltonian, "dense_operator_matrix")
        else None
    )
    if sector_action is None:
        operator = resolve_operator_matrix(hamiltonian)
        return _SKQDExecutionPlan(
            sector_action=None,
            operator=operator,
            operator_dimension=int(operator.shape[0]),
            execution_mode="dense_matrix",
        )
    return _SKQDExecutionPlan(
        sector_action=sector_action,
        operator=None,
        operator_dimension=int(sector_action.dimension),
        execution_mode="sector_matrix_free",
    )


def _resolve_legacy_sampling_time_step(
    *,
    skqd_config: SKQDConfig,
    plan: _SKQDExecutionPlan,
    hamiltonian: object,
) -> float:
    """Resolve the legacy Krylov extension time step, applying paper auto-scaling.

    Honors an explicit user time step; otherwise derives Delta t = pi / Delta E_{N-1}
    from the operator or sector-action spectral width.
    """
    explicit = getattr(skqd_config, "sampling_time_step", None)
    if explicit is not None:
        return float(explicit)
    if plan.sector_action is not None:
        spectral_width, _source = estimate_action_spectral_width(
            plan.sector_action,
            pauli_hamiltonian=getattr(hamiltonian, "pauli_hamiltonian", None),
        )
    elif plan.operator is not None:
        spectral_width, _source = estimate_dense_spectral_width(plan.operator)
    else:
        raise ValueError("SKQD legacy extension requires an operator or sector action")
    return paper_time_step(spectral_width)


def _run_skqd_extension(
    *,
    sqd_result: SKQDResult | Any,
    plan: _SKQDExecutionPlan,
    hamiltonian: object,
    krylov_extension_dim: int,
    sampling_time_step: float,
    residual_tolerance: float,
    progress_callback: ProgressCallback | None,
) -> _SKQDExtensionOutcome:
    """Resolve the Krylov seed and run the dense or sector extension path."""
    return execute_skqd_extension(
        sqd_result=sqd_result,
        plan=plan,
        hamiltonian=hamiltonian,
        krylov_extension_dim=krylov_extension_dim,
        sampling_time_step=sampling_time_step,
        residual_tolerance=residual_tolerance,
        progress_callback=progress_callback,
        resolve_sector_seed_fn=_sector_seed_state_from_sqd_result_with_source,
        resolve_dense_seed_fn=_seed_state_from_sqd_result_with_source,
        build_sector_krylov_fn=_build_sector_krylov_extension,
        build_dense_krylov_fn=_build_krylov_extension,
        build_sector_hf_reference_fn=hartree_fock_sector_state,
        build_dense_hf_reference_fn=build_hf_reference_state,
    )


def _failed_skqd_extension_outcome(plan: _SKQDExecutionPlan) -> _SKQDExtensionOutcome:
    """Create an explicit empty extension outcome after a recoverable extension failure."""
    seed = np.zeros(plan.operator_dimension, dtype=complex)
    return _SKQDExtensionOutcome(
        sqd_seed=None,
        seed_source="extension_failed",
        krylov_seed=seed,
        ritz_values_raw=np.asarray([], dtype=float),
        basis_rank=0,
        residual_diagnostics={
            "relative_ritz_residual": None,
            "ritz_residual_norm": None,
        },
        ground_state=None,
    )


def _emit_skqd_completion(
    *,
    progress_callback: ProgressCallback | None,
    payload: _SKQDCompletionPayload,
) -> None:
    """Emit the SKQD completed progress payload."""
    if progress_callback is None:
        return
    progress_callback(
        {
            "algorithm": "skqd",
            "stage": "completed",
            "step": "krylov_extension",
            "iteration": payload.basis_rank,
            "energy": float(payload.primary_energy),
            "completed_iterations": payload.basis_rank,
            "total_iterations": payload.basis_rank,
            "overall_iterations": payload.primary_iterations,
            "krylov_extension_dim": payload.krylov_extension_dim,
            "time_step": payload.sampling_time_step,
            "basis_rank": payload.basis_rank,
            "sqd_iterations": payload.sqd_iterations,
            "seeded_from_sqd": payload.seeded_from_sqd,
            "seeded_from_sqd_occupancies": False,
            "seed_source": payload.seed_source,
            "execution_mode": payload.execution_mode,
            "krylov_converged": payload.krylov_converged,
            "sqd_converged": payload.sqd_converged,
            "overall_converged": payload.overall_converged,
            "selected_solution": payload.selected_solution,
            "selected_solution_converged": payload.selected_solution_converged,
            "relative_residual": payload.relative_residual,
            "residual_tolerance": payload.residual_tolerance,
            "min_ritz": payload.min_ritz,
            "max_ritz": payload.max_ritz,
        }
    )


def _run_skqd_sample_union(
    *,
    hamiltonian: object,
    backend: object | None,
    skqd_config: SKQDConfig,
    plan: Any,
    progress_callback: ProgressCallback | None,
    backend_context: Any | None,
    started_at: float,
    selected_ci_execution: dict[str, Any],
) -> SKQDResult:
    """Run the direct sample-union path and persist its explicit status."""
    use_sampler_circuits = (
        getattr(backend_context, "backend_target", None) in {"aer_simulator", "ibm_runtime"}
        and backend is not None
    )
    execution_path = (
        "sampler_krylov_union" if use_sampler_circuits else "analysis_only_exact_statevector_oracle"
    )
    if use_sampler_circuits:
        sample_union, workflow_metadata = execute_sampler_sample_union_workflow(
            hamiltonian=hamiltonian,
            backend=backend,
            skqd_config=skqd_config,
            backend_context=backend_context,
        )
    else:
        sample_union, outcome, workflow_metadata = execute_sample_union_workflow(
            hamiltonian=hamiltonian,
            plan=plan,
            skqd_config=skqd_config,
        )
    if use_sampler_circuits:
        deps = import_sqd_dependencies()
        options = resolve_sqd_options(
            skqd_config.sqd_config,
            hamiltonian,
            sample_budget=getattr(backend_context, "shots", None),
        )
        outcome = solve_sample_union_selected_ci(
            sample_union,
            options=options,
            rng=np.random.default_rng(skqd_config.seed),
            recover_configurations=deps.recover_configurations,
            postselect_by_hamming_right_and_left=deps.postselect_by_hamming_right_and_left,
            solve_fermion=deps.solve_fermion,
        )
    sqd_core = _build_not_run_sqd_core_summary(
        reason="sample_union_mode_uses_direct_krylov_samples"
    )
    prefix_options = resolve_sqd_options(
        skqd_config.sqd_config,
        hamiltonian,
        sample_budget=getattr(backend_context, "shots", None),
    )
    prefix_summaries = build_skqd_prefix_summaries(
        sample_union,
        num_elec_a=prefix_options.num_elec_a,
        num_elec_b=prefix_options.num_elec_b,
    )
    sample_count = sum(sample.bitstring_matrix.shape[0] for sample in sample_union.samples_by_state)
    primary_iterations = len(sample_union.samples_by_state)
    convergence_verdict = evaluate_sample_union_convergence(
        prefix_summaries=prefix_summaries,
        selected_ci_summary=outcome.summary,
    )
    converged = bool(convergence_verdict["converged"])
    diagnostics = {
        **workflow_metadata,
        "requested_sampling_mode": skqd_config.sampling_mode,
        "execution_path": execution_path,
        "selected_ci_execution": dict(selected_ci_execution),
        "execution_provenance": {
            "requested_sampling_mode": skqd_config.sampling_mode,
            "actual_sampling_mode": workflow_metadata["sampling_mode"],
            "execution_path": execution_path,
            "comparison_scope": (
                "sampler_krylov_union" if use_sampler_circuits else "analysis_only"
            ),
            "hardware_sampling_capable": use_sampler_circuits,
            "backend_target": getattr(backend_context, "backend_target", None),
        },
        "work_ledger": dict(sample_union.work_ledger),
        "sample_union": outcome.summary,
        "krylov_prefix_summaries": prefix_summaries,
        "sample_provenance": list(sample_union.provenance),
        "selected_solution": "skqd_sample_union",
        "selected_solution_converged": converged,
        "convergence_status": convergence_verdict["convergence_status"],
        "convergence_verdict": convergence_verdict,
        "sqd_core_status": "not_run",
        "sqd_core_energy": None,
        "sample_union_energy": float(outcome.energy),
        "sqd_iterations": 0,
        "sqd_converged": None,
        "primary_iteration_unit": "krylov_state",
        "extension_attempted": False,
        "extension_status": "not_applicable",
        "extension_failure_reason": None,
        "legacy_extension_available": True,
        "sample_count": int(sample_count),
        "wall_time_seconds": time.monotonic() - started_at,
    }
    if progress_callback is not None:
        progress_callback(
            {
                "algorithm": "skqd",
                "stage": "completed",
                "step": "sample_union",
                "iteration": len(sample_union.samples_by_state),
                "completed_iterations": len(sample_union.samples_by_state),
                "total_iterations": len(sample_union.samples_by_state),
                "overall_iterations": primary_iterations,
                "iteration_unit": "krylov_state",
                "energy": float(outcome.energy),
                "sampling_mode": workflow_metadata["sampling_mode"],
                "selected_solution": "skqd_sample_union",
                "selected_solution_converged": converged,
                "overall_converged": converged,
                "convergence_status": convergence_verdict["convergence_status"],
            }
        )
    return SKQDResult(
        algorithm="skqd",
        primary_energy=float(outcome.energy),
        primary_iterations=primary_iterations,
        converged=converged,
        sqd_core=sqd_core,
        krylov_extension_diagnostics=diagnostics,
        circuit_artifacts=[],
        circuit_artifact_policy={},
    )


def run_skqd(
    *,
    hamiltonian: object,
    backend: object | None,
    config: dict[str, Any],
    progress_callback: ProgressCallback | None = None,
    backend_context: Any | None = None,
) -> SKQDResult:
    """Run direct SKQD sample-union mode or the explicit legacy extension."""
    resolved = resolve_algorithm_config(config, "skqd")
    skqd_config = resolve_skqd_config(resolved)
    backend_target = getattr(backend_context, "backend_target", None)
    if (
        skqd_config.sampling_mode == "sample_union_exact"
        and backend is None
        and backend_target in {"aer_simulator", "ibm_runtime"}
    ):
        raise RuntimeError(
            f"SKQD requires a sampler for the requested {backend_target} execution; "
            "refusing to fall back to the exact local statevector oracle"
        )

    t_start = time.monotonic()
    plan = _prepare_skqd_execution(hamiltonian)
    logger.info(
        "SKQD setup: operator_dim=%d krylov_extension_dim=%d execution_mode=%s",
        plan.operator_dimension,
        skqd_config.krylov_extension_dim,
        plan.execution_mode,
    )
    if skqd_config.sampling_mode == "sample_union_exact":
        selected_ci_device = normalize_chemistry_device(
            (getattr(backend_context, "chemistry_options", {}) or {}).get("selected_ci_device")
        )
        if selected_ci_device == "GPU":
            raise RuntimeError(
                "GPU selected-CI is not available for SKQD sample_union_exact because that "
                "path must diagonalize the arbitrary sampled determinant union on CPU"
            )
        selected_ci_execution = {
            "requested_device": selected_ci_device,
            "actual_device": "CPU",
            "provider": "skqd.sample_union_exact",
            "fallback_reason": (
                "SKQD sample_union_exact uses the exact arbitrary-union CPU solver"
                if selected_ci_device == "AUTO"
                else None
            ),
        }
        return _run_skqd_sample_union(
            hamiltonian=hamiltonian,
            backend=backend,
            skqd_config=skqd_config,
            plan=plan,
            progress_callback=progress_callback,
            backend_context=backend_context,
            started_at=t_start,
            selected_ci_execution=selected_ci_execution,
        )
    sqd_result = run_sqd(
        hamiltonian=hamiltonian,
        backend=backend,
        config=skqd_config.sqd_config,
        progress_callback=progress_callback,
        backend_context=backend_context,
    )
    sampling_time_step = _resolve_legacy_sampling_time_step(
        skqd_config=skqd_config,
        plan=plan,
        hamiltonian=hamiltonian,
    )
    extension_failure_reason: str | None = None
    extension_started = time.monotonic()
    try:
        extension = _run_skqd_extension(
            sqd_result=sqd_result,
            plan=plan,
            hamiltonian=hamiltonian,
            krylov_extension_dim=skqd_config.krylov_extension_dim,
            sampling_time_step=sampling_time_step,
            residual_tolerance=skqd_config.residual_tolerance,
            progress_callback=progress_callback,
        )
    except Exception as exc:
        extension = _failed_skqd_extension_outcome(plan)
        extension_failure_reason = f"{type(exc).__name__}: {exc}"
        logger.warning("SKQD Krylov extension failed; preserving SQD core result: %s", exc)
    extension_elapsed = time.monotonic() - extension_started
    ritz_values = [float(value) for value in extension.ritz_values_raw]
    sqd_core_energy = (
        float(sqd_result.primary_energy) if sqd_result.primary_energy is not None else None
    )

    krylov_extension_diagnostics = _build_skqd_extension_diagnostics(
        plan=plan,
        extension=extension,
        sqd_result=sqd_result,
        ritz_values=ritz_values,
        krylov_extension_dim=skqd_config.krylov_extension_dim,
        sampling_time_step=sampling_time_step,
    )

    sqd_core = _build_sqd_core_summary(sqd_result)
    circuit_artifacts = _build_skqd_circuit_artifacts(sqd_result)

    extension_energy = float(ritz_values[0]) if ritz_values else None
    relative_residual = extension.residual_diagnostics.get("relative_ritz_residual")
    krylov_converged = (
        isinstance(relative_residual, (int, float))
        and np.isfinite(float(relative_residual))
        and relative_residual <= skqd_config.residual_tolerance
    )
    primary_energy, selected_solution = _select_skqd_primary_solution(
        sqd_core_energy=sqd_core_energy,
        extension_energy=extension_energy,
        extension_converged=bool(krylov_converged),
    )
    if primary_energy is None:
        raise ValueError("SKQD produced no SQD-core or Krylov-extension energy")
    primary_iterations = int(sqd_result.primary_iterations or 0) + extension.basis_rank
    overall_converged = bool(sqd_result.converged) and bool(krylov_converged)
    krylov_extension_diagnostics["krylov_converged"] = krylov_converged
    krylov_extension_diagnostics["overall_converged"] = overall_converged
    krylov_extension_diagnostics["extension_attempted"] = True
    krylov_extension_diagnostics["extension_status"] = (
        "failed" if extension_failure_reason is not None else "completed"
    )
    krylov_extension_diagnostics["extension_failure_reason"] = extension_failure_reason
    krylov_extension_diagnostics["extension_cost"] = {
        "wall_time_seconds": extension_elapsed,
        "requested_dimension": skqd_config.krylov_extension_dim,
        "basis_rank": extension.basis_rank,
        "operator_dimension": plan.operator_dimension,
    }
    converged = bool(sqd_result.converged) if selected_solution == "sqd_core" else overall_converged
    _add_skqd_solution_diagnostics(
        krylov_extension_diagnostics,
        sqd_core_energy=sqd_core_energy,
        extension_energy=extension_energy,
        selected_solution=selected_solution,
        selected_solution_converged=converged,
    )
    if extension_failure_reason is None:
        _add_skqd_state_diagnostics(
            krylov_extension_diagnostics,
            plan=plan,
            extension=extension,
            sampling_time_step=sampling_time_step,
        )
    skqd_elapsed = time.monotonic() - t_start
    logger.info(
        "SKQD finished: energy=%.8f converged=%s selected_solution=%s sqd_energy=%s "
        "basis_rank=%d total_iterations=%d relative_residual=%s elapsed=%.3fs",
        primary_energy,
        converged,
        selected_solution,
        f"{sqd_core_energy:.8f}" if sqd_core_energy is not None else None,
        extension.basis_rank,
        primary_iterations,
        relative_residual,
        skqd_elapsed,
    )

    _emit_skqd_completion(
        progress_callback=progress_callback,
        payload=_build_skqd_completion_payload(
            extension=extension,
            sqd_result=sqd_result,
            skqd_config=skqd_config,
            primary_energy=primary_energy,
            primary_iterations=primary_iterations,
            selected_solution=selected_solution,
            selected_solution_converged=converged,
            krylov_converged=krylov_converged,
            overall_converged=overall_converged,
            ritz_values=ritz_values,
            execution_mode=plan.execution_mode,
            sampling_time_step=sampling_time_step,
        ),
    )

    return SKQDResult(
        algorithm="skqd",
        primary_energy=primary_energy,
        primary_iterations=primary_iterations,
        converged=converged,
        sqd_core=sqd_core,
        krylov_extension_diagnostics={
            **krylov_extension_diagnostics,
            "ritz_values": ritz_values,
        },
        circuit_artifacts=circuit_artifacts,
        circuit_artifact_policy=sqd_result.circuit_artifact_policy,
    )
