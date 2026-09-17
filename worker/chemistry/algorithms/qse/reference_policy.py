"""QSE reference-state policy and construction helpers for the algorithm package."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
from qiskit.quantum_info import Statevector

from worker.chemistry.algorithms.qse.reference import (
    normalize_reference_state_vector,
    string_option,
    vector_size_to_qubits,
)
from worker.chemistry.algorithms.vqe.workflow import run_vqe
from worker.chemistry.ansatz_registry import build_ansatz
from worker.chemistry.circuit_artifacts import retag_circuit_artifact
from worker.chemistry.hamiltonian_action import HamiltonianAction
from worker.chemistry.progress import ProgressCallback, ProgressEvent
from worker.chemistry.sector_basis import (
    hartree_fock_sector_state,
    state_from_sector_amplitudes,
)
from worker.chemistry.solver_utils import bounded_int


def _reference_vqe_cost(
    *,
    vqe_result: Any,
    ansatz_name: str,
    optimizer_name: str,
    reference_reps: int,
    execution_mode: str,
) -> dict[str, Any]:
    """Capture the measured cost of the VQE reference-state optimization."""
    diagnostics = getattr(vqe_result, "optimizer_diagnostics", {})
    diagnostics = diagnostics if isinstance(diagnostics, dict) else {}
    objective_evaluations = diagnostics.get(
        "objective_evaluations",
        diagnostics.get("function_evaluations"),
    )
    if not isinstance(objective_evaluations, int) or isinstance(objective_evaluations, bool):
        objective_evaluations = None
    optimizer_iterations = diagnostics.get("optimizer_iterations")
    if not isinstance(optimizer_iterations, int) or isinstance(optimizer_iterations, bool):
        optimizer_iterations = None
    optimizer_converged = getattr(vqe_result, "converged", None)
    if not isinstance(optimizer_converged, bool):
        optimizer_converged = None
    final_delta = diagnostics.get("final_delta_energy")
    final_delta = (
        float(final_delta)
        if isinstance(final_delta, (int, float)) and np.isfinite(float(final_delta))
        else None
    )
    threshold = diagnostics.get("convergence_threshold")
    threshold = (
        float(threshold)
        if isinstance(threshold, (int, float)) and np.isfinite(float(threshold))
        else None
    )
    scientific_converged = (
        final_delta <= threshold if final_delta is not None and threshold is not None else None
    )
    return {
        "cost_type": "vqe_reference_optimization",
        "execution_mode": execution_mode,
        "cost_status": "measured" if objective_evaluations is not None else "partial",
        "ansatz_name": ansatz_name,
        "optimizer_name": optimizer_name,
        "reps": reference_reps,
        "objective_evaluations": objective_evaluations,
        "optimizer_iterations": optimizer_iterations,
        "max_function_evaluations": diagnostics.get("max_function_evaluations"),
        "state_preparations": objective_evaluations,
        "optimizer_converged": optimizer_converged,
        "scientific_converged": scientific_converged,
        "budget_exhausted": diagnostics.get("termination_reason") == "max_function_evaluations",
        "termination_reason": diagnostics.get("termination_reason"),
        "best_observed_energy": diagnostics.get("best_observed_energy"),
        "final_energy": diagnostics.get("final_energy"),
    }


def _tag_reference_artifact(
    artifact: dict[str, Any],
    *,
    vqe_cost: dict[str, Any],
) -> dict[str, Any]:
    """Retag a reference circuit and attach the VQE cost without changing its shape."""
    tagged = retag_circuit_artifact(
        artifact,
        algorithm="qse",
        role="reference",
        source="vqe_reference",
        artifact_id_prefix="qse.reference",
        phase="reference",
        representative=True,
    )
    tagged["reference_cost"] = dict(vqe_cost)
    return tagged


def _reference_progress_callback(
    *,
    progress_callback: ProgressCallback | None,
    ansatz_name: str,
    optimizer_name: str,
    reference_iterations: int,
    reference_reps: int,
) -> Callable[[ProgressEvent], None]:
    reference_progress = {"count": 0}

    def emit(payload: ProgressEvent) -> None:
        reference_progress["count"] += 1
        if progress_callback is None:
            return
        qse_payload: dict[str, Any] = {
            "algorithm": "qse",
            "stage": "progress",
            "step": "reference_vqe",
            "iteration": reference_progress["count"],
            "completed_iterations": reference_progress["count"],
            "energy": None,
            "reference_method": "vqe",
            "reference_ansatz": ansatz_name,
            "reference_optimizer": optimizer_name,
            "reference_max_iterations": reference_iterations,
            "reference_reps": reference_reps,
        }
        energy = payload.get("energy")
        if isinstance(energy, (int, float)):
            qse_payload["energy"] = float(energy)
        progress_callback(qse_payload)

    return emit


def _reference_backend(backend: object, run_vqe_fn: Callable[..., Any]) -> tuple[object, str]:
    if run_vqe_fn is run_vqe:
        from qiskit.primitives import StatevectorEstimator

        return StatevectorEstimator(), "exact_emulation"
    return backend, "exact_emulation"


def _build_vqe_reference_state_and_artifacts(
    *,
    ansatz: Any,
    vqe_result: Any,
    vqe_cost: dict[str, Any],
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    optimal_parameters = np.asarray(vqe_result.optimal_parameters, dtype=float).reshape(-1)
    if optimal_parameters.size != ansatz.num_parameters:
        raise ValueError(
            "QSE VQE reference parameter count does not match the ansatz "
            f"(expected {ansatz.num_parameters}, received {optimal_parameters.size})"
        )
    if not np.all(np.isfinite(optimal_parameters)):
        raise ValueError("QSE VQE reference parameters must be finite")

    if ansatz.num_parameters == 0:
        state = Statevector.from_instruction(ansatz).data
        reference_artifact = next(
            (artifact for artifact in vqe_result.circuit_artifacts if artifact.get("role") == "ansatz"),
            None,
        )
        artifacts = (
            [_tag_reference_artifact(reference_artifact, vqe_cost=vqe_cost)]
            if reference_artifact is not None
            else []
        )
        return np.asarray(state, dtype=complex), artifacts

    state = Statevector.from_instruction(ansatz.assign_parameters(optimal_parameters.tolist())).data
    state = np.asarray(state, dtype=complex)
    norm = float(np.linalg.norm(state))
    if np.isclose(norm, 0.0):
        raise ValueError("QSE VQE reference solve produced a zero-norm state")
    reference_artifact = next(
        (artifact for artifact in vqe_result.circuit_artifacts if artifact.get("role") == "final"),
        None,
    )
    artifacts = (
        [_tag_reference_artifact(reference_artifact, vqe_cost=vqe_cost)]
        if reference_artifact is not None
        else []
    )
    return state / norm, artifacts


def build_vqe_reference_state(
    *,
    hamiltonian: object,
    backend: object,
    vector_size: int,
    resolved_config: dict[str, Any],
    progress_callback: ProgressCallback | None,
    run_vqe_fn: Callable[..., Any] = run_vqe,
    build_ansatz_fn: Callable[..., Any] = build_ansatz,
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    """Build a VQE-derived reference state from runtime config."""
    chemistry_sector_available = all(
        isinstance(getattr(hamiltonian, name, None), int)
        for name in ("num_spatial_orbitals", "num_electrons_alpha", "num_electrons_beta")
    ) and int(getattr(hamiltonian, "num_qubits", 0) or 0) == 2 * int(
        getattr(hamiltonian, "num_spatial_orbitals", 0) or 0
    )
    ansatz_name = string_option(
        resolved_config.get("vqe_reference_ansatz_name"),
        default="NumberPreserving" if chemistry_sector_available else "EfficientSU2",
    )
    optimizer_name = string_option(
        resolved_config.get("vqe_reference_optimizer_name"),
        default="COBYLA",
    )
    reference_reps = bounded_int(
        resolved_config.get("vqe_reference_reps"),
        default=2,
        low=1,
        high=6,
    )
    reference_iterations = bounded_int(
        resolved_config.get("vqe_reference_max_iterations"),
        default=300,
        low=1,
        high=1000,
    )

    reference_progress = _reference_progress_callback(
        progress_callback=progress_callback,
        ansatz_name=ansatz_name,
        optimizer_name=optimizer_name,
        reference_iterations=reference_iterations,
        reference_reps=reference_reps,
    )
    reference_backend, execution_mode = _reference_backend(backend, run_vqe_fn)

    vqe_result = run_vqe_fn(
        hamiltonian=hamiltonian,
        backend=reference_backend,
        config={
            "algorithm": "vqe",
            "ansatz_name": ansatz_name,
            "optimizer_name": optimizer_name,
            "max_iterations": reference_iterations,
            "reps": reference_reps,
            "initial_point_strategy": "zero_plus_seeded_random",
            "initial_point_candidates": 2,
        },
        progress_callback=reference_progress,
    )
    vqe_cost = _reference_vqe_cost(
        vqe_result=vqe_result,
        ansatz_name=ansatz_name,
        optimizer_name=optimizer_name,
        reference_reps=reference_reps,
        execution_mode=execution_mode,
    )

    num_qubits = vector_size_to_qubits(vector_size)
    ansatz = build_ansatz_fn(
        ansatz_name=ansatz_name,
        num_qubits=num_qubits,
        reps=reference_reps,
        num_electrons_alpha=getattr(hamiltonian, "num_electrons_alpha", None),
        num_electrons_beta=getattr(hamiltonian, "num_electrons_beta", None),
    )
    return _build_vqe_reference_state_and_artifacts(
        ansatz=ansatz,
        vqe_result=vqe_result,
        vqe_cost=vqe_cost,
    )


def resolve_reference_state(
    *,
    hamiltonian: object,
    backend: object,
    operator_matrix: np.ndarray,
    resolved_config: dict[str, Any],
    progress_callback: ProgressCallback | None,
    build_vqe_reference_state_fn: Callable[..., tuple[np.ndarray, list[dict[str, Any]]]],
    build_hf_reference_state_fn: Callable[..., np.ndarray],
    hf_reference_artifacts_fn: Callable[[object], list[dict[str, Any]]],
    normalize_reference_state_vector_fn: Callable[
        ..., np.ndarray
    ] = normalize_reference_state_vector,
) -> tuple[str, np.ndarray, list[dict[str, Any]]]:
    """Resolve dense QSE reference-state policy from runtime configuration."""
    reference_method = str(resolved_config.get("reference_method", "vqe")).lower()
    vector_size = operator_matrix.shape[0]

    if reference_method == "hf":
        reference_state = build_hf_reference_state_fn(hamiltonian, fallback_dim=vector_size)
        norm = float(np.linalg.norm(reference_state))
        if np.isclose(norm, 0.0):
            raise ValueError("QSE HF reference state has zero norm")
        return reference_method, reference_state / norm, hf_reference_artifacts_fn(hamiltonian)

    if reference_method == "vqe":
        reference_state, reference_artifacts = build_vqe_reference_state_fn(
            hamiltonian=hamiltonian,
            backend=backend,
            vector_size=vector_size,
            resolved_config=resolved_config,
            progress_callback=progress_callback,
        )
        return reference_method, reference_state, reference_artifacts

    if reference_method == "provided_state":
        provided_vector = resolved_config.get("provided_state_vector")
        if provided_vector is None:
            provided_vector = resolved_config.get("reference_state_vector")
        if provided_vector is None:
            provided_state = resolved_config.get("provided_state")
            if isinstance(provided_state, dict):
                provided_vector = provided_state.get("state_vector")

        if provided_vector is None:
            raise ValueError("QSE reference_method='provided_state' requires provided_state_vector")

        return (
            reference_method,
            normalize_reference_state_vector_fn(
                provided_vector,
                vector_size=vector_size,
            ),
            [],
        )

    raise ValueError(
        f"Unsupported QSE reference_method '{reference_method}'. Supported: hf, vqe, "
        "provided_state, provided_sector"
    )


def resolve_sector_reference_state(
    *,
    hamiltonian: object,
    action: HamiltonianAction,
    resolved_config: dict[str, Any],
    hf_reference_artifacts_fn: Callable[[object], list[dict[str, Any]]],
    hartree_fock_sector_state_fn: Callable[..., np.ndarray] = hartree_fock_sector_state,
    state_from_sector_amplitudes_fn: Callable[..., np.ndarray] = state_from_sector_amplitudes,
) -> tuple[str, np.ndarray, list[dict[str, Any]]]:
    """Resolve a QSE reference state in the fixed-particle sector."""
    reference_method = str(resolved_config.get("reference_method", "vqe")).lower()
    if reference_method == "hf":
        reference_state = hartree_fock_sector_state_fn(action.norb, action.nelec)
        norm = float(np.linalg.norm(reference_state))
        if np.isclose(norm, 0.0):
            raise ValueError("QSE HF sector reference state has zero norm")
        return reference_method, reference_state / norm, hf_reference_artifacts_fn(hamiltonian)

    if reference_method == "provided_sector":
        raw_amplitudes = resolved_config.get("provided_sector_amplitudes")
        if raw_amplitudes is None:
            provided_reference = resolved_config.get("provided_sector_reference")
            if isinstance(provided_reference, dict):
                raw_amplitudes = provided_reference.get("amplitudes")
        return (
            reference_method,
            state_from_sector_amplitudes_fn(
                raw_amplitudes,
                norb=action.norb,
                nelec=action.nelec,
                dimension=action.dimension,
            ),
            [],
        )

    raise ValueError(
        "QSE sector matrix-free path supports reference_method='hf' "
        "or reference_method='provided_sector'"
    )


__all__ = [
    "build_vqe_reference_state",
    "resolve_reference_state",
    "resolve_sector_reference_state",
]
