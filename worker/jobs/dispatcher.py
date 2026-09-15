"""Algorithm dispatcher for worker execution."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import numpy as np

from shared.contracts.identifiers import RunAlgorithm
from worker.adapters.base import BackendAdapter, BackendExecutionContext
from worker.chemistry.algorithms.sqd.workflow import run_sqd
from worker.chemistry.ansatz_registry import build_ansatz
from worker.chemistry.kqd_solver import run_kqd
from worker.chemistry.progress import ProgressCallback
from worker.chemistry.projected_execution import (
    ProjectedExecutionPolicy,
    QSEExecutionPolicy,
    resolve_projected_execution_policy,
    resolve_qse_execution_policy,
)
from worker.chemistry.qfd_solver import run_qfd
from worker.chemistry.qse_solver import run_qse
from worker.chemistry.skqd_solver import run_skqd
from worker.chemistry.solver_utils import resolve_algorithm_config
from worker.chemistry.types import AlgorithmResult
from worker.chemistry.vqe_solver import run_vqe
from worker.exceptions import BackendError

AlgorithmRunner = Callable[
    [
        BackendAdapter,
        dict[str, Any],
        object,
        ProgressCallback | None,
        BackendExecutionContext | None,
    ],
    AlgorithmResult,
]


class PrimitiveRequirement(StrEnum):
    """Primitive contract declared by a registered algorithm."""

    ESTIMATOR = "estimator"
    SAMPLER = "sampler"
    OPTIONAL_ESTIMATOR = "optional_estimator"
    SAMPLER_AND_OPTIONAL_ESTIMATOR = "sampler_and_optional_estimator"


@dataclass(frozen=True, slots=True)
class AlgorithmDefinition:
    """Runtime metadata and entry point for one worker algorithm."""

    algorithm: str
    runner: AlgorithmRunner
    config_namespace: str
    primitive_requirement: PrimitiveRequirement


def _run_vqe(
    backend: BackendAdapter,
    config: dict[str, Any],
    hamiltonian_bundle: object,
    progress_callback: ProgressCallback | None,
    backend_context: BackendExecutionContext | None,
) -> AlgorithmResult:
    estimator = backend.create_estimator(backend_context)
    return run_vqe(
        hamiltonian=hamiltonian_bundle,
        backend=estimator,
        config=config,
        progress_callback=progress_callback,
        backend_context=backend_context,
    )


def _run_sqd(
    backend: BackendAdapter,
    config: dict[str, Any],
    hamiltonian_bundle: object,
    progress_callback: ProgressCallback | None,
    backend_context: BackendExecutionContext | None,
) -> AlgorithmResult:
    sampler = backend.create_sampler(backend_context)
    resolved = resolve_algorithm_config(config, "sqd")
    sampling_source = str(resolved.get("sampling_state_source", "hf")).lower()
    if sampling_source not in {"hf", "vqe"}:
        raise ValueError("SQD sampling_state_source must be 'hf' or 'vqe'")
    if sampling_source == "hf":
        return run_sqd(
            hamiltonian=hamiltonian_bundle,
            backend=sampler,
            config=config,
            progress_callback=progress_callback,
            backend_context=backend_context,
        )

    estimator = backend.create_estimator(backend_context)
    ansatz_name = str(resolved.get("sampling_vqe_ansatz_name") or "NumberPreserving")
    optimizer_name = str(resolved.get("sampling_vqe_optimizer_name") or "COBYLA")
    reps = int(resolved.get("sampling_vqe_reps") or 2)
    max_iterations = int(resolved.get("sampling_vqe_max_iterations") or 120)

    def vqe_sampling_progress(payload: dict[str, Any]) -> None:
        if progress_callback is None:
            return
        progress_callback(
            {
                **payload,
                "algorithm": "sqd",
                "step": "sampling_vqe",
                "reference_algorithm": "vqe",
                "progress_phase": "reference",
                "reference_completed_iterations": payload.get("completed_iterations"),
                "reference_total_iterations": payload.get(
                    "max_function_evaluations", payload.get("max_iterations")
                ),
            }
        )

    vqe_result = run_vqe(
        hamiltonian=hamiltonian_bundle,
        backend=estimator,
        config={
            "algorithm": "vqe",
            "ansatz_name": ansatz_name,
            "optimizer_name": optimizer_name,
            "max_iterations": max_iterations,
            "max_function_evaluations": max_iterations,
            "reps": reps,
            "seed": resolved.get("sampling_vqe_seed"),
            "initial_point_strategy": "zero_plus_seeded_random",
            "initial_point_candidates": 2,
        },
        progress_callback=vqe_sampling_progress,
        backend_context=backend_context,
    )
    num_qubits = int(getattr(hamiltonian_bundle, "num_qubits"))
    ansatz = build_ansatz(
        ansatz_name=ansatz_name,
        num_qubits=num_qubits,
        reps=reps,
        num_electrons_alpha=getattr(hamiltonian_bundle, "num_electrons_alpha", None),
        num_electrons_beta=getattr(hamiltonian_bundle, "num_electrons_beta", None),
    )
    optimal_parameters = np.asarray(vqe_result.optimal_parameters, dtype=float)

    def sampling_circuit_factory(**_kwargs: Any) -> object:
        return ansatz.assign_parameters(optimal_parameters.tolist())

    return run_sqd(
        hamiltonian=hamiltonian_bundle,
        backend=sampler,
        config=config,
        progress_callback=progress_callback,
        backend_context=backend_context,
        sampling_circuit_factory=sampling_circuit_factory,
        sampling_source="vqe_correlated_state",
        sampling_provider={
            "method": "vqe",
            "state_preparation": "bound_vqe_ansatz",
            "ansatz_name": ansatz_name,
            "optimizer_name": optimizer_name,
            "reps": reps,
            "max_iterations": max_iterations,
            "max_function_evaluations": max_iterations,
            "vqe_converged": bool(vqe_result.converged),
            "vqe_energy": float(vqe_result.primary_energy),
            "vqe_ideal_sector_probability": vqe_result.optimizer_diagnostics.get(
                "ideal_sector_probability"
            ),
            "vqe_ideal_sector_leakage": vqe_result.optimizer_diagnostics.get(
                "ideal_sector_leakage"
            ),
        },
    )


def _run_kqd(
    backend: BackendAdapter,
    config: dict[str, Any],
    hamiltonian_bundle: object,
    progress_callback: ProgressCallback | None,
    backend_context: BackendExecutionContext | None,
) -> AlgorithmResult:
    # KQD keeps the projected solve local. IBM Runtime supplies measured
    # projected matrix elements through EstimatorV2. Small Aer targets use
    # AerSimulator for state propagation; large Aer targets use Aer Estimator
    # branch matrix elements to avoid dense full-Hilbert operators.
    execution_policy: ProjectedExecutionPolicy = resolve_projected_execution_policy(
        hamiltonian=hamiltonian_bundle,
        backend_context=backend_context,
    )
    primitive = (
        backend.create_estimator(backend_context)
        if execution_policy.requires_estimator
        else None
    )
    return run_kqd(
        hamiltonian=hamiltonian_bundle,
        backend=primitive,
        config=config,
        progress_callback=progress_callback,
        backend_context=backend_context,
        execution_policy=execution_policy,
    )


def _run_qfd(
    backend: BackendAdapter,
    config: dict[str, Any],
    hamiltonian_bundle: object,
    progress_callback: ProgressCallback | None,
    backend_context: BackendExecutionContext | None,
) -> AlgorithmResult:
    # QFD keeps the projected solve local. IBM Runtime supplies measured
    # projected matrix elements through EstimatorV2. Small Aer targets use
    # AerSimulator for state propagation; large Aer targets use Aer Estimator
    # branch matrix elements to avoid dense full-Hilbert operators.
    execution_policy: ProjectedExecutionPolicy = resolve_projected_execution_policy(
        hamiltonian=hamiltonian_bundle,
        backend_context=backend_context,
    )
    primitive = (
        backend.create_estimator(backend_context)
        if execution_policy.requires_estimator
        else None
    )
    return run_qfd(
        hamiltonian=hamiltonian_bundle,
        backend=primitive,
        config=config,
        progress_callback=progress_callback,
        backend_context=backend_context,
        execution_policy=execution_policy,
    )


def _run_qse(
    backend: BackendAdapter,
    config: dict[str, Any],
    hamiltonian_bundle: object,
    progress_callback: ProgressCallback | None,
    backend_context: BackendExecutionContext | None,
) -> AlgorithmResult:
    resolved = resolve_algorithm_config(config, "qse")
    reference_method = str(resolved.get("reference_method", "vqe")).lower()
    # Measured QSE (noisy Aer or IBM Runtime) requires the backend estimator to
    # measure projected H/S matrix elements. A VQE reference also needs an
    # estimator for its optimization. The IBM estimator is created through the
    # existing adapter, which fails closed without credentials.
    execution_policy: QSEExecutionPolicy = resolve_qse_execution_policy(
        backend_context=backend_context,
        reference_method=reference_method,
    )
    estimator = (
        backend.create_estimator(backend_context)
        if execution_policy.requires_estimator
        else None
    )
    return run_qse(
        hamiltonian=hamiltonian_bundle,
        backend=estimator,
        config=config,
        progress_callback=progress_callback,
        backend_context=backend_context,
        execution_policy=execution_policy,
    )


def _run_skqd(
    backend: BackendAdapter,
    config: dict[str, Any],
    hamiltonian_bundle: object,
    progress_callback: ProgressCallback | None,
    backend_context: BackendExecutionContext | None,
) -> AlgorithmResult:
    sampler = backend.create_sampler(backend_context)
    return run_skqd(
        hamiltonian=hamiltonian_bundle,
        backend=sampler,
        config=config,
        progress_callback=progress_callback,
        backend_context=backend_context,
    )


_ALGORITHM_REGISTRY: dict[str, AlgorithmDefinition] = {
    RunAlgorithm.VQE.value: AlgorithmDefinition(
        algorithm=RunAlgorithm.VQE.value,
        runner=_run_vqe,
        config_namespace=RunAlgorithm.VQE.value,
        primitive_requirement=PrimitiveRequirement.ESTIMATOR,
    ),
    RunAlgorithm.SQD.value: AlgorithmDefinition(
        algorithm=RunAlgorithm.SQD.value,
        runner=_run_sqd,
        config_namespace=RunAlgorithm.SQD.value,
        primitive_requirement=PrimitiveRequirement.SAMPLER_AND_OPTIONAL_ESTIMATOR,
    ),
    RunAlgorithm.KQD.value: AlgorithmDefinition(
        algorithm=RunAlgorithm.KQD.value,
        runner=_run_kqd,
        config_namespace=RunAlgorithm.KQD.value,
        primitive_requirement=PrimitiveRequirement.OPTIONAL_ESTIMATOR,
    ),
    RunAlgorithm.QFD.value: AlgorithmDefinition(
        algorithm=RunAlgorithm.QFD.value,
        runner=_run_qfd,
        config_namespace=RunAlgorithm.QFD.value,
        primitive_requirement=PrimitiveRequirement.OPTIONAL_ESTIMATOR,
    ),
    RunAlgorithm.QSE.value: AlgorithmDefinition(
        algorithm=RunAlgorithm.QSE.value,
        runner=_run_qse,
        config_namespace=RunAlgorithm.QSE.value,
        primitive_requirement=PrimitiveRequirement.OPTIONAL_ESTIMATOR,
    ),
    RunAlgorithm.SKQD.value: AlgorithmDefinition(
        algorithm=RunAlgorithm.SKQD.value,
        runner=_run_skqd,
        config_namespace=RunAlgorithm.SKQD.value,
        primitive_requirement=PrimitiveRequirement.SAMPLER,
    ),
}


def dispatch_algorithm(
    *,
    algorithm: str,
    backend: BackendAdapter,
    config_snapshot: dict[str, Any],
    hamiltonian_bundle: object,
    progress_callback: ProgressCallback | None = None,
    backend_context: BackendExecutionContext | None = None,
) -> AlgorithmResult:
    """Dispatch to the selected algorithm runner."""
    definition = _ALGORITHM_REGISTRY.get(algorithm)
    if definition is None:
        supported = ", ".join(sorted(_ALGORITHM_REGISTRY))
        raise BackendError(
            f"algorithm '{algorithm}' is not enabled in worker rollout (supported: {supported})"
        )
    return definition.runner(
        backend,
        config_snapshot,
        hamiltonian_bundle,
        progress_callback,
        backend_context,
    )


def supported_algorithms() -> set[str]:
    """Return currently enabled algorithm identifiers."""
    return set(_ALGORITHM_REGISTRY)


def algorithm_definitions() -> dict[str, AlgorithmDefinition]:
    """Return a copy of the worker algorithm registry metadata."""
    return dict(_ALGORITHM_REGISTRY)
