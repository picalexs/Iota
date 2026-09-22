"""Setup and result metadata assembly for worker execution."""

from __future__ import annotations

from typing import Any

from worker.adapters.base import BackendExecutionContext
from worker.chemistry.circuit_artifacts import enrich_circuit_artifacts
from worker.jobs.execution_plan import (
    DeviceRequest,
    ExecutionPlan,
    ResourceClass,
    StageRequest,
)
from worker.contracts import (
    BackendAdapterContract,
    ChemistryInputContract,
    HamiltonianBundleContract,
)


def dense_classical_execution_metadata(
    algorithm: str,
    backend_context: BackendExecutionContext,
) -> dict[str, Any]:
    if backend_context.backend_target == "ibm_runtime":
        return {
            "execution_mode": "hardware_matrix_elements",
            "actual_execution_target": "ibm_runtime",
            "actual_path_class": "hardware_matrix_elements",
            "aer_simulator_used": False,
            "backend_primitives_used": True,
            "primitive_family": "qiskit_ibm_runtime.EstimatorV2",
            "backend_note": (
                f"{algorithm.upper()} measures projected Hamiltonian/overlap matrix "
                "elements with branch-state Estimator circuits; the final generalized "
                "eigensolve remains local."
            ),
        }
    if backend_context.backend_target == "aer_simulator":
        return {
            "execution_mode": "aer_statevector_evolution",
            "actual_execution_target": "aer_simulator",
            "actual_path_class": "aer_statevector_evolution",
            "aer_simulator_used": True,
            "backend_primitives_used": False,
            "primitive_family": "qiskit_aer.AerSimulator",
            "transpilation_summary": {
                "optimization_level": backend_context.optimization_level,
                "preview": (
                    "AerSimulator Pauli-evolution circuits are transpiled before statevector save."
                ),
            },
            "backend_note": (
                f"{algorithm.upper()} uses AerSimulator for time-evolution state "
                "propagation; projected Hamiltonian/overlap matrices and the final "
                "generalized eigensolve remain local."
            ),
        }
    return {
        "execution_mode": "dense_classical",
        "actual_execution_target": "local_classical",
        "actual_path_class": "dense_classical",
        "aer_simulator_used": False,
        "backend_primitives_used": False,
        "primitive_family": None,
        "fallback_reason": f"{algorithm}_uses_local_classical_projected_solver",
        "backend_note": (
            f"{algorithm.upper()} uses dense classical eigensolver/tensor operations after "
            "Hamiltonian construction; no backend primitive is invoked."
        ),
    }


def branch_matrix_execution_metadata(algorithm: str, backend_target: str) -> dict[str, Any]:
    if backend_target == "aer_simulator":
        return {
            "execution_mode": "aer_branch_estimator",
            "actual_execution_target": "aer_simulator",
            "actual_path_class": "aer_branch_estimator",
            "aer_simulator_used": True,
            "backend_primitives_used": True,
            "primitive_family": "qiskit_aer.EstimatorV2",
            "backend_note": (
                f"{algorithm.upper()} uses Aer Estimator branch-state circuits to "
                "assemble projected Hamiltonian/overlap matrices; the final "
                "generalized eigensolve remains local."
            ),
        }
    if backend_target == "ibm_runtime":
        return dense_classical_execution_metadata(
            algorithm,
            BackendExecutionContext(backend_target=backend_target),
        )
    return {}


def pending_conditional_execution_metadata(algorithm: str) -> dict[str, Any]:
    """Describe a conditional path before the solver has produced a result."""
    return {
        "execution_mode": f"{algorithm}_path_pending",
        "backend_primitives_used": False,
        "primitive_family": None,
        "backend_note": (
            f"{algorithm.upper()} setup metadata does not prove primitive execution; "
            "the terminal result records the resolved execution path."
        ),
    }


def _requested_device(value: Any) -> DeviceRequest:
    if isinstance(value, str):
        return DeviceRequest(value.strip().upper())
    return DeviceRequest.CPU


def _stage_plan_metadata(
    *,
    algorithm: str,
    backend_context: BackendExecutionContext,
    adapter_metadata: dict[str, Any],
    result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build planned stage provenance without claiming runtime proof."""
    backend_options = backend_context.backend_options
    resources = backend_context.resource_metadata
    available_devices = adapter_metadata.get("available_devices")
    aer_gpu_available = isinstance(available_devices, list) and "GPU" in available_devices
    aer_request = _requested_device(backend_options.get("device"))
    chemistry_options = backend_context.chemistry_options
    reference_request = _requested_device(chemistry_options.get("reference_device"))
    selected_ci_request = _requested_device(chemistry_options.get("selected_ci_device"))

    reference_actual = resources.get("reference_device_actual")
    reference_gpu_available = reference_actual == "GPU"
    selected_ci_execution = {}
    if isinstance(result, dict):
        metrics = result.get("algorithm_metrics")
        if isinstance(metrics, dict) and isinstance(metrics.get("selected_ci_execution"), dict):
            selected_ci_execution = metrics["selected_ci_execution"]
    selected_ci_actual = selected_ci_execution.get("actual_device")
    selected_ci_gpu_available = selected_ci_actual == "GPU"
    selected_ci_request = _requested_device(
        selected_ci_execution.get("requested_device", selected_ci_request.value)
    )

    requests = [
        StageRequest(
            name="reference_scf",
            resource_class=(
                ResourceClass.CHEMISTRY_GPU
                if reference_request is not DeviceRequest.CPU
                else ResourceClass.CPU
            ),
            requested_device=reference_request,
            gpu_available=reference_gpu_available,
            provider=resources.get("reference_provider"),
        ),
        StageRequest(
            name="hamiltonian_build",
            resource_class=ResourceClass.CPU,
            requested_device=DeviceRequest.CPU,
            gpu_available=False,
            provider="pyscf+ffsim",
        ),
        StageRequest(
            name="state_generation_or_sampling",
            resource_class=(
                ResourceClass.AER_GPU
                if aer_request is DeviceRequest.GPU
                else ResourceClass.CPU
            ),
            requested_device=aer_request,
            gpu_available=aer_gpu_available,
            provider="qiskit_aer" if backend_context.backend_target == "aer_simulator" else None,
        ),
        StageRequest(
            name="selected_ci",
            resource_class=(
                ResourceClass.SBD_GPU
                if selected_ci_request is not DeviceRequest.CPU
                else ResourceClass.CPU
            ),
            requested_device=selected_ci_request,
            gpu_available=selected_ci_gpu_available,
            provider=selected_ci_execution.get("provider") or "qiskit_addon_sqd",
        ),
        StageRequest(
            name="projected_solve",
            resource_class=ResourceClass.CPU,
            requested_device=DeviceRequest.CPU,
            gpu_available=False,
            provider="numpy+scipy",
        ),
        StageRequest(
            name="finalize",
            resource_class=ResourceClass.CPU,
            requested_device=DeviceRequest.CPU,
            gpu_available=False,
            provider="worker",
        ),
    ]
    # Non-SQD algorithms do not have a selected-CI stage. Keep the stage in the
    # plan only when it was requested or reported, so metadata remains honest.
    if algorithm not in {"sqd", "skqd"} and selected_ci_request is DeviceRequest.CPU:
        requests = [request for request in requests if request.name != "selected_ci"]

    plan = ExecutionPlan.resolve(requests)
    stage_paths = [
        {
            "stage_name": stage.name,
            "resource_class": stage.resource_class.value,
            "requested_device": stage.requested_device.value,
            "planned_device": stage.actual_device.value,
            "actual_device": _observed_stage_device(
                stage,
                adapter_metadata=adapter_metadata,
                reference_gpu_available=reference_gpu_available,
                selected_ci_gpu_available=selected_ci_gpu_available,
            ),
            "device_verified": _stage_device_verified(
                stage,
                adapter_metadata=adapter_metadata,
                reference_gpu_available=reference_gpu_available,
                selected_ci_gpu_available=selected_ci_gpu_available,
            ),
            "provider": stage.provider,
            "fallback_reason": stage.fallback_reason,
        }
        for stage in plan.stages
    ]
    actual_gpu_classes = {
        stage["resource_class"]
        for stage in stage_paths
        if stage["actual_device"] == DeviceRequest.GPU.value
    }
    if ResourceClass.AER_GPU.value in actual_gpu_classes:
        lane = "aer_gpu"
    elif actual_gpu_classes:
        lane = "chemistry_gpu"
    elif backend_context.backend_target == "ibm_runtime":
        lane = "ibm_runtime"
    elif backend_context.backend_target == "aer_simulator":
        lane = "aer_circuit"
    else:
        lane = "local_exact"
    return {
        "execution_lane": lane,
        "stage_paths": stage_paths,
        "plan_is_runtime_proof": False,
    }


def _observed_stage_device(
    stage: Any,
    *,
    adapter_metadata: dict[str, Any],
    reference_gpu_available: bool,
    selected_ci_gpu_available: bool,
) -> str | None:
    if stage.actual_device is DeviceRequest.CPU:
        return "CPU"
    if stage.resource_class is ResourceClass.AER_GPU:
        return (
            adapter_metadata.get("actual_device")
            if adapter_metadata.get("device_verified") is True
            else None
        )
    if stage.resource_class is ResourceClass.CHEMISTRY_GPU and reference_gpu_available:
        return "GPU"
    if stage.resource_class is ResourceClass.SBD_GPU and selected_ci_gpu_available:
        return "GPU"
    return None


def _stage_device_verified(
    stage: Any,
    *,
    adapter_metadata: dict[str, Any],
    reference_gpu_available: bool,
    selected_ci_gpu_available: bool,
) -> bool:
    if stage.actual_device is DeviceRequest.CPU:
        return True
    if stage.resource_class is ResourceClass.AER_GPU:
        return (
            adapter_metadata.get("device_verified") is True
            and adapter_metadata.get("actual_device") == "GPU"
        )
    return (
        (stage.resource_class is ResourceClass.CHEMISTRY_GPU and reference_gpu_available)
        or (stage.resource_class is ResourceClass.SBD_GPU and selected_ci_gpu_available)
    )


def merge_backend_metadata(
    *,
    algorithm: str,
    adapter_metadata: dict[str, Any],
    backend_context: BackendExecutionContext,
    provisional: bool = False,
) -> dict[str, Any]:
    metadata = {
        "backend_target": backend_context.backend_target,
        "requested_target": backend_context.backend_target,
        "selection_policy": backend_context.selection_policy,
        "shots": backend_context.shots,
        "requested_shots": (
            backend_context.requested_shots
            if backend_context.requested_shots is not None
            else backend_context.shots
        ),
        "effective_shots": backend_context.shots,
        "requested_estimator_precision": (
            backend_context.requested_estimator_precision
            if backend_context.requested_estimator_precision is not None
            else backend_context.estimator_precision
        ),
        "effective_estimator_precision": backend_context.estimator_precision,
        "measurement_mode": (
            "exact" if backend_context.estimator_precision == 0.0 else "precision_sampled"
        ),
        "uncertainty_policy": "configured_estimator_precision",
        "simulator_method": backend_context.simulator_method,
        "optimization_level": backend_context.optimization_level,
        "noise_summary": {"enabled": bool(backend_context.noise_profile)},
        "resource_metadata": dict(backend_context.resource_metadata),
        "execution_plan": _stage_plan_metadata(
            algorithm=algorithm,
            backend_context=backend_context,
            adapter_metadata=adapter_metadata,
        ),
        **adapter_metadata,
    }
    aer_state_evolution = backend_context.resource_metadata.get("aer_state_evolution")
    if isinstance(aer_state_evolution, dict):
        metadata["aer_state_evolution"] = dict(aer_state_evolution)
        if aer_state_evolution.get("actual_device") in {"CPU", "GPU"}:
            metadata["actual_device"] = aer_state_evolution["actual_device"]
            metadata["device_verified"] = aer_state_evolution.get("device_verified") is True
    if provisional and algorithm in {"kqd", "qfd", "qse"}:
        metadata.update(pending_conditional_execution_metadata(algorithm))
    elif algorithm in {"kqd", "qfd"}:
        metadata.update(dense_classical_execution_metadata(algorithm, backend_context))
    if not provisional:
        metadata.setdefault("actual_path_class", metadata.get("execution_mode"))
        if not metadata.get("actual_execution_target"):
            if metadata.get("aer_simulator_used") is True:
                metadata["actual_execution_target"] = "aer_simulator"
            elif metadata.get("backend_primitives_used") is False:
                metadata["actual_execution_target"] = "local_classical"
            else:
                metadata["actual_execution_target"] = backend_context.backend_target
    return metadata


def uses_branch_matrix_elements(result: dict[str, Any]) -> bool:
    metrics = result.get("algorithm_metrics")
    if not isinstance(metrics, dict):
        return False
    summary = metrics.get("matrix_element_summary")
    return (
        isinstance(summary, dict) and summary.get("matrix_element_strategy") == "branch_estimator"
    )


def _refine_qse_backend_metadata(
    result: dict[str, Any],
    backend_metadata: dict[str, Any],
) -> dict[str, Any]:
    metrics = result.get("algorithm_metrics")
    metrics = metrics if isinstance(metrics, dict) else {}
    if metrics.get("execution_mode") == "dense_exact_emulation":
        return {
            **backend_metadata,
            "execution_mode": "qse_dense_exact_emulation",
            "actual_path_class": "qse_dense_exact_emulation",
            "actual_execution_target": "local_classical",
            "aer_simulator_used": False,
            "backend_primitives_used": False,
            "primitive_family": None,
            "execution_scope": "local_exact_emulation",
            "projected_matrix_source": "local_exact_statevectors",
            "measured_projected_matrix_elements": False,
            "fallback_reason": "qse_declared_exact_emulation_reference",
            "backend_note": (
                "QSE uses an exact local statevector reference and exact local projected "
                "matrix construction; the requested backend is not invoked on this path."
            ),
        }
    execution_mode = metrics.get("execution_mode") or "qse_projected_local"
    is_sector_emulation = execution_mode == "sector_matrix_free"
    return {
        **backend_metadata,
        "execution_mode": execution_mode,
        "actual_path_class": execution_mode,
        "actual_execution_target": "local_classical",
        "backend_primitives_used": False,
        "primitive_family": None,
        "execution_scope": (
            "local_sector_emulation" if is_sector_emulation else "local_exact_emulation"
        ),
        "projected_matrix_source": (
            "local_sector_action" if is_sector_emulation else "local_exact_statevectors"
        ),
        "measured_projected_matrix_elements": False,
        "fallback_reason": "qse_local_reference_and_projected_solver",
        "backend_note": (
            "QSE uses a local reference and local projected diagonalization; "
            "no backend primitive was executed."
        ),
    }


def refine_backend_metadata_from_result(
    *,
    algorithm: str,
    result: dict[str, Any],
    backend_metadata: dict[str, Any],
) -> dict[str, Any]:
    if algorithm == "qse":
        return _refine_qse_backend_metadata(result, backend_metadata)
    if algorithm not in {"kqd", "qfd"}:
        return backend_metadata
    backend_target = str(backend_metadata.get("backend_target") or "")
    if uses_branch_matrix_elements(result):
        return {
            **backend_metadata,
            **branch_matrix_execution_metadata(algorithm, backend_target),
        }

    metrics = result.get("algorithm_metrics")
    summary = metrics.get("matrix_element_summary") if isinstance(metrics, dict) else None
    if (
        algorithm == "kqd"
        and isinstance(summary, dict)
        and summary.get("matrix_element_strategy") == "dense_classical"
        and summary.get("implemented_evolution_method") == "exact_matrix_evolution"
    ):
        metadata = dict(backend_metadata)
        metadata.pop("transpilation_summary", None)
        requested_backend_name = metadata.pop("resolved_backend_name", None)
        requested_optimization_level = metadata.pop("optimization_level", None)
        requested_noise_summary = metadata.pop("noise_summary", None)
        for key in ("job_id", "job_ids", "pub_count"):
            metadata.pop(key, None)
        if requested_backend_name is not None:
            metadata["requested_resolved_backend_name"] = requested_backend_name
        if requested_optimization_level is not None:
            metadata["requested_optimization_level"] = requested_optimization_level
        if requested_noise_summary is not None:
            metadata["requested_noise_summary"] = requested_noise_summary
        metadata.update(
            {
                "execution_mode": "exact_matrix_evolution",
                "actual_path_class": "dense_classical",
                "actual_execution_target": "local_classical",
                "resolved_backend_name": None,
                "optimization_level": None,
                "aer_simulator_used": False,
                "backend_primitives_used": False,
                "primitive_family": None,
                "noise_summary": {"enabled": False},
                "shots": None,
                "effective_shots": None,
                "effective_estimator_precision": None,
                "measurement_mode": "exact",
                "uncertainty_policy": "exact_local_computation",
                "simulator_method": None,
                "actual_noise_applied": False,
                "backend_note": (
                    "KQD exact matrix-spectrum evolution runs locally; the requested "
                    "backend was not invoked."
                ),
            }
        )
        return metadata
    if isinstance(summary, dict) and summary.get("matrix_element_strategy") == "sector_matrix_free":
        return {
            **backend_metadata,
            "execution_mode": "sector_matrix_free",
            "actual_path_class": "sector_matrix_free",
            "actual_execution_target": "local_classical",
            "aer_simulator_used": False,
            "backend_primitives_used": False,
            "primitive_family": None,
            "fallback_reason": f"{algorithm}_uses_local_sector_matrix_free_solver",
            "backend_note": (
                f"{algorithm.upper()} uses local matrix-free sector evolution and a local "
                "projected solve; no backend primitive was invoked."
            ),
        }

    context = BackendExecutionContext(backend_target=backend_target)
    return {
        **backend_metadata,
        **dense_classical_execution_metadata(algorithm, context),
    }


def build_hamiltonian_message(chemistry_input: ChemistryInputContract) -> str:
    active_space = chemistry_input.active_space
    return "Building Hamiltonian" + (
        f" for active_space={active_space[0]}e/{active_space[1]}o."
        if active_space is not None
        else " with automatic active-space selection."
    )


def active_space_payload(active_space: tuple[int, int] | None) -> dict[str, int] | None:
    if active_space is None:
        return None
    return {"n_electrons": active_space[0], "n_orbitals": active_space[1]}


def build_setup_payload(
    *,
    algorithm: str,
    mode: str,
    backend_context: BackendExecutionContext,
    backend_adapter: BackendAdapterContract,
    hamiltonian_bundle: HamiltonianBundleContract,
) -> dict[str, Any]:
    setup_payload: dict[str, Any] = {
        "stage": "setup",
        "algorithm": algorithm,
        "mode": mode,
        "backend_target": backend_context.backend_target,
        "adapter": backend_adapter.capabilities.backend_target,
        "num_qubits": hamiltonian_bundle.num_qubits,
        "num_spatial_orbitals": hamiltonian_bundle.num_spatial_orbitals,
        "active_space": hamiltonian_bundle.metadata.get("active_space"),
        "chemistry_pipeline": hamiltonian_bundle.metadata.get("pipeline"),
        "hf_energy": hamiltonian_bundle.metadata.get("hf_energy"),
        "casci_energy": hamiltonian_bundle.metadata.get("casci_energy"),
        "nuclear_repulsion": hamiltonian_bundle.metadata.get("nuclear_repulsion"),
    }
    problem_manifest = hamiltonian_bundle.metadata.get("problem_manifest")
    if isinstance(problem_manifest, dict):
        setup_payload["problem_manifest"] = problem_manifest
    setup_backend_metadata = merge_backend_metadata(
        algorithm=algorithm,
        adapter_metadata=backend_adapter.execution_metadata(backend_context),
        backend_context=backend_context,
        provisional=True,
    )
    setup_payload.update(setup_backend_metadata)
    if hamiltonian_bundle.metadata.get("active_space_auto_reduced"):
        setup_payload["active_space_auto_reduced"] = True
        setup_payload["original_num_orbitals"] = hamiltonian_bundle.metadata.get(
            "original_num_orbitals"
        )
        setup_payload["original_num_electrons"] = hamiltonian_bundle.metadata.get(
            "original_num_electrons"
        )
    return setup_payload


def apply_result_metadata(
    result: dict[str, Any],
    *,
    algorithm: str,
    mode: str,
    backend_target: str,
    chemistry_input: ChemistryInputContract,
    backend_adapter: BackendAdapterContract,
    backend_context: BackendExecutionContext,
) -> None:
    result["mode"] = mode
    result["backend_target"] = backend_target
    result["basis_set"] = chemistry_input.basis
    result.setdefault("reference_basis", chemistry_input.basis)
    raw_result = result.get("raw_result")
    problem_manifest = (
        raw_result.get("problem_manifest") if isinstance(raw_result, dict) else None
    )
    if not isinstance(problem_manifest, dict):
        problem_manifest = result.get("problem_manifest")
    if isinstance(problem_manifest, dict):
        result["problem_manifest"] = problem_manifest
        if isinstance(raw_result, dict):
            raw_result["problem_manifest"] = problem_manifest
    if isinstance(raw_result, dict):
        raw_result.setdefault("basis_set", chemistry_input.basis)

    backend_metadata = merge_backend_metadata(
        algorithm=algorithm,
        adapter_metadata=backend_adapter.execution_metadata(backend_context),
        backend_context=backend_context,
    )
    backend_metadata = refine_backend_metadata_from_result(
        algorithm=algorithm,
        result=result,
        backend_metadata=backend_metadata,
    )
    backend_metadata["execution_plan"] = _stage_plan_metadata(
        algorithm=algorithm,
        backend_context=backend_context,
        adapter_metadata=backend_metadata,
        result=result,
    )
    result["backend_execution"] = backend_metadata
    result["raw_result"]["backend_execution"] = backend_metadata
    if isinstance(result.get("algorithm_metrics"), dict):
        if isinstance(problem_manifest, dict):
            result["algorithm_metrics"]["problem_manifest"] = problem_manifest
        result["algorithm_metrics"]["backend_execution"] = backend_metadata
        raw_artifacts = result["algorithm_metrics"].get("circuit_artifacts")
        if isinstance(raw_artifacts, list):
            result["algorithm_metrics"]["circuit_artifacts"] = enrich_circuit_artifacts(
                raw_artifacts,
                backend_metadata=backend_metadata,
            )
