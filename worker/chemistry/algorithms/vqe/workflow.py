"""VQE workflow orchestration."""

from __future__ import annotations

import logging
import time
from typing import Any

import numpy as np
from qiskit.quantum_info import SparsePauliOp
from scipy.optimize import minimize

from worker.chemistry.algorithms.vqe import circuit_artifacts as _vqe_circuit_artifacts
from worker.chemistry.algorithms.vqe import objective as _vqe_objective
from worker.chemistry.algorithms.vqe import spsa as _vqe_spsa
from worker.chemistry.algorithms.vqe import state_data as _vqe_state_data
from worker.chemistry.algorithms.vqe.config import (
    resolve_parameter_bounds,
    resolve_vqe_config,
    select_vqe_execution_policy,
    select_vqe_optimizer_name,
)
from worker.chemistry.algorithms.vqe.initial_point import (
    _build_initial_point_candidates,
    _select_initial_point,
)
from worker.chemistry.algorithms.vqe.objective import (
    evaluate_energy as _evaluate_energy,
)
from worker.chemistry.algorithms.vqe.objective import (
    evaluate_energy_with_uncertainty as _evaluate_energy_with_uncertainty,
)
from worker.chemistry.algorithms.vqe.results import (
    build_parameterless_vqe_result,
    build_vqe_initial_point_limit_result,
    build_vqe_result,
    reported_vqe_energy_source,
)
from worker.chemistry.algorithms.vqe.retry import (
    retry_stationary_warm_start as _retry_stationary_warm_start_impl,
)
from worker.chemistry.algorithms.vqe.retry import (
    run_scipy_vqe_with_retry,
    should_retry_stationary_warm_start,
    warm_start_retry_indices,
)
from worker.chemistry.algorithms.vqe.scipy import (
    best_or_latest_energy,
    run_scipy_vqe_optimizer,
)
from worker.chemistry.algorithms.vqe.state_data import (
    compute_quantum_state_data as _compute_quantum_state_data,
)
from worker.chemistry.algorithms.vqe.state_data import (
    sector_diagnostics_from_ansatz as _sector_diagnostics_from_ansatz,
)
from worker.chemistry.algorithms.vqe.state_data import (
    should_compute_statevector_data as _should_compute_statevector_data,
)
from worker.chemistry.algorithms.vqe.telemetry import (
    FunctionEvaluationLimitReached,
    VQEObjectiveState,
)
from worker.chemistry.ansatz_registry import build_ansatz
from worker.chemistry.optimizer_registry import build_optimizer
from worker.chemistry.progress import ProgressCallback
from worker.chemistry.solver_utils import resolve_algorithm_config
from worker.chemistry.types import VQEResult

logger = logging.getLogger(__name__)

_extract_pub_energy = _vqe_objective.extract_pub_energy
_bloch_vectors_from_statevector = _vqe_state_data.bloch_vectors_from_statevector


def _resolve_operator_and_width(hamiltonian: object) -> tuple[SparsePauliOp, int]:
    """Resolve a SparsePauliOp from current rollout Hamiltonian input shapes."""
    pauli = getattr(hamiltonian, "pauli_hamiltonian", None)
    if isinstance(pauli, SparsePauliOp):
        num_qubits = pauli.num_qubits
        if not isinstance(num_qubits, int):
            raise ValueError("Resolved VQE operator has invalid qubit width")
        return pauli, num_qubits

    if isinstance(hamiltonian, SparsePauliOp):
        num_qubits = hamiltonian.num_qubits
        if not isinstance(num_qubits, int):
            raise ValueError("Resolved VQE operator has invalid qubit width")
        return hamiltonian, num_qubits

    raise ValueError(
        "Unable to resolve VQE operator from hamiltonian; expected "
        "HamiltonianBundle.pauli_hamiltonian or SparsePauliOp."
    )


_is_delta_converged = _vqe_spsa.is_delta_converged
_run_spsa = _vqe_spsa.run_spsa
_build_vqe_circuit_artifacts = _vqe_circuit_artifacts.build_vqe_circuit_artifacts


def _run_parameterless_vqe(
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
) -> VQEResult:
    """Keep the legacy parameterless VQE result helper import-compatible."""
    return build_parameterless_vqe_result(
        objective=objective,
        initial_point=initial_point,
        include_statevector_data=include_statevector_data,
        ansatz=ansatz,
        num_qubits=num_qubits,
        optimizer_diagnostics=optimizer_diagnostics,
        initial_point_diagnostics=initial_point_diagnostics,
        ansatz_name=ansatz_name,
        optimizer_name=optimizer_name,
        reps=reps,
        compute_state_data_fn=_compute_quantum_state_data,
        build_circuit_artifacts_fn=_build_vqe_circuit_artifacts,
    )


def _build_vqe_initial_point_limit_result(
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
    objective_state: VQEObjectiveState | None = None,
) -> VQEResult:
    """Keep the legacy VQE limit-result helper import-compatible."""
    return build_vqe_initial_point_limit_result(
        ansatz=ansatz,
        ansatz_name=ansatz_name,
        optimizer_name=optimizer_name,
        reps=reps,
        optimizer_diagnostics=optimizer_diagnostics,
        initial_point_diagnostics=initial_point_diagnostics,
        best_point=best_point,
        best_energy=best_energy,
        candidate_points=candidate_points,
        convergence_trace=convergence_trace,
        exc=exc,
        objective_state=objective_state,
        best_energy_selector_fn=best_or_latest_energy,
        build_circuit_artifacts_fn=_build_vqe_circuit_artifacts,
    )


def _run_scipy_vqe_optimizer(
    *,
    objective: Any,
    initial_point: np.ndarray,
    optimizer: Any,
    optimizer_diagnostics: dict[str, Any],
    convergence_trace: list[float],
    parameter_bounds: list[tuple[float, float]] | None,
    best_point_getter: Any,
    best_energy_getter: Any,
) -> tuple[np.ndarray, float, int, bool, dict[str, Any]]:
    """Run the scipy-backed VQE optimization path."""
    return run_scipy_vqe_optimizer(
        objective=objective,
        initial_point=initial_point,
        optimizer=optimizer,
        optimizer_diagnostics=optimizer_diagnostics,
        convergence_trace=convergence_trace,
        parameter_bounds=parameter_bounds,
        best_point_getter=best_point_getter,
        best_energy_getter=best_energy_getter,
        minimize_fn=minimize,
    )


def _should_retry_stationary_warm_start(
    *,
    optimizer: Any,
    initial_point: np.ndarray,
    candidate_points: list[np.ndarray],
    converged: bool,
    optimizer_diagnostics: dict[str, Any],
) -> bool:
    """Keep the legacy VQE retry-policy import compatible."""
    return should_retry_stationary_warm_start(
        optimizer=optimizer,
        initial_point=initial_point,
        candidate_points=candidate_points,
        converged=converged,
        optimizer_diagnostics=optimizer_diagnostics,
    )


def _warm_start_retry_indices(
    *,
    candidate_points: list[np.ndarray],
    selected_initial_diagnostics: dict[str, Any],
) -> list[int]:
    """Keep the legacy warm-start ordering import compatible."""
    return warm_start_retry_indices(
        candidate_points=candidate_points,
        selected_initial_diagnostics=selected_initial_diagnostics,
    )


def _retry_stationary_warm_start(
    *,
    objective: VQEObjectiveState,
    optimizer: Any,
    optimizer_diagnostics: dict[str, Any],
    convergence_trace: list[float],
    parameter_bounds: list[tuple[float, float]] | None,
    candidate_points: list[np.ndarray],
    selected_initial_diagnostics: dict[str, Any],
    current_result: tuple[np.ndarray, float, int, bool, dict[str, Any]],
    run_optimizer_fn: Any | None = None,
) -> tuple[np.ndarray, float, int, bool, dict[str, Any]]:
    """Keep the legacy VQE retry helper import compatible."""
    return _retry_stationary_warm_start_impl(
        objective=objective,
        optimizer=optimizer,
        optimizer_diagnostics=optimizer_diagnostics,
        convergence_trace=convergence_trace,
        parameter_bounds=parameter_bounds,
        candidate_points=candidate_points,
        selected_initial_diagnostics=selected_initial_diagnostics,
        current_result=current_result,
        run_optimizer_fn=run_optimizer_fn or _run_scipy_vqe_optimizer,
    )


def _run_scipy_vqe_with_retry(
    *,
    objective: VQEObjectiveState,
    initial_point: np.ndarray,
    optimizer: Any,
    optimizer_diagnostics: dict[str, Any],
    convergence_trace: list[float],
    parameter_bounds: list[tuple[float, float]] | None,
    candidate_points: list[np.ndarray],
    selected_initial_diagnostics: dict[str, Any],
) -> tuple[np.ndarray, float, int, bool, dict[str, Any]]:
    return run_scipy_vqe_with_retry(
        objective=objective,
        initial_point=initial_point,
        optimizer=optimizer,
        optimizer_diagnostics=optimizer_diagnostics,
        convergence_trace=convergence_trace,
        parameter_bounds=parameter_bounds,
        candidate_points=candidate_points,
        selected_initial_diagnostics=selected_initial_diagnostics,
        run_optimizer_fn=_run_scipy_vqe_optimizer,
        should_retry_fn=_should_retry_stationary_warm_start,
        retry_fn=_retry_stationary_warm_start,
    )


def _select_initial_point_or_limit_result(
    *,
    objective: VQEObjectiveState,
    candidate_points: list[np.ndarray],
    ansatz: Any,
    ansatz_name: str,
    optimizer_name: str,
    reps: int,
    optimizer_diagnostics: dict[str, Any],
    initial_point_diagnostics: dict[str, Any],
) -> tuple[np.ndarray, dict[str, Any]] | VQEResult:
    try:
        initial_point, selected_initial_diagnostics = _select_initial_point(
            objective=objective,
            candidates=candidate_points,
        )
    except FunctionEvaluationLimitReached as exc:
        return _build_vqe_initial_point_limit_result(
            ansatz=ansatz,
            ansatz_name=ansatz_name,
            optimizer_name=optimizer_name,
            reps=reps,
            optimizer_diagnostics=optimizer_diagnostics,
            initial_point_diagnostics=initial_point_diagnostics,
            best_point=objective.best_point,
            best_energy=objective.best_energy,
            candidate_points=candidate_points,
            convergence_trace=objective.convergence_trace,
            exc=exc,
            objective_state=objective,
        )
    merged_diagnostics = {
        **optimizer_diagnostics,
        **initial_point_diagnostics,
        **selected_initial_diagnostics,
    }
    return initial_point, merged_diagnostics


def _optimize_vqe(
    *,
    objective: VQEObjectiveState,
    initial_point: np.ndarray,
    optimizer: Any,
    optimizer_name: str,
    optimizer_diagnostics: dict[str, Any],
    convergence_threshold: float,
    seed: Any,
    convergence_trace: list[float],
    parameter_bounds: list[tuple[float, float]] | None,
    candidate_points: list[np.ndarray],
    selected_initial_diagnostics: dict[str, Any],
) -> tuple[np.ndarray, float, int, bool, dict[str, Any]]:
    if optimizer.kind == "scipy":
        return _run_scipy_vqe_with_retry(
            objective=objective,
            initial_point=initial_point,
            optimizer=optimizer,
            optimizer_diagnostics=optimizer_diagnostics,
            convergence_trace=convergence_trace,
            parameter_bounds=parameter_bounds,
            candidate_points=candidate_points,
            selected_initial_diagnostics=selected_initial_diagnostics,
        )
    if optimizer.kind == "spsa":
        return _run_spsa_vqe_optimizer(
            objective=objective,
            initial_point=initial_point,
            optimizer=optimizer,
            optimizer_name=optimizer_name,
            optimizer_diagnostics=optimizer_diagnostics,
            convergence_threshold=convergence_threshold,
            seed=seed,
            convergence_trace=convergence_trace,
            parameter_bounds=parameter_bounds,
            evaluation_count_getter=lambda: objective.evaluation_count,
            best_point_getter=lambda: objective.best_point,
            best_energy_getter=lambda: objective.best_energy,
        )
    raise ValueError(f"Unsupported optimizer kind '{optimizer.kind}'")


def _run_spsa_vqe_optimizer(
    *,
    objective: Any,
    initial_point: np.ndarray,
    optimizer: Any,
    optimizer_name: str,
    optimizer_diagnostics: dict[str, Any],
    convergence_threshold: float,
    seed: Any,
    convergence_trace: list[float],
    parameter_bounds: list[tuple[float, float]] | None,
    evaluation_count_getter: Any,
    best_point_getter: Any,
    best_energy_getter: Any,
) -> tuple[np.ndarray, float, int, bool, dict[str, Any]]:
    """Run the SPSA-backed VQE optimization path."""
    base_optimizer_diagnostics = optimizer_diagnostics
    try:
        optimal_point, iterations, converged, spsa_diagnostics = _run_spsa(
            objective=objective,
            initial_point=initial_point,
            max_iterations=optimizer.max_iterations,
            options=optimizer.options,
            threshold=convergence_threshold,
            seed=seed if isinstance(seed, int) else None,
            convergence_trace=convergence_trace,
            parameter_bounds=parameter_bounds,
        )
        optimizer_diagnostics = {
            "optimizer_name": optimizer_name,
            **base_optimizer_diagnostics,
            **spsa_diagnostics,
        }
        if (
            optimizer.max_function_evaluations is None
            or int(evaluation_count_getter()) < optimizer.max_function_evaluations
        ):
            final_energy = float(objective(optimal_point))
        else:
            final_energy = best_or_latest_energy(best_energy_getter(), convergence_trace)
        return optimal_point, final_energy, iterations, converged, optimizer_diagnostics
    except FunctionEvaluationLimitReached as exc:
        best_point = best_point_getter()
        optimal_point = best_point if best_point is not None else initial_point
        return (
            optimal_point,
            best_or_latest_energy(best_energy_getter(), convergence_trace),
            max(len(convergence_trace), 1),
            False,
            {
                "optimizer_name": optimizer_name,
                **base_optimizer_diagnostics,
                "success": False,
                "termination_reason": "max_function_evaluations",
                "message": str(exc),
                "function_evaluations": len(convergence_trace),
                "objective_evaluations": len(convergence_trace),
                "optimizer_iterations": None,
            },
        )


def _build_vqe_result(
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
    objective_state: VQEObjectiveState,
    optimizer_diagnostics: dict[str, Any],
) -> VQEResult:
    """Keep the legacy canonical VQE result helper import-compatible."""
    return build_vqe_result(
        ansatz=ansatz,
        ansatz_name=ansatz_name,
        optimizer_name=optimizer_name,
        reps=reps,
        num_qubits=num_qubits,
        include_statevector_data=include_statevector_data,
        optimal_point=optimal_point,
        final_energy=final_energy,
        iterations=iterations,
        converged=converged,
        objective_state=objective_state,
        optimizer_diagnostics=optimizer_diagnostics,
        compute_state_data_fn=_compute_quantum_state_data,
        build_circuit_artifacts_fn=_build_vqe_circuit_artifacts,
    )


def _reported_vqe_energy_source(
    *,
    final_energy: float,
    best_observed_energy: float,
    final_point: np.ndarray,
    reported_point: np.ndarray,
) -> str:
    """Keep the legacy VQE energy-source helper import-compatible."""
    return reported_vqe_energy_source(
        final_energy=final_energy,
        best_observed_energy=best_observed_energy,
        final_point=final_point,
        reported_point=reported_point,
    )


def _update_independent_reevaluation(
    *,
    diagnostics: dict[str, Any],
    objective: VQEObjectiveState,
    backend: Any,
    ansatz: Any,
    operator: Any,
    optimal_point: np.ndarray,
    final_energy: float,
    include_statevector_data: bool,
) -> None:
    reevaluation_mode = "exact_statevector" if include_statevector_data else "estimator_backend"
    max_evaluations = objective.max_function_evaluations
    if max_evaluations is not None and objective.evaluation_count >= max_evaluations:
        diagnostics.update(
            {
                "independent_final_energy": None,
                "independent_reevaluation_status": "skipped_max_function_evaluations",
                "independent_reevaluation_mode": reevaluation_mode,
                "independent_final_standard_error": None,
                "independent_uncertainty_status": "skipped_max_function_evaluations",
            }
        )
        return
    # Count the submission before evaluating it, including backend failures.
    objective.final_reevaluation_count += 1
    try:
        independent_final_energy, independent_standard_error = _evaluate_energy_with_uncertainty(
            backend=backend,
            ansatz=ansatz,
            operator=operator,
            parameter_values=np.asarray(optimal_point, dtype=float),
        )
        diagnostics.update(
            {
                "independent_final_energy": independent_final_energy,
                "independent_reevaluation_status": "completed",
                "independent_reevaluation_mode": reevaluation_mode,
                "independent_reevaluation_delta": float(
                    abs(independent_final_energy - float(final_energy))
                ),
                "independent_final_standard_error": independent_standard_error,
                "independent_uncertainty_status": (
                    "available"
                    if independent_standard_error is not None
                    else "unavailable_from_backend"
                ),
            }
        )
    except Exception as exc:  # pragma: no cover - backend failures are runtime-specific
        diagnostics.update(
            {
                "independent_final_energy": None,
                "independent_reevaluation_status": "failed",
                "independent_reevaluation_mode": reevaluation_mode,
                "independent_reevaluation_error": exc.__class__.__name__,
                "independent_final_standard_error": None,
                "independent_uncertainty_status": "failed",
            }
        )


def _update_sector_diagnostics(
    diagnostics: dict[str, Any],
    *,
    hamiltonian: object,
    ansatz: Any,
    parameter_point: np.ndarray,
) -> None:
    if not all(
        isinstance(getattr(hamiltonian, name, None), int)
        for name in ("num_spatial_orbitals", "num_electrons_alpha", "num_electrons_beta")
    ):
        return
    diagnostics.update(
        _sector_diagnostics_from_ansatz(
            ansatz,
            parameter_point,
            num_spatial_orbitals=int(hamiltonian.num_spatial_orbitals),
            num_electrons_alpha=int(hamiltonian.num_electrons_alpha),
            num_electrons_beta=int(hamiltonian.num_electrons_beta),
        )
    )


def run_vqe(
    *,
    hamiltonian: object,
    backend: Any,
    config: dict[str, Any],
    progress_callback: ProgressCallback | None = None,
    backend_context: Any | None = None,
) -> VQEResult:
    """Run VQE using scipy/SPSA optimizers and Qiskit V2 estimator PUBs."""
    resolved = resolve_algorithm_config(config, "vqe")
    vqe_config = resolve_vqe_config(resolved)
    optimizer_name, optimizer_selection_reason = select_vqe_optimizer_name(
        resolved,
        optimizer_policy=vqe_config.optimizer_policy,
        backend_target=getattr(backend_context, "backend_target", None),
        noise_profile=getattr(backend_context, "noise_profile", None),
    )
    execution_policy, execution_policy_selection_reason = select_vqe_execution_policy(
        backend_target=getattr(backend_context, "backend_target", None),
        noise_profile=getattr(backend_context, "noise_profile", None),
    )

    operator, num_qubits = _resolve_operator_and_width(hamiltonian)
    statevector_context = {**config, **resolved}
    include_statevector_data = _should_compute_statevector_data(backend, statevector_context)
    if not hasattr(backend, "run"):
        raise ValueError(
            "VQE backend must provide a run() method compatible with estimator primitives"
        )

    ansatz = build_ansatz(
        ansatz_name=vqe_config.ansatz_name,
        num_qubits=num_qubits,
        reps=vqe_config.reps,
        num_electrons_alpha=getattr(hamiltonian, "num_electrons_alpha", None),
        num_electrons_beta=getattr(hamiltonian, "num_electrons_beta", None),
    )
    optimizer = build_optimizer(
        optimizer_name=optimizer_name,
        max_iterations=vqe_config.max_iterations,
        minimum_iterations=ansatz.num_parameters + 2,
        max_function_evaluations=vqe_config.max_function_evaluations,
        optimizer_options=(
            vqe_config.optimizer_options if isinstance(vqe_config.optimizer_options, dict) else None
        ),
    )

    pauli_terms = len(operator) if hasattr(operator, "__len__") else "?"
    logger.info(
        "VQE setup: ansatz=%s optimizer=%s num_qubits=%d parameters=%d "
        "max_iterations=%d max_function_evaluations=%s pauli_terms=%s",
        vqe_config.ansatz_name,
        optimizer_name,
        num_qubits,
        ansatz.num_parameters,
        optimizer.max_iterations,
        optimizer.max_function_evaluations,
        pauli_terms,
    )

    requested_optimizer_max_function_evaluations = None
    if isinstance(vqe_config.optimizer_options, dict):
        raw_maxfun = vqe_config.optimizer_options.get("maxfun")
        if isinstance(raw_maxfun, (int, float)) and not isinstance(raw_maxfun, bool):
            requested_optimizer_max_function_evaluations = int(raw_maxfun)
    effective_optimizer_max_function_evaluations = (
        optimizer.options.get("maxfun") if isinstance(optimizer.options, dict) else None
    )
    optimizer_function_limit_source = (
        "native_optimizer"
        if effective_optimizer_max_function_evaluations is not None
        else "objective_callback"
    )
    budget_limit_warning = None
    if (
        optimizer.max_function_evaluations is not None
        and effective_optimizer_max_function_evaluations is None
        and optimizer.max_iterations < optimizer.max_function_evaluations
    ):
        budget_limit_warning = (
            "The optimizer maxiter limit is lower than the generic objective "
            "evaluation limit; maxiter is the effective limiter."
        )
        logger.warning(
            "%s optimizer=%s maxiter=%d objective_limit=%d",
            budget_limit_warning,
            optimizer.name,
            optimizer.max_iterations,
            optimizer.max_function_evaluations,
        )

    optimizer_diagnostics: dict[str, Any] = {
        "optimizer_kind": optimizer.kind,
        "optimizer_name": optimizer.name,
        "requested_optimizer_name": resolved.get("optimizer_name") or resolved.get("optimizer"),
        "optimizer_policy": vqe_config.optimizer_policy,
        "optimizer_selection_reason": optimizer_selection_reason,
        "execution_policy": execution_policy,
        "execution_policy_selection_reason": execution_policy_selection_reason,
        "seed": vqe_config.seed if isinstance(vqe_config.seed, int) else 42,
        "effective_max_iterations": optimizer.max_iterations,
        "requested_max_iterations": vqe_config.max_iterations,
        "requested_optimizer_max_iterations": vqe_config.max_iterations,
        "effective_optimizer_max_iterations": optimizer.max_iterations,
        "max_function_evaluations": optimizer.max_function_evaluations,
        "requested_max_function_evaluations": vqe_config.max_function_evaluations,
        "effective_max_function_evaluations": optimizer.max_function_evaluations,
        "requested_objective_max_function_evaluations": (
            vqe_config.max_function_evaluations
        ),
        "effective_objective_max_function_evaluations": optimizer.max_function_evaluations,
        "optimizer_max_function_evaluations": effective_optimizer_max_function_evaluations,
        "requested_optimizer_max_function_evaluations": (
            requested_optimizer_max_function_evaluations
        ),
        "effective_optimizer_max_function_evaluations": (
            effective_optimizer_max_function_evaluations
        ),
        "optimizer_function_limit_source": optimizer_function_limit_source,
        "budget_limit_warning": budget_limit_warning,
        "optimizer_options": optimizer.options or {},
        "convergence_threshold": vqe_config.convergence_threshold,
        "convergence_threshold_policy": "absolute_energy_delta",
    }

    def evaluate_energy(parameter_values: np.ndarray) -> tuple[float, float | None] | float:
        # Keep the legacy solver seam usable for local integrations that
        # replace ``_evaluate_energy``. The production path obtains the
        # uncertainty from this same primitive submission.
        if _evaluate_energy is not _vqe_objective.evaluate_energy:
            return _evaluate_energy(
                backend=backend,
                ansatz=ansatz,
                operator=operator,
                parameter_values=parameter_values,
            )
        return _evaluate_energy_with_uncertainty(
            backend=backend,
            ansatz=ansatz,
            operator=operator,
            parameter_values=parameter_values,
        )

    objective_state = VQEObjectiveState(
        energy_evaluator=evaluate_energy,
        progress_callback=progress_callback,
        ansatz_name=vqe_config.ansatz_name,
        optimizer_name=optimizer.name,
        optimizer_kind=optimizer.kind,
        max_iterations=optimizer.max_iterations,
        max_function_evaluations=optimizer.max_function_evaluations,
        parameter_count=ansatz.num_parameters,
        num_qubits=num_qubits,
        shots=(
            int(getattr(backend_context, "shots"))
            if isinstance(getattr(backend_context, "shots", None), (int, float))
            and not isinstance(getattr(backend_context, "shots", None), bool)
            else None
        ),
    )

    parameter_bounds = resolve_parameter_bounds(
        resolved,
        num_parameters=ansatz.num_parameters,
    )
    candidate_points, initial_point_diagnostics = _build_initial_point_candidates(
        resolved,
        num_parameters=ansatz.num_parameters,
        seed=vqe_config.seed if isinstance(vqe_config.seed, int) else 42,
        parameter_bounds=parameter_bounds,
    )
    sector_metadata = {
        key: value
        for key, value in (
            {
                "sector_target": None,
                "ideal_sector_probability": None,
                "ideal_sector_leakage": None,
                "sector_diagnostic_source": None,
            }
            if not all(
                isinstance(getattr(hamiltonian, name, None), int)
                for name in (
                    "num_spatial_orbitals",
                    "num_electrons_alpha",
                    "num_electrons_beta",
                )
            )
            else _sector_diagnostics_from_ansatz(
                ansatz,
                candidate_points[0],
                num_spatial_orbitals=int(hamiltonian.num_spatial_orbitals),
                num_electrons_alpha=int(hamiltonian.num_electrons_alpha),
                num_electrons_beta=int(hamiltonian.num_electrons_beta),
            )
        ).items()
    }
    optimizer_diagnostics.update(sector_metadata)
    if ansatz.num_parameters == 0:
        return _run_parameterless_vqe(
            objective=objective_state,
            initial_point=candidate_points[0],
            include_statevector_data=include_statevector_data,
            ansatz=ansatz,
            num_qubits=num_qubits,
            optimizer_diagnostics=optimizer_diagnostics,
            initial_point_diagnostics=initial_point_diagnostics,
            ansatz_name=vqe_config.ansatz_name,
            optimizer_name=optimizer.name,
            reps=vqe_config.reps,
        )

    selected_initial_point = _select_initial_point_or_limit_result(
        objective=objective_state,
        candidate_points=candidate_points,
        ansatz=ansatz,
        ansatz_name=vqe_config.ansatz_name,
        optimizer_name=optimizer.name,
        reps=vqe_config.reps,
        optimizer_diagnostics=optimizer_diagnostics,
        initial_point_diagnostics=initial_point_diagnostics,
    )
    if isinstance(selected_initial_point, VQEResult):
        return selected_initial_point

    initial_point, optimizer_diagnostics = selected_initial_point
    selected_initial_diagnostics = {
        key: value
        for key, value in optimizer_diagnostics.items()
        if key.startswith("initial_point_")
    }
    objective_state.optimizer_started_at = time.monotonic()
    try:
        optimal_point, final_energy, iterations, converged, optimizer_diagnostics = _optimize_vqe(
            objective=objective_state,
            initial_point=initial_point,
            optimizer=optimizer,
            optimizer_name=optimizer.name,
            optimizer_diagnostics=optimizer_diagnostics,
            convergence_threshold=vqe_config.convergence_threshold,
            seed=vqe_config.seed,
            convergence_trace=objective_state.convergence_trace,
            parameter_bounds=parameter_bounds,
            candidate_points=candidate_points,
            selected_initial_diagnostics=selected_initial_diagnostics,
        )
    finally:
        objective_state.optimizer_finished_at = time.monotonic()
    _update_independent_reevaluation(
        diagnostics=optimizer_diagnostics,
        objective=objective_state,
        backend=backend,
        ansatz=ansatz,
        operator=operator,
        optimal_point=optimal_point,
        final_energy=final_energy,
        include_statevector_data=include_statevector_data,
    )
    _update_sector_diagnostics(
        optimizer_diagnostics,
        hamiltonian=hamiltonian,
        ansatz=ansatz,
        parameter_point=optimal_point,
    )

    return _build_vqe_result(
        ansatz=ansatz,
        ansatz_name=vqe_config.ansatz_name,
        optimizer_name=optimizer.name,
        reps=vqe_config.reps,
        num_qubits=num_qubits,
        include_statevector_data=include_statevector_data,
        optimal_point=optimal_point,
        final_energy=final_energy,
        iterations=iterations,
        converged=converged,
        objective_state=objective_state,
        optimizer_diagnostics=optimizer_diagnostics,
    )
