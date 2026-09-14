"""Shared work-unit estimation helpers for API and worker."""

from __future__ import annotations

from typing import Any

from shared.contracts.registry_metadata import resolve_ansatz_id, resolve_optimizer_id

DEFAULT_QSE_REFERENCE_ITERATIONS = 300
MAX_VQE_INITIAL_POINT_CANDIDATES = 16


def _as_positive_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value <= 0:
        return None
    return value


def _as_positive_numeric_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value <= 0:
        return None
    return int(value)


def bounded_positive_int(value: Any, *, default: int, high: int | None = None) -> int:
    """Return a positive integer clamped to high when possible."""
    parsed = _as_positive_int(value)
    if parsed is None:
        parsed = default
    if high is not None:
        parsed = min(parsed, high)
    return max(parsed, 1)


def estimate_vqe_parameter_count(
    *,
    config_payload: dict[str, Any],
    num_qubits: int | None,
) -> int | None:
    """Estimate ansatz parameter count without importing Qiskit."""
    if num_qubits is None or num_qubits <= 0:
        return None

    reps = bounded_positive_int(config_payload.get("reps"), default=2, high=6)
    ansatz_name = str(config_payload.get("ansatz_name") or config_payload.get("ansatz") or "")
    normalized = resolve_ansatz_id(ansatz_name)

    if normalized == "realamplitudes":
        return max(1, num_qubits * (reps + 1))

    return max(1, 2 * num_qubits * (reps + 1))


def vqe_candidate_evaluations(config_payload: dict[str, Any]) -> int:
    """Estimate pre-optimizer objective calls used to choose a VQE starting point."""
    if config_payload.get("initial_parameters") is not None or config_payload.get("initial_point"):
        return 0

    strategy = str(config_payload.get("initial_point_strategy") or "zero_plus_seeded_random")
    default_candidates = 2 if strategy == "zero_plus_seeded_random" else 1
    candidates = bounded_positive_int(
        config_payload.get("initial_point_candidates"),
        default=default_candidates,
        high=MAX_VQE_INITIAL_POINT_CANDIDATES,
    )
    return candidates if candidates > 1 else 0


def _select_runtime_config(algorithm_key: str, config_payload: dict[str, Any]) -> dict[str, Any]:
    advanced_config = config_payload.get("advanced_config")
    if (
        isinstance(advanced_config, dict)
        and str(advanced_config.get("algorithm", "")).lower() == algorithm_key
    ):
        return advanced_config
    return config_payload


def _explicit_vqe_evaluation_cap(runtime_config: dict[str, Any]) -> int | None:
    explicit_evaluation_cap = _as_positive_numeric_int(
        runtime_config.get("max_function_evaluations")
    )
    if explicit_evaluation_cap is not None:
        return explicit_evaluation_cap

    optimizer_options = runtime_config.get("optimizer_options")
    if not isinstance(optimizer_options, dict):
        return None
    return _as_positive_numeric_int(optimizer_options.get("maxfun"))


def _estimate_vqe_iterations(
    *,
    runtime_config: dict[str, Any],
    num_qubits: int | None,
) -> int:
    explicit_evaluation_cap = _explicit_vqe_evaluation_cap(runtime_config)
    if explicit_evaluation_cap is not None:
        return explicit_evaluation_cap

    max_iterations = _as_positive_numeric_int(runtime_config.get("max_iterations")) or 100
    parameter_count = estimate_vqe_parameter_count(
        config_payload=runtime_config,
        num_qubits=num_qubits,
    )
    if parameter_count is not None:
        max_iterations = max(max_iterations, parameter_count + 2)

    optimizer_value = runtime_config.get("optimizer_name") or runtime_config.get("optimizer") or ""
    optimizer_name = resolve_optimizer_id(str(optimizer_value))
    candidate_evaluations = vqe_candidate_evaluations(runtime_config)
    if optimizer_name == "SPSA":
        return candidate_evaluations + max_iterations * 3 + 2
    if optimizer_name in {"L_BFGS_B", "SLSQP"}:
        multiplier = max(5, (parameter_count or 4) + 1)
        return candidate_evaluations + max_iterations * multiplier
    return candidate_evaluations + max_iterations


def _build_qse_reference_config(runtime_config: dict[str, Any]) -> dict[str, Any]:
    return {
        "algorithm": "vqe",
        "ansatz_name": runtime_config.get("vqe_reference_ansatz_name", "EfficientSU2"),
        "optimizer_name": runtime_config.get("vqe_reference_optimizer_name", "COBYLA"),
        "max_iterations": (
            runtime_config.get("vqe_reference_max_iterations") or DEFAULT_QSE_REFERENCE_ITERATIONS
        ),
        "reps": runtime_config.get("vqe_reference_reps", 2),
        "initial_point_strategy": "zero_plus_seeded_random",
        "initial_point_candidates": 2,
    }


def _estimate_qse_iterations(
    *,
    runtime_config: dict[str, Any],
    num_qubits: int | None,
) -> int:
    subspace_iterations = _as_positive_numeric_int(runtime_config.get("max_subspace_dim")) or 16
    if str(runtime_config.get("reference_method", "")).lower() != "vqe":
        return subspace_iterations

    return subspace_iterations + estimate_total_iterations(
        algorithm="vqe",
        config_payload=_build_qse_reference_config(runtime_config),
        num_qubits=num_qubits,
    )


def _estimate_skqd_iterations(runtime_config: dict[str, Any]) -> int:
    """Estimate SKQD work from its sampled Krylov states.

    SKQD uses a cumulative sample union and one selected-CI solve. It does
    not run the SQD recovery loop, so ``base_sampling_options.max_iterations``
    is not part of its workload.
    """
    krylov_extension_dim = _as_positive_numeric_int(runtime_config.get("krylov_extension_dim")) or 1
    return krylov_extension_dim


def _estimate_primary_iterations(
    *,
    algorithm: str,
    runtime_config: dict[str, Any],
    num_qubits: int | None,
) -> int:
    """Estimate the algorithm-native primary progress axis."""
    if algorithm == "vqe":
        return _estimate_vqe_iterations(
            runtime_config=runtime_config,
            num_qubits=num_qubits,
        )
    if algorithm == "sqd":
        return _as_positive_numeric_int(runtime_config.get("max_iterations")) or 100
    if algorithm == "kqd":
        return _as_positive_numeric_int(runtime_config.get("krylov_dim")) or 16
    if algorithm == "qfd":
        return _as_positive_numeric_int(runtime_config.get("num_time_points")) or 32
    if algorithm == "qse":
        return _estimate_qse_iterations(
            runtime_config=runtime_config,
            num_qubits=num_qubits,
        )
    if algorithm == "skqd":
        return _estimate_skqd_iterations(runtime_config)
    return 1


def _is_projected_branch_target(backend_target: str | None) -> bool:
    """Return whether projected matrix elements use the branch-estimator path."""
    return str(backend_target or "").strip().lower() in {"aer_simulator", "ibm_runtime"}


def _projected_branch_work(
    *,
    algorithm: str,
    runtime_config: dict[str, Any],
    backend_target: str | None,
) -> tuple[int, int] | None:
    """Return ``(matrix-element-pairs, total-progress-units)`` for branch paths."""
    if algorithm not in {"kqd", "qfd"} or not _is_projected_branch_target(backend_target):
        return None
    dimension_key = "krylov_dim" if algorithm == "kqd" else "num_time_points"
    dimension = _as_positive_numeric_int(runtime_config.get(dimension_key))
    if dimension is None:
        dimension = 16 if algorithm == "kqd" else 32
    matrix_element_pairs = dimension * (dimension + 1) // 2
    return matrix_element_pairs, matrix_element_pairs + dimension


def estimate_total_iterations(
    *,
    algorithm: str,
    config_payload: dict[str, Any],
    num_qubits: int | None = None,
    backend_target: str | None = None,
) -> int:
    """Estimate total progress units from algorithm-native configuration payloads.

    The primary axis remains algorithm-specific. Branch-estimator KQD and QFD
    also execute one projected matrix-element unit for each upper-triangular
    state pair and a final projected solve phase. Include those units when the
    execution target selects that path.
    """
    algorithm_key = algorithm.lower()
    runtime_config = _select_runtime_config(algorithm_key, config_payload)
    primary_iterations = _estimate_primary_iterations(
        algorithm=algorithm_key,
        runtime_config=runtime_config,
        num_qubits=num_qubits,
    )
    projected_work = _projected_branch_work(
        algorithm=algorithm_key,
        runtime_config=runtime_config,
        backend_target=backend_target,
    )
    return projected_work[1] if projected_work is not None else primary_iterations


def estimate_workload_breakdown(
    *,
    algorithm: str,
    config_payload: dict[str, Any],
    num_qubits: int | None = None,
    backend_target: str | None = None,
) -> dict[str, Any]:
    """Describe native progress work and any nested algorithm work.

    SQD with a VQE sampling state has two distinct workloads: the SQD
    recovery rounds and the VQE objective evaluations used to prepare the
    sampling state. Keep the native iteration count unchanged so progress
    events remain comparable with existing runs.
    """
    algorithm_key = algorithm.lower()
    runtime_config = _select_runtime_config(algorithm_key, config_payload)
    primary_iterations = _estimate_primary_iterations(
        algorithm=algorithm_key,
        runtime_config=runtime_config,
        num_qubits=num_qubits,
    )
    workload: dict[str, Any] = {
        "estimated_primary_iterations": primary_iterations,
        "estimated_total_work_units": primary_iterations,
        "work_unit_policy": "algorithm_native_iterations",
    }

    projected_work = _projected_branch_work(
        algorithm=algorithm_key,
        runtime_config=runtime_config,
        backend_target=backend_target,
    )
    if projected_work is not None:
        matrix_element_pairs, total_work_units = projected_work
        workload.update(
            {
                "estimated_matrix_element_pairs": matrix_element_pairs,
                "estimated_total_work_units": total_work_units,
                "work_unit_policy": (
                    "projected_state_pairs_plus_projected_solve"
                ),
            }
        )

    sampling_source = str(runtime_config.get("sampling_state_source") or "hf").lower()
    if algorithm_key != "sqd" or sampling_source != "vqe":
        return workload

    reference_config = {
        "algorithm": "vqe",
        "ansatz_name": runtime_config.get("sampling_vqe_ansatz_name") or "NumberPreserving",
        "optimizer_name": runtime_config.get("sampling_vqe_optimizer_name") or "COBYLA",
        "max_iterations": runtime_config.get("sampling_vqe_max_iterations") or 120,
        "reps": runtime_config.get("sampling_vqe_reps") or 2,
        "initial_point_strategy": "zero_plus_seeded_random",
        # The worker always evaluates two candidates for the nested VQE.
        "initial_point_candidates": 2,
    }
    reference_iterations = estimate_total_iterations(
        algorithm="vqe",
        config_payload=reference_config,
        num_qubits=num_qubits,
    )
    workload.update(
        {
            "estimated_reference_iterations": reference_iterations,
            "estimated_total_work_units": primary_iterations + reference_iterations,
            "work_unit_policy": "sqd_recovery_rounds_plus_sampling_vqe_objective_evaluations",
            "reference_workload": "sampling_vqe",
        }
    )
    return workload
