"""Pure result and terminal-estimate normalization for worker callbacks."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from worker.chemistry.projected_subspace import projected_diagnostic_energy_is_reportable
from worker.exceptions import InvalidResultError
from worker.persistence.run_repository import normalize_payload_value

ResultPersistencePayload = tuple[
    float,
    int,
    list[float],
    bool,
    dict[str, Any],
    dict[str, Any] | None,
    dict[str, Any],
]
WORKER_RUNTIME_BASIS = "worker_execution_segment_monotonic"


def terminal_runtime_metadata(
    *,
    finished_at: datetime,
    result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"run_finished_at": finished_at.isoformat()}

    runtime_raw = result.get("runtime_seconds") if isinstance(result, dict) else None
    if isinstance(runtime_raw, (int, float)) and math.isfinite(float(runtime_raw)):
        payload["runtime_seconds"] = float(runtime_raw)
        runtime_basis = result.get("runtime_basis") if isinstance(result, dict) else None
        payload["runtime_basis"] = (
            runtime_basis if isinstance(runtime_basis, str) and runtime_basis else WORKER_RUNTIME_BASIS
        )

    return payload


def _coerce_non_negative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    if not math.isfinite(numeric) or not numeric.is_integer() or numeric < 0:
        return None
    return int(numeric)


def _required_non_negative_int(value: Any, *, field: str) -> int:
    if value is None:
        return 0
    normalized = _coerce_non_negative_int(value)
    if normalized is None:
        raise InvalidResultError(
            f"invalid_{field}",
            f"solver result field '{field}' must be a finite non-negative integer",
        )
    return normalized


def _completed_iterations_from_estimate(latest_estimate: Any) -> int | None:
    estimate = latest_estimate if isinstance(latest_estimate, dict) else {}
    total_iterations = _coerce_non_negative_int(estimate.get("estimated_total_iterations"))
    remaining_iterations = _coerce_non_negative_int(estimate.get("estimated_remaining_iterations"))
    if total_iterations is None:
        return None
    if remaining_iterations is None:
        return total_iterations if total_iterations > 0 else None
    completed_iterations = max(total_iterations - remaining_iterations, 0)
    return completed_iterations if completed_iterations > 0 else None


def _result_completed_iterations(normalized_result: ResultPersistencePayload) -> int | None:
    _, iterations, _, _, _, algorithm_metrics, _ = normalized_result
    metrics = algorithm_metrics if isinstance(algorithm_metrics, dict) else {}
    objective_evaluations = _coerce_non_negative_int(metrics.get("objective_evaluations"))
    if objective_evaluations is not None and objective_evaluations > 0:
        return objective_evaluations
    return iterations if iterations > 0 else None


def build_terminal_latest_estimate(
    *,
    result: dict[str, Any],
    finished_at: datetime,
    latest_estimate: Any,
    normalized_result: ResultPersistencePayload,
) -> dict[str, Any] | None:
    runtime_seconds = _finite_float(result.get("runtime_seconds"))
    if runtime_seconds is None or runtime_seconds <= 0:
        return None

    completed_iterations = max(
        _completed_iterations_from_estimate(latest_estimate) or 0,
        _result_completed_iterations(normalized_result) or 0,
    )
    if completed_iterations <= 0:
        return None

    _, _, _, _, raw_payload, _, _ = normalized_result
    previous_estimate = latest_estimate if isinstance(latest_estimate, dict) else {}
    estimate = {
        "source": "telemetry",
        "algorithm": raw_payload.get("algorithm"),
        "estimated_total_iterations": completed_iterations,
        "estimated_remaining_iterations": 0,
        "estimated_total_seconds": runtime_seconds,
        "estimated_remaining_seconds": 0.0,
        "confidence": 1.0,
        "updated_at": finished_at.isoformat(),
        "estimated_seconds_per_iteration": runtime_seconds / completed_iterations,
    }
    if estimate["algorithm"] is None:
        estimate["algorithm"] = previous_estimate.get("algorithm")
    for key in (
        "estimated_primary_iterations",
        "estimated_reference_iterations",
        "estimated_total_work_units",
        "work_unit_policy",
        "reference_workload",
    ):
        if key in previous_estimate:
            estimate[key] = previous_estimate[key]
    return estimate


def _build_normalized_raw_payload(
    result: dict[str, Any],
    energy_raw: Any,
    iterations_raw: Any,
    converged_raw: Any,
    algorithm_metrics_raw: Any,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    raw_result = result.get("raw_result")
    raw_payload: dict[str, Any] = raw_result.copy() if isinstance(raw_result, dict) else {}
    if isinstance(result.get("algorithm"), str):
        raw_payload.setdefault("algorithm", result["algorithm"])
    if not isinstance(algorithm_metrics_raw, dict) and isinstance(
        raw_payload.get("algorithm_metrics"), dict
    ):
        algorithm_metrics_raw = raw_payload["algorithm_metrics"]
    if isinstance(algorithm_metrics_raw, dict):
        raw_payload.setdefault("algorithm_metrics", algorithm_metrics_raw)
    raw_payload.setdefault("primary_energy", energy_raw)
    raw_payload.setdefault("primary_iterations", iterations_raw)
    raw_payload.setdefault("converged", converged_raw)
    normalized = normalize_payload_value(raw_payload)
    raw_payload = normalized if isinstance(normalized, dict) else {}
    normalized_metrics = raw_payload.get("algorithm_metrics")
    algorithm_metrics = normalized_metrics if isinstance(normalized_metrics, dict) else None
    return raw_payload, algorithm_metrics


def _persisted_energy(provenance: dict[str, Any]) -> float:
    reported_energy = provenance.get("reported_energy")
    if isinstance(reported_energy, (int, float)) and math.isfinite(float(reported_energy)):
        return float(reported_energy)
    # Keep the legacy numeric DB column safe while provenance marks the result invalid.
    return 0.0


def normalize_result_for_persistence(
    result: dict[str, Any],
) -> ResultPersistencePayload:
    """Normalize algorithm-native result payloads into DB-compatible fields."""
    energy_raw = result.get("energy", result.get("primary_energy"))
    iterations_raw = result.get("iterations", result.get("primary_iterations", 0))
    optimal_parameters_raw = result.get("optimal_parameters")
    converged_raw = result.get("converged")
    algorithm_metrics_raw = result.get("algorithm_metrics")

    iterations = _required_non_negative_int(iterations_raw, field="iterations")
    optimal_parameters_value = (
        normalize_payload_value(optimal_parameters_raw)
        if isinstance(optimal_parameters_raw, list)
        else []
    )
    optimal_parameters = (
        optimal_parameters_value if isinstance(optimal_parameters_value, list) else []
    )
    converged = bool(converged_raw) if isinstance(converged_raw, bool) else False

    raw_payload, algorithm_metrics_raw = _build_normalized_raw_payload(
        result,
        energy_raw,
        iterations_raw,
        converged_raw,
        algorithm_metrics_raw,
    )

    provenance = _extract_energy_provenance(
        result=result,
        raw_payload=raw_payload,
        algorithm_metrics=algorithm_metrics_raw,
    )
    if isinstance(algorithm_metrics_raw, dict):
        algorithm_metrics_raw["benchmark_provenance"] = _build_benchmark_provenance(
            result=result,
            metrics=algorithm_metrics_raw,
            energy_provenance=provenance,
            converged=converged,
        )
        raw_payload["algorithm_metrics"] = algorithm_metrics_raw
    energy = _persisted_energy(provenance)

    return (
        energy,
        iterations,
        optimal_parameters,
        converged,
        raw_payload,
        algorithm_metrics_raw,
        provenance,
    )


def _finite_float(value: Any) -> float | None:
    if (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
    ):
        return float(value)
    return None


def _first_finite(*values: Any) -> float | None:
    """Return the first finite value without treating zero as missing."""
    for value in values:
        finite_value = _finite_float(value)
        if finite_value is not None:
            return finite_value
    return None


def _projected_energy_is_reportable(
    *,
    result: dict[str, Any],
    metrics: dict[str, Any],
) -> bool:
    """Accept stable or reportable-diagnostic projected energies."""
    algorithm = result.get("algorithm")
    if not isinstance(algorithm, str):
        algorithm = metrics.get("algorithm")
    if algorithm not in {"kqd", "qfd", "qse"}:
        return True

    matrix_summary = metrics.get("matrix_element_summary")
    branch_estimator = (
        isinstance(matrix_summary, dict)
        and matrix_summary.get("matrix_element_strategy") == "branch_estimator"
    )

    diagnostics = _projected_stability_diagnostics(metrics)
    if isinstance(diagnostics, dict) and "stability_state" in diagnostics:
        return projected_diagnostic_energy_is_reportable(diagnostics)
    return not branch_estimator


def _projected_stability_diagnostics(metrics: dict[str, Any]) -> Any:
    """Return branch-estimator stability diagnostics for KQD/QFD or QSE."""
    diagnostics = metrics.get("stability_summary")
    if isinstance(diagnostics, dict) and diagnostics:
        return diagnostics
    return metrics.get("conditioning_summary")


def _projected_energy_is_stabilized_diagnostic(metrics: dict[str, Any]) -> bool:
    """Return whether a reportable projected energy is rank-reduced and diagnostic."""
    diagnostics = _projected_stability_diagnostics(metrics)
    if not isinstance(diagnostics, dict):
        return False
    if diagnostics.get("stability_state") != "stabilized":
        return False
    return int(diagnostics.get("dropped_rank", 0) or 0) > 0 or bool(
        diagnostics.get("psd_projected", False)
    )


def _finite_trace_values(value: Any) -> list[float]:
    if not isinstance(value, list):
        return []
    return [
        float(item)
        for item in value
        if isinstance(item, (int, float)) and math.isfinite(float(item))
    ]


def _energy_source(
    *,
    result: dict[str, Any],
    sci_package: dict[str, Any],
    best_observed_energy: float | None,
    reported_energy: float | None,
) -> str:
    source = result.get("reported_energy_source") or sci_package.get("reported_energy_source")
    if isinstance(source, str) and source:
        return source
    return "best_observed_energy" if best_observed_energy == reported_energy else "final_energy"


def _classical_reference_energy(
    *,
    metrics: dict[str, Any],
    raw_payload: dict[str, Any],
) -> float | None:
    classical_refs = metrics.get("classical_references")
    if not isinstance(classical_refs, dict):
        classical_refs = raw_payload.get("classical_references")
    classical_refs = classical_refs if isinstance(classical_refs, dict) else {}

    return _first_finite(
        classical_refs.get("fci"),
        classical_refs.get("casci"),
        classical_refs.get("hf"),
    )


def _extract_energy_provenance(
    *,
    result: dict[str, Any],
    raw_payload: dict[str, Any],
    algorithm_metrics: dict[str, Any] | None,
) -> dict[str, Any]:
    """Extract final/best/reported/reference energies for persisted result columns."""
    metrics = algorithm_metrics or {}
    sci_package = metrics.get("sci_result_package")
    sci_package = sci_package if isinstance(sci_package, dict) else {}
    trace_values = _finite_trace_values(metrics.get("convergence_trace"))

    final_energy = _first_finite(
        result.get("final_energy"),
        sci_package.get("final_energy"),
        result.get("primary_energy"),
        result.get("energy"),
    )
    best_observed_energy = _first_finite(
        result.get("best_observed_energy"),
        sci_package.get("best_energy"),
        min(trace_values) if trace_values else None,
        result.get("primary_energy"),
        result.get("energy"),
    )
    reported_energy = _first_finite(
        result.get("reported_energy"),
        best_observed_energy,
        result.get("primary_energy"),
        result.get("energy"),
    )
    source = (
        _energy_source(
            result=result,
            sci_package=sci_package,
            best_observed_energy=best_observed_energy,
            reported_energy=reported_energy,
        )
        if reported_energy is not None
        else "unavailable"
    )
    reference_energy = _classical_reference_energy(metrics=metrics, raw_payload=raw_payload)

    signed_error = (
        reported_energy - reference_energy
        if reported_energy is not None and reference_energy is not None
        else None
    )
    reference_basis = result.get("reference_basis") or result.get("basis_set")
    if not isinstance(reference_basis, str):
        reference_basis = None

    convergence = metrics.get("convergence")
    convergence = convergence if isinstance(convergence, dict) else {}
    canonical_scientific_status = convergence.get("scientific_converged")
    canonical_diagnostic = convergence.get("projected_solve_is_diagnostic") is True

    if not _projected_energy_is_reportable(result=result, metrics=metrics):
        return {
            "final_energy": None,
            "best_observed_energy": None,
            "reported_energy": None,
            "reported_energy_is_valid": False,
            "reported_energy_source": "unavailable_unstable_projected_solve",
            "reported_energy_invalid_reason": "unstable_projected_metric",
            "reference_energy": reference_energy,
            "reference_basis": reference_basis,
            "signed_error": None,
        }

    if _projected_energy_is_stabilized_diagnostic(metrics):
        return {
            "final_energy": final_energy,
            "best_observed_energy": best_observed_energy,
            "reported_energy": reported_energy,
            "reported_energy_is_valid": reported_energy is not None,
            "reported_energy_source": "stabilized_projected_diagnostic",
            "projected_solve_is_diagnostic": True,
            "scientific_converged": False,
            "reference_energy": reference_energy,
            "reference_basis": reference_basis,
            "signed_error": signed_error,
        }

    provenance = {
        "final_energy": final_energy,
        "best_observed_energy": best_observed_energy,
        "reported_energy": reported_energy,
        "reported_energy_is_valid": reported_energy is not None,
        "reported_energy_source": (
            "projected_branch_diagnostic" if canonical_diagnostic else source
        ),
        "reference_energy": reference_energy,
        "reference_basis": reference_basis,
        "signed_error": signed_error,
    }
    if "scientific_converged" in convergence:
        provenance["scientific_converged"] = canonical_scientific_status
    if canonical_diagnostic:
        provenance["projected_solve_is_diagnostic"] = True
    return provenance


def _first_mapping(*values: Any) -> dict[str, Any]:
    for value in values:
        if isinstance(value, dict):
            return value
    return {}


def _benchmark_work_ledger(metrics: dict[str, Any]) -> dict[str, Any] | None:
    matrix_summary = metrics.get("matrix_element_summary")
    sci_package = metrics.get("sci_result_package")
    optimizer_diagnostics = metrics.get("optimizer_diagnostics")
    return next(
        (
            candidate
            for candidate in (
                metrics.get("work_ledger"),
                _first_mapping(matrix_summary).get("work_ledger"),
                _first_mapping(sci_package).get("work_ledger"),
                _first_mapping(optimizer_diagnostics).get("work_ledger"),
            )
            if isinstance(candidate, dict)
        ),
        None,
    )


def _build_benchmark_provenance(
    *,
    result: dict[str, Any],
    metrics: dict[str, Any],
    energy_provenance: dict[str, Any],
    converged: bool,
) -> dict[str, Any]:
    execution = _first_mapping(metrics.get("backend_execution"))
    noise_summary = _first_mapping(execution.get("noise_summary"))
    return {
        "schema_version": 1,
        "execution": {
            "requested_target": result.get("backend_target")
            or execution.get("backend_target"),
            "actual_execution_target": execution.get("actual_execution_target"),
            "actual_path_class": execution.get("actual_path_class"),
            "backend_primitives_used": execution.get("backend_primitives_used"),
            "primitive_family": execution.get("primitive_family"),
            "requested_shots": execution.get("requested_shots"),
            "effective_shots": execution.get("effective_shots"),
            "requested_estimator_precision": execution.get("requested_estimator_precision"),
            "effective_estimator_precision": execution.get("effective_estimator_precision"),
            "noise_source": noise_summary.get("source"),
            "noise_fingerprint": noise_summary.get("model_fingerprint_sha256"),
        },
        "work_ledger": _benchmark_work_ledger(metrics),
        "energy": {
            "reported_energy": energy_provenance.get("reported_energy"),
            "reported_energy_is_valid": energy_provenance.get("reported_energy_is_valid"),
            "reported_energy_source": energy_provenance.get("reported_energy_source"),
            "projected_solve_is_diagnostic": bool(
                energy_provenance.get("projected_solve_is_diagnostic", False)
            ),
            "scientific_converged": energy_provenance.get("scientific_converged", converged),
        },
    }
