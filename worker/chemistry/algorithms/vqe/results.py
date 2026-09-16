"""VQE result construction and energy provenance helpers for the algorithm package."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

import numpy as np

from worker.chemistry.reference_descriptor import (
    ReferenceDescriptor,
    fingerprint_circuit_metadata,
)
from worker.chemistry.types import VQEResult

logger = logging.getLogger(__name__)

StateDataBuilder = Callable[[Any, np.ndarray, int], tuple[Any, Any, Any]]
CircuitArtifactBuilder = Callable[..., list[dict[str, Any]]]
BestEnergySelector = Callable[[float | None, list[float]], float]


def _objective_observation_diagnostics(
    objective_state: Any,
    *,
    initial_point_evaluations: int = 0,
    initial_point_candidates: int | None = None,
    warm_start_retry_count: int = 0,
    optimizer_start_count: int | None = None,
) -> dict[str, Any]:
    """Build the VQE work and uncertainty ledger from objective state."""
    trace = list(getattr(objective_state, "convergence_trace", []) or [])
    standard_error_trace = list(getattr(objective_state, "standard_error_trace", []) or [])
    if len(standard_error_trace) < len(trace):
        standard_error_trace.extend([None] * (len(trace) - len(standard_error_trace)))
    elif len(standard_error_trace) > len(trace):
        standard_error_trace = standard_error_trace[: len(trace)]

    objective_evaluations = len(trace)
    objective_evaluation_attempts = max(
        objective_evaluations,
        int(getattr(objective_state, "evaluation_attempt_count", objective_evaluations) or 0),
    )
    objective_evaluation_failures = max(
        0,
        int(getattr(objective_state, "evaluation_failure_count", 0) or 0),
    )
    initial_point_evaluations = max(0, min(initial_point_evaluations, objective_evaluations))
    final_reevaluation_evaluations = max(
        0,
        int(getattr(objective_state, "final_reevaluation_count", 0) or 0),
    )
    primitive_work = getattr(objective_state, "primitive_work", None)
    primitive_run_attempts = max(0, int(getattr(primitive_work, "run_attempts", 0) or 0))
    primitive_pub_attempts = max(0, int(getattr(primitive_work, "pub_attempts", 0) or 0))
    primitive_jobs = max(0, int(getattr(primitive_work, "jobs_returned", 0) or 0))
    primitive_pubs = max(0, int(getattr(primitive_work, "pubs_returned", 0) or 0))
    primitive_run_failures = max(0, int(getattr(primitive_work, "run_failures", 0) or 0))
    shots = getattr(objective_state, "shots", None)
    estimator_precision = getattr(objective_state, "estimator_precision", None)
    if isinstance(estimator_precision, (int, float)) and float(estimator_precision) > 0.0:
        shot_budget_mode = "estimator_precision"
        shots_per_pub = None
        total_shots = None
    elif shots is not None:
        shot_budget_mode = "fixed_shots"
        shots_per_pub = int(shots)
        total_shots = primitive_pubs * shots_per_pub
    else:
        shot_budget_mode = "exact_expectation"
        shots_per_pub = None
        total_shots = None
    available_uncertainties = sum(value is not None for value in standard_error_trace)
    if available_uncertainties == objective_evaluations and objective_evaluations:
        uncertainty_status = "available"
    elif available_uncertainties:
        uncertainty_status = "partial"
    else:
        uncertainty_status = "unavailable_from_backend"

    started_at = getattr(objective_state, "started_at", None)
    wall_time_seconds = (
        max(0.0, time.monotonic() - float(started_at))
        if isinstance(started_at, (int, float))
        else None
    )
    optimizer_started_at = getattr(objective_state, "optimizer_started_at", None)
    optimizer_finished_at = getattr(objective_state, "optimizer_finished_at", None)
    optimizer_wall_time_seconds = None
    if isinstance(optimizer_started_at, (int, float)):
        optimizer_end = (
            float(optimizer_finished_at)
            if isinstance(optimizer_finished_at, (int, float))
            else time.monotonic()
        )
        optimizer_wall_time_seconds = max(0.0, optimizer_end - float(optimizer_started_at))

    work_ledger = {
        "initial_point_evaluations": initial_point_evaluations,
        "optimizer_objective_evaluations": objective_evaluations - initial_point_evaluations,
        "objective_evaluations": objective_evaluations,
        "objective_evaluation_attempts": objective_evaluation_attempts,
        "objective_evaluation_failures": objective_evaluation_failures,
        "final_reevaluation_evaluations": final_reevaluation_evaluations,
        "primitive_run_attempts": primitive_run_attempts,
        "primitive_pub_attempts": primitive_pub_attempts,
        "primitive_run_failures": primitive_run_failures,
        "primitive_pubs": primitive_pubs,
        "primitive_jobs": primitive_jobs,
        "warm_start_candidate_count": (
            max(0, int(initial_point_candidates))
            if initial_point_candidates is not None
            else 0
        ),
        "warm_start_retry_count": max(0, int(warm_start_retry_count)),
        "optimizer_start_count": (
            max(0, int(optimizer_start_count))
            if optimizer_start_count is not None
            else 0
        ),
        "shot_budget_mode": shot_budget_mode,
        "estimator_precision_per_pub": (
            float(estimator_precision)
            if isinstance(estimator_precision, (int, float)) and estimator_precision > 0.0
            else None
        ),
        "shots_per_pub": shots_per_pub,
        "primitive_shots": total_shots,
        "primitive_shot_count_basis": (
            "configured_shots_per_returned_pub" if total_shots is not None else None
        ),
        "wall_time_seconds": wall_time_seconds,
        "optimizer_wall_time_seconds": optimizer_wall_time_seconds,
    }
    return {
        "objective_standard_error_trace": standard_error_trace,
        "objective_standard_error_observations": available_uncertainties,
        "objective_uncertainty_status": uncertainty_status,
        "initial_point_evaluations": initial_point_evaluations,
        "optimizer_objective_evaluations": objective_evaluations - initial_point_evaluations,
        "objective_evaluation_attempts": objective_evaluation_attempts,
        "objective_evaluation_failures": objective_evaluation_failures,
        "final_reevaluation_evaluations": final_reevaluation_evaluations,
        "primitive_run_attempts": primitive_run_attempts,
        "primitive_pub_attempts": primitive_pub_attempts,
        "primitive_run_failures": primitive_run_failures,
        "primitive_pubs": primitive_pubs,
        "primitive_jobs": primitive_jobs,
        "shot_budget_mode": shot_budget_mode,
        "estimator_precision_per_pub": (
            float(estimator_precision)
            if isinstance(estimator_precision, (int, float)) and estimator_precision > 0.0
            else None
        ),
        "shots_per_pub": shots_per_pub,
        "primitive_shots": total_shots,
        "primitive_shot_count_basis": (
            "configured_shots_per_returned_pub" if total_shots is not None else None
        ),
        "wall_time_seconds": wall_time_seconds,
        "optimizer_wall_time_seconds": optimizer_wall_time_seconds,
        "work_ledger": work_ledger,
    }


def _stable_termination_reason(
    diagnostics: dict[str, Any],
    *,
    objective_evaluations: int,
    converged: bool,
) -> str:
    """Normalize native optimizer output to stable worker reason codes."""
    current_reason = diagnostics.get("termination_reason")
    objective_limit = diagnostics.get("effective_max_function_evaluations")
    if objective_limit is None:
        objective_limit = diagnostics.get("effective_objective_max_function_evaluations")
    if objective_limit is None:
        objective_limit = diagnostics.get("max_function_evaluations")
    if (
        current_reason == "max_function_evaluations"
        or (
            isinstance(objective_limit, (int, float))
            and objective_evaluations >= int(objective_limit)
        )
    ):
        return "max_function_evaluations"

    native_limit = diagnostics.get("effective_optimizer_max_function_evaluations")
    native_evaluations = diagnostics.get("optimizer_function_evaluations")
    if (
        isinstance(native_limit, (int, float))
        and isinstance(native_evaluations, (int, float))
        and native_evaluations >= int(native_limit)
    ):
        return "max_function_evaluations"

    if current_reason in {"ansatz_has_no_parameters", "stationary_initial_point"}:
        return str(current_reason)
    if current_reason == "optimizer_success" and converged:
        return "optimizer_success"
    if current_reason in {"optimizer_failure", None}:
        optimizer_iterations = diagnostics.get("optimizer_iterations")
        effective_iterations = diagnostics.get("effective_optimizer_max_iterations")
        if effective_iterations is None:
            effective_iterations = diagnostics.get("effective_max_iterations")
        if (
            isinstance(optimizer_iterations, (int, float))
            and isinstance(effective_iterations, (int, float))
            and optimizer_iterations >= int(effective_iterations)
        ):
            return "max_iterations"
        return "optimizer_success" if converged else "optimizer_failure"
    return str(current_reason)


def _update_vqe_truth_diagnostics(
    diagnostics: dict[str, Any],
    *,
    objective_state: Any,
    converged: bool,
) -> None:
    """Persist independent optimizer, numerical, and scientific status."""
    objective_evaluations = len(getattr(objective_state, "convergence_trace", []) or [])
    termination_reason = _stable_termination_reason(
        diagnostics,
        objective_evaluations=objective_evaluations,
        converged=converged,
    )
    objective_limit = diagnostics.get("effective_max_function_evaluations")
    if objective_limit is None:
        objective_limit = diagnostics.get("effective_objective_max_function_evaluations")
    if objective_limit is None:
        objective_limit = diagnostics.get("max_function_evaluations")
    budget_exhausted = termination_reason == "max_function_evaluations" or bool(
        isinstance(objective_limit, (int, float))
        and objective_evaluations >= int(objective_limit)
    )
    trace = list(getattr(objective_state, "convergence_trace", []) or [])
    best_energy = getattr(objective_state, "best_energy", None)
    final_energy = diagnostics.get("final_energy")
    numerical_stability = bool(
        trace
        and all(np.isfinite(float(value)) for value in trace)
        and (best_energy is None or np.isfinite(float(best_energy)))
        and (final_energy is None or np.isfinite(float(final_energy)))
    )
    optimizer_success = diagnostics.get("success")
    if not isinstance(optimizer_success, bool):
        optimizer_success = bool(converged)
    threshold = diagnostics.get("convergence_threshold")
    delta = diagnostics.get("final_delta_energy")
    delta_stable = (
        isinstance(delta, (int, float))
        and isinstance(threshold, (int, float))
        and np.isfinite(float(delta))
        and float(delta) <= float(threshold)
    )
    scientific_converged = (
        True
        if termination_reason == "ansatz_has_no_parameters" and numerical_stability
        else bool(
            optimizer_success
            and numerical_stability
            and not budget_exhausted
            and (
                delta_stable
                or (diagnostics.get("optimizer_kind") == "spsa" and converged)
            )
        )
    )
    native_message = diagnostics.get("message")
    diagnostics.update(
        {
            "termination_reason": termination_reason,
            "termination_reason_code": termination_reason,
            "native_termination_message": str(native_message) if native_message is not None else None,
            "optimizer_success": optimizer_success,
            "numerical_stability": numerical_stability,
            "scientific_converged": scientific_converged,
            "budget_exhausted": budget_exhausted,
        }
    )


def _attach_reference_descriptor(
    diagnostics: dict[str, Any],
    *,
    artifacts: list[dict[str, Any]],
    ansatz_name: str,
    include_statevector_data: bool,
    energy: float,
) -> None:
    """Persist VQE preparation provenance without claiming a noisy state."""
    diagnostics["reference_descriptor"] = ReferenceDescriptor(
        reference_source="vqe_optimizer",
        preparation_path="ansatz_circuit",
        execution_mode=("statevector_diagnostic" if include_statevector_data else "estimator_backend"),
        reference_energy=float(energy),
        circuit_fingerprint=fingerprint_circuit_metadata(artifacts),
        ansatz_name=ansatz_name,
        metadata={"state_fingerprint_status": "not_claimed_for_estimator_run"},
    ).to_metadata()


def build_parameterless_vqe_result(
    *,
    objective: Any,
    initial_point: np.ndarray,
    include_statevector_data: bool,
    ansatz: Any,
    num_qubits: int,
    optimizer_diagnostics: dict[str, Any],
    initial_point_diagnostics: dict[str, Any],
    ansatz_name: str,
    optimizer_name: str,
    reps: int,
    compute_state_data_fn: StateDataBuilder,
    build_circuit_artifacts_fn: CircuitArtifactBuilder,
) -> VQEResult:
    """Build the parameterless VQE result without invoking an optimizer."""
    final_energy = objective(initial_point)
    final_parameters = [float(value) for value in np.asarray(initial_point, dtype=float)]
    if include_statevector_data:
        bloch_vectors, dm_real, dm_imag = compute_state_data_fn(
            ansatz,
            initial_point,
            num_qubits,
        )
    else:
        bloch_vectors = dm_real = dm_imag = None
    diagnostics = {
        **optimizer_diagnostics,
        **initial_point_diagnostics,
        "termination_reason": "ansatz_has_no_parameters",
        "function_evaluations": 1,
        "objective_evaluations": 1,
        "optimizer_iterations": 0,
        "final_energy": float(final_energy),
        "best_observed_energy": float(final_energy),
        "reported_energy_source": "final_optimizer_objective",
        "final_parameters": final_parameters,
        "best_observed_parameters": final_parameters,
        "best_objective_evaluation": 1,
    }
    diagnostics.update(
        _objective_observation_diagnostics(
            objective,
            initial_point_evaluations=0,
            initial_point_candidates=int(
                initial_point_diagnostics.get("initial_point_candidates", 0) or 0
            ),
            optimizer_start_count=0,
        )
    )
    _update_vqe_truth_diagnostics(diagnostics, objective_state=objective, converged=True)
    artifacts = build_circuit_artifacts_fn(
        ansatz=ansatz,
        ansatz_name=ansatz_name,
        optimizer_name=optimizer_name,
        reps=reps,
        optimal_point=initial_point,
        final_point=initial_point,
        reported_energy_source="final_optimizer_objective",
    )
    _attach_reference_descriptor(
        diagnostics,
        artifacts=artifacts,
        ansatz_name=ansatz_name,
        include_statevector_data=include_statevector_data,
        energy=final_energy,
    )
    return VQEResult(
        algorithm="vqe",
        primary_energy=final_energy,
        primary_iterations=1,
        converged=True,
        optimal_parameters=[],
        convergence_trace=[final_energy],
        optimizer_diagnostics=diagnostics,
        bloch_vectors=bloch_vectors,
        density_matrix_real=dm_real,
        density_matrix_imag=dm_imag,
        circuit_artifacts=artifacts,
    )


def build_vqe_initial_point_limit_result(
    *,
    ansatz: Any,
    ansatz_name: str,
    optimizer_name: str,
    reps: int,
    optimizer_diagnostics: dict[str, Any],
    initial_point_diagnostics: dict[str, Any],
    best_point: np.ndarray | None,
    best_energy: float | None,
    candidate_points: list[np.ndarray],
    convergence_trace: list[float],
    exc: Exception,
    best_energy_selector_fn: BestEnergySelector,
    build_circuit_artifacts_fn: CircuitArtifactBuilder,
    objective_state: Any | None = None,
) -> VQEResult:
    """Build the early-stop result when warm-start selection hits the eval cap."""
    initial_point = best_point if best_point is not None else candidate_points[0]
    final_energy = best_energy_selector_fn(best_energy, convergence_trace)
    selected_parameters = [float(value) for value in np.asarray(initial_point, dtype=float)]
    best_objective_evaluation = int(np.argmin(convergence_trace)) + 1 if convergence_trace else None
    diagnostics = {
        **optimizer_diagnostics,
        **initial_point_diagnostics,
        "success": False,
        "termination_reason": "max_function_evaluations",
        "message": str(exc),
        "function_evaluations": len(convergence_trace),
        "objective_evaluations": len(convergence_trace),
        "optimizer_iterations": 0,
        "final_energy": float(final_energy),
        "best_observed_energy": float(final_energy),
        "reported_energy_source": "best_observed_optimizer_evaluation",
        "final_parameters": selected_parameters,
        "best_observed_parameters": selected_parameters,
        "best_objective_evaluation": best_objective_evaluation,
    }
    if objective_state is not None:
        diagnostics.update(
            _objective_observation_diagnostics(
                objective_state,
                initial_point_evaluations=int(
                    initial_point_diagnostics.get("initial_point_selection_evaluations", 0)
                    or 0
                ),
                initial_point_candidates=int(
                    initial_point_diagnostics.get("initial_point_candidates", 0) or 0
                ),
                optimizer_start_count=0,
            )
        )
        _update_vqe_truth_diagnostics(
            diagnostics,
            objective_state=objective_state,
            converged=False,
        )
    artifacts = build_circuit_artifacts_fn(
        ansatz=ansatz,
        ansatz_name=ansatz_name,
        optimizer_name=optimizer_name,
        reps=reps,
        optimal_point=np.asarray(initial_point, dtype=float),
        final_point=np.asarray(initial_point, dtype=float),
        reported_energy_source="best_observed_optimizer_evaluation",
    )
    _attach_reference_descriptor(
        diagnostics,
        artifacts=artifacts,
        ansatz_name=ansatz_name,
        include_statevector_data=False,
        energy=final_energy,
    )
    return VQEResult(
        algorithm="vqe",
        primary_energy=final_energy,
        primary_iterations=max(len(convergence_trace), 1),
        converged=False,
        optimal_parameters=selected_parameters,
        convergence_trace=convergence_trace or [final_energy],
        optimizer_diagnostics=diagnostics,
        circuit_artifacts=artifacts,
    )


def reported_vqe_energy_source(
    *,
    final_energy: float,
    best_observed_energy: float,
    final_point: np.ndarray,
    reported_point: np.ndarray,
) -> str:
    """Return the persisted VQE energy-source label."""
    same_energy = bool(
        np.isfinite(final_energy)
        and np.isfinite(best_observed_energy)
        and abs(float(final_energy) - best_observed_energy) <= 1e-12
    )
    same_point = reported_point.shape == final_point.shape and np.allclose(
        reported_point, final_point, atol=1e-12, rtol=0.0
    )
    if same_energy and same_point:
        return "final_optimizer_objective"
    return "best_observed_optimizer_evaluation"


def build_vqe_result(
    *,
    ansatz: Any,
    ansatz_name: str,
    optimizer_name: str,
    reps: int,
    num_qubits: int,
    include_statevector_data: bool,
    optimal_point: np.ndarray,
    final_energy: float,
    iterations: int,
    converged: bool,
    objective_state: Any,
    optimizer_diagnostics: dict[str, Any],
    **result_dependencies: Any,
) -> VQEResult:
    """Build the canonical VQE result after optimizer execution."""
    compute_state_data_fn = result_dependencies["compute_state_data_fn"]
    build_circuit_artifacts_fn = result_dependencies["build_circuit_artifacts_fn"]
    convergence_trace = objective_state.convergence_trace
    if not convergence_trace:
        convergence_trace = [final_energy]
    iterations = max(len(convergence_trace), iterations, 1)
    optimizer_diagnostics["function_evaluations"] = len(convergence_trace)
    optimizer_diagnostics["objective_evaluations"] = len(convergence_trace)
    optimizer_diagnostics.setdefault("optimizer_iterations", None)
    optimizer_diagnostics["reported_iterations"] = iterations
    optimizer_diagnostics["reported_iterations_unit"] = "objective_evaluations"
    if len(convergence_trace) >= 2:
        optimizer_diagnostics["final_delta_energy"] = float(
            abs(convergence_trace[-1] - convergence_trace[-2])
        )

    optimizer_diagnostics.update(
        _objective_observation_diagnostics(
            objective_state,
            initial_point_evaluations=int(
                optimizer_diagnostics.get("initial_point_selection_evaluations", 0) or 0
            ),
            initial_point_candidates=int(
                optimizer_diagnostics.get("initial_point_candidates", 0) or 0
            ),
            warm_start_retry_count=int(optimizer_diagnostics.get("warm_start_retry_count", 0) or 0),
            optimizer_start_count=1
            + int(optimizer_diagnostics.get("warm_start_retry_count", 0) or 0),
        )
    )

    best_observed_energy = (
        float(objective_state.best_energy)
        if objective_state.best_energy is not None
        else float(final_energy)
    )
    final_point = np.asarray(optimal_point, dtype=float)
    reported_point = np.asarray(
        objective_state.best_point if objective_state.best_point is not None else optimal_point,
        dtype=float,
    )
    best_objective_evaluation = int(np.argmin(convergence_trace)) + 1 if convergence_trace else None
    reported_energy_source = reported_vqe_energy_source(
        final_energy=final_energy,
        best_observed_energy=best_observed_energy,
        final_point=final_point,
        reported_point=reported_point,
    )
    optimizer_diagnostics["final_energy"] = float(final_energy)
    optimizer_diagnostics["best_observed_energy"] = best_observed_energy
    optimizer_diagnostics["reported_energy_source"] = reported_energy_source
    optimizer_diagnostics["final_parameters"] = [float(value) for value in final_point]
    optimizer_diagnostics["best_observed_parameters"] = [float(value) for value in reported_point]
    optimizer_diagnostics["best_objective_evaluation"] = best_objective_evaluation
    _update_vqe_truth_diagnostics(
        optimizer_diagnostics,
        objective_state=objective_state,
        converged=converged,
    )

    logger.info(
        "VQE finished: energy=%.8f final_energy=%.8f converged=%s iterations=%d optimizer=%s",
        best_observed_energy,
        final_energy,
        converged,
        iterations,
        optimizer_name,
    )

    if include_statevector_data:
        bloch_vectors, dm_real, dm_imag = compute_state_data_fn(
            ansatz,
            reported_point,
            num_qubits,
        )
    else:
        bloch_vectors = dm_real = dm_imag = None

    artifacts = build_circuit_artifacts_fn(
        ansatz=ansatz,
        ansatz_name=ansatz_name,
        optimizer_name=optimizer_name,
        reps=reps,
        optimal_point=reported_point,
        final_point=final_point,
        reported_energy_source=reported_energy_source,
    )
    _attach_reference_descriptor(
        optimizer_diagnostics,
        artifacts=artifacts,
        ansatz_name=ansatz_name,
        include_statevector_data=include_statevector_data,
        energy=best_observed_energy,
    )
    return VQEResult(
        algorithm="vqe",
        primary_energy=best_observed_energy,
        primary_iterations=iterations,
        converged=converged,
        optimal_parameters=[float(value) for value in reported_point],
        convergence_trace=convergence_trace,
        optimizer_diagnostics=optimizer_diagnostics,
        bloch_vectors=bloch_vectors,
        density_matrix_real=dm_real,
        density_matrix_imag=dm_imag,
        circuit_artifacts=artifacts,
    )


__all__ = [
    "BestEnergySelector",
    "CircuitArtifactBuilder",
    "StateDataBuilder",
    "build_parameterless_vqe_result",
    "build_vqe_initial_point_limit_result",
    "build_vqe_result",
    "reported_vqe_energy_source",
]
