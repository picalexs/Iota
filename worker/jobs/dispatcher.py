"""Algorithm dispatcher for worker execution."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np

from shared.contracts.identifiers import RunAlgorithm
from worker.adapters.base import BackendAdapter, BackendExecutionContext
from worker.chemistry.ansatz_registry import build_ansatz
from worker.chemistry.kqd_solver import run_kqd
from worker.chemistry.progress import ProgressCallback
from worker.chemistry.qfd_solver import run_qfd
from worker.chemistry.qse_solver import run_qse
from worker.chemistry.skqd_solver import run_skqd
from worker.chemistry.solver_utils import resolve_algorithm_config
from worker.chemistry.sqd_solver import run_sqd
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

_DENSE_QUBIT_LIMIT = 12


def _hamiltonian_num_qubits(hamiltonian_bundle: object) -> int:
    if hasattr(hamiltonian_bundle, "num_qubits"):
        return int(getattr(hamiltonian_bundle, "num_qubits") or 0)
    pauli = getattr(hamiltonian_bundle, "pauli_hamiltonian", None)
    if pauli is not None and hasattr(pauli, "num_qubits"):
        return int(getattr(pauli, "num_qubits") or 0)
    return 0


def _projected_matrix_estimator_required(
    *,
    hamiltonian_bundle: object,
    backend_context: BackendExecutionContext | None,
) -> bool:
    backend_target = getattr(backend_context, "backend_target", None)
    if backend_target == "ibm_runtime":
        return True
    return backend_target == "aer_simulator" and (
        getattr(backend_context, "noise_profile", None) is not None
        or _hamiltonian_num_qubits(hamiltonian_bundle) > _DENSE_QUBIT_LIMIT
    )


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
    primitive = (
        backend.create_estimator(backend_context)
        if _projected_matrix_estimator_required(
            hamiltonian_bundle=hamiltonian_bundle,
            backend_context=backend_context,
        )
        else None
    )
    return run_kqd(
        hamiltonian=hamiltonian_bundle,
        backend=primitive,
        config=config,
        progress_callback=progress_callback,
        backend_context=backend_context,
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
    primitive = (
        backend.create_estimator(backend_context)
        if _projected_matrix_estimator_required(
            hamiltonian_bundle=hamiltonian_bundle,
            backend_context=backend_context,
        )
        else None
    )
    return run_qfd(
        hamiltonian=hamiltonian_bundle,
        backend=primitive,
        config=config,
        progress_callback=progress_callback,
        backend_context=backend_context,
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
    backend_target = getattr(backend_context, "backend_target", None)
    measured_path = backend_target == "ibm_runtime" or (
        backend_target == "aer_simulator"
        and getattr(backend_context, "noise_profile", None) is not None
    )
    estimator = (
        backend.create_estimator(backend_context)
        if measured_path or reference_method == "vqe"
        else None
    )
    return run_qse(
        hamiltonian=hamiltonian_bundle,
        backend=estimator,
        config=config,
        progress_callback=progress_callback,
        backend_context=backend_context,
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


_ALGORITHM_REGISTRY: dict[str, AlgorithmRunner] = {
    RunAlgorithm.VQE.value: _run_vqe,
    RunAlgorithm.SQD.value: _run_sqd,
    RunAlgorithm.KQD.value: _run_kqd,
    RunAlgorithm.QFD.value: _run_qfd,
    RunAlgorithm.QSE.value: _run_qse,
    RunAlgorithm.SKQD.value: _run_skqd,
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
    runner = _ALGORITHM_REGISTRY.get(algorithm)
    if runner is None:
        supported = ", ".join(sorted(_ALGORITHM_REGISTRY))
        raise BackendError(
            f"algorithm '{algorithm}' is not enabled in worker rollout (supported: {supported})"
        )
    return runner(backend, config_snapshot, hamiltonian_bundle, progress_callback, backend_context)


def supported_algorithms() -> set[str]:
    """Return currently enabled algorithm identifiers."""
    return set(_ALGORITHM_REGISTRY)
