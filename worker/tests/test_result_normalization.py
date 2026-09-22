"""Unit tests for pure worker result normalization."""

from datetime import UTC, datetime

import pytest

from worker.exceptions import InvalidResultError
from worker.jobs.result_normalization import (
    build_terminal_latest_estimate,
    normalize_result_for_persistence,
    terminal_runtime_metadata,
)


def test_normalize_result_preserves_provenance_and_uses_best_observation() -> None:
    normalized = normalize_result_for_persistence(
        {
            "algorithm": "vqe",
            "energy": -1.0,
            "iterations": 3,
            "optimal_parameters": [0.1, 0.2],
            "converged": True,
            "algorithm_metrics": {
                "convergence_trace": [-0.8, -1.2],
                "classical_references": {"fci": -1.1},
            },
            "reference_basis": "sto-3g",
        }
    )

    energy, iterations, parameters, converged, raw_payload, metrics, provenance = normalized
    assert energy == pytest.approx(-1.2)
    assert iterations == 3
    assert parameters == [0.1, 0.2]
    assert converged is True
    assert raw_payload["algorithm"] == "vqe"
    assert metrics == raw_payload["algorithm_metrics"]
    assert provenance == {
        "final_energy": -1.0,
        "best_observed_energy": -1.2,
        "reported_energy": -1.2,
        "reported_energy_is_valid": True,
        "reported_energy_source": "best_observed_energy",
        "reference_energy": -1.1,
        "reference_basis": "sto-3g",
        "signed_error": pytest.approx(-0.1),
    }


def test_normalize_result_builds_canonical_benchmark_provenance() -> None:
    normalized = normalize_result_for_persistence(
        {
            "algorithm": "kqd",
            "backend_target": "ibm_runtime",
            "energy": -1.2,
            "iterations": 2,
            "converged": False,
                "algorithm_metrics": {
                    "backend_execution": {
                        "actual_execution_target": "local_classical",
                        "actual_path_class": "sector_matrix_free",
                        "requested_device": None,
                        "actual_device": None,
                        "aer_version": None,
                        "backend_primitives_used": False,
                    "primitive_family": None,
                    "requested_shots": 4096,
                    "effective_shots": None,
                    "requested_estimator_precision": 0.015625,
                    "effective_estimator_precision": 0.0,
                    "noise_summary": {"enabled": False},
                },
                "matrix_element_summary": {
                    "work_ledger": {"ledger_version": 1, "primitive_run_calls": 2}
                },
            },
        }
    )

    metrics = normalized[5]
    assert metrics is not None
    assert metrics["benchmark_provenance"] == {
        "schema_version": 2,
        "execution": {
            "requested_target": "ibm_runtime",
            "actual_execution_target": "local_classical",
            "actual_path_class": "sector_matrix_free",
            "requested_device": None,
            "actual_device": None,
            "aer_version": None,
            "backend_primitives_used": False,
            "primitive_family": None,
            "requested_shots": 4096,
            "effective_shots": None,
            "requested_estimator_precision": 0.015625,
            "effective_estimator_precision": 0.0,
            "measurement_mode": None,
            "simulator_method": None,
            "noise_source": None,
            "noise_fingerprint": None,
        },
        "work_ledger": {"ledger_version": 1, "primitive_run_calls": 2},
        "reference": {},
        "benchmark_eligible": False,
        "benchmark_exclusion_reason": "reference_provenance_unavailable",
        "energy": {
            "reported_energy": -1.2,
            "reported_energy_is_valid": True,
            "reported_energy_source": "best_observed_energy",
            "projected_solve_is_diagnostic": False,
            "scientific_converged": False,
        },
    }


def test_normalize_marks_valid_casci_result_benchmark_eligible() -> None:
    normalized = normalize_result_for_persistence(
        {
            "algorithm": "vqe",
            "energy": -1.13,
            "iterations": 3,
            "converged": True,
            "algorithm_metrics": {
                "classical_references": {"fci": -1.15},
                "reference_provenance": {
                    "method": "CASCI",
                    "validity_status": "valid",
                },
            },
        }
    )

    benchmark_provenance = normalized[5]["benchmark_provenance"]
    assert benchmark_provenance["benchmark_eligible"] is True
    assert benchmark_provenance["benchmark_exclusion_reason"] is None


def test_normalize_result_preserves_indeterminate_scientific_status() -> None:
    normalized = normalize_result_for_persistence(
        {
            "algorithm": "kqd",
            "energy": -1.0,
            "iterations": 1,
            "converged": True,
            "algorithm_metrics": {
                "convergence": {
                    "scientific_converged": None,
                    "convergence_failure_reason": "full_space_residual_unavailable",
                }
            },
        }
    )

    assert normalized[-1]["scientific_converged"] is None
    assert normalized[5]["benchmark_provenance"]["energy"]["scientific_converged"] is None


@pytest.mark.parametrize(
    "result",
    [
        {"algorithm": "vqe"},
        {"algorithm": "vqe", "energy": float("nan")},
        {"algorithm": "vqe", "energy": float("inf")},
        {
            "algorithm": "vqe",
            "algorithm_metrics": {"classical_references": {"fci": -1.1}},
        },
    ],
)
def test_normalize_marks_missing_or_non_finite_energy_invalid(result: dict) -> None:
    energy, _, _, _, _, _, provenance = normalize_result_for_persistence(result)

    assert energy == 0.0
    assert provenance["final_energy"] is None
    assert provenance["best_observed_energy"] is None
    assert provenance["reported_energy"] is None
    assert provenance["reported_energy_is_valid"] is False
    assert provenance["reported_energy_source"] == "unavailable"


def test_normalize_accepts_zero_as_a_valid_algorithm_energy() -> None:
    normalized = normalize_result_for_persistence(
        {"algorithm": "vqe", "energy": 0.0, "iterations": 1}
    )

    energy, _, _, _, _, _, provenance = normalized

    assert energy == 0.0
    assert provenance["reported_energy"] == 0.0
    assert provenance["reported_energy_is_valid"] is True


@pytest.mark.parametrize("iterations", [-1, 1.5, float("nan"), float("inf"), True, "3"])
def test_normalize_rejects_invalid_iteration_counts(iterations: object) -> None:
    with pytest.raises(InvalidResultError, match="iterations"):
        normalize_result_for_persistence({"energy": -1.0, "iterations": iterations})


def test_normalize_rejects_stabilized_branch_energy_without_residual() -> None:
    normalized = normalize_result_for_persistence(
        {
            "algorithm": "kqd",
            "energy": -1.11,
            "primary_energy": -1.11,
            "algorithm_metrics": {
                "matrix_element_summary": {"matrix_element_strategy": "branch_estimator"},
                "stability_summary": {"stability_state": "stabilized", "dropped_rank": 1},
            },
        }
    )

    assert normalized[0] == 0.0
    assert normalized[-1]["reported_energy"] is None
    assert normalized[-1]["reported_energy_is_valid"] is False
    assert normalized[-1]["reported_energy_source"] == (
        "unavailable_unstable_projected_solve"
    )
    assert normalized[-1]["reported_energy_invalid_reason"] == "unstable_projected_metric"


def test_normalize_rejects_invalid_local_qfd_energy() -> None:
    normalized = normalize_result_for_persistence(
        {
            "algorithm": "qfd",
            "energy": 0.0,
            "primary_energy": 0.0,
            "algorithm_metrics": {
                "matrix_element_summary": {"matrix_element_strategy": "dense_classical"},
                "stability_summary": {"stability_state": "invalid", "retained_rank": 0},
            },
        }
    )

    assert normalized[0] == 0.0
    assert normalized[-1]["reported_energy"] is None
    assert normalized[-1]["reported_energy_is_valid"] is False
    assert normalized[-1]["reported_energy_source"] == (
        "unavailable_unstable_projected_solve"
    )


def test_normalize_rejects_invalid_qfd_energy_without_matrix_summary() -> None:
    normalized = normalize_result_for_persistence(
        {
            "algorithm": "qfd",
            "energy": 0.0,
            "primary_energy": 0.0,
            "algorithm_metrics": {
                "stability_summary": {"stability_state": "invalid", "retained_rank": 0},
            },
        }
    )

    assert normalized[0] == 0.0
    assert normalized[-1]["reported_energy"] is None
    assert normalized[-1]["reported_energy_is_valid"] is False
    assert normalized[-1]["reported_energy_source"] == (
        "unavailable_unstable_projected_solve"
    )
    assert normalized[-1]["reported_energy_invalid_reason"] == "unstable_projected_metric"


def test_normalize_reports_stabilized_branch_energy_as_diagnostic() -> None:
    normalized = normalize_result_for_persistence(
        {
            "algorithm": "kqd",
            "energy": -1.11,
            "primary_energy": -1.11,
            "algorithm_metrics": {
                "matrix_element_summary": {"matrix_element_strategy": "branch_estimator"},
                "stability_summary": {
                    "stability_state": "stabilized",
                    "dropped_rank": 1,
                    "retained_rank": 3,
                    "relative_projected_ritz_residual": 1e-3,
                },
            },
        }
    )

    provenance = normalized[-1]
    assert provenance["reported_energy"] == -1.11
    assert provenance["reported_energy_is_valid"] is True
    assert provenance["reported_energy_source"] == "stabilized_projected_diagnostic"
    assert provenance["projected_solve_is_diagnostic"] is True
    assert provenance["scientific_converged"] is False
    assert "reported_energy_invalid_reason" not in provenance


@pytest.mark.parametrize("algorithm", ["kqd", "qfd"])
def test_normalize_reports_rank_reduced_exact_energy_as_diagnostic(algorithm: str) -> None:
    normalized = normalize_result_for_persistence(
        {
            "algorithm": algorithm,
            "energy": -1.1372744055,
            "primary_energy": -1.1372744055,
            "algorithm_metrics": {
                "matrix_element_summary": {"matrix_element_strategy": "dense_classical"},
                "stability_summary": {
                    "stability_state": "stabilized",
                    "dropped_rank": 1,
                    "retained_rank": 7,
                    "relative_generalized_residual": 1e-15,
                },
            },
        }
    )

    provenance = normalized[-1]
    assert provenance["reported_energy"] == pytest.approx(-1.1372744055)
    assert provenance["reported_energy_is_valid"] is True
    assert provenance["reported_energy_source"] == "stabilized_projected_diagnostic"
    assert provenance["projected_solve_is_diagnostic"] is True
    assert provenance["scientific_converged"] is False
    assert "reported_energy_invalid_reason" not in provenance


def test_normalize_rejects_stabilized_branch_energy_with_nonfinite_residual() -> None:
    normalized = normalize_result_for_persistence(
        {
            "algorithm": "qfd",
            "energy": -1.07,
            "primary_energy": -1.07,
            "algorithm_metrics": {
                "matrix_element_summary": {"matrix_element_strategy": "branch_estimator"},
                "stability_summary": {
                    "stability_state": "stabilized",
                    "dropped_rank": 1,
                    "retained_rank": 0,
                    "relative_projected_ritz_residual": float("nan"),
                },
            },
        }
    )

    assert normalized[-1]["reported_energy"] is None
    assert normalized[-1]["reported_energy_is_valid"] is False
    assert normalized[-1]["reported_energy_invalid_reason"] == "unstable_projected_metric"


def test_zero_classical_reference_is_not_dropped() -> None:
    normalized = normalize_result_for_persistence(
        {
            "algorithm": "vqe",
            "energy": 0.25,
            "algorithm_metrics": {"classical_references": {"fci": 0.0, "hf": -1.0}},
        }
    )

    assert normalized[-1]["reference_energy"] == 0.0
    assert normalized[-1]["signed_error"] == 0.25


def test_terminal_runtime_metadata_ignores_non_finite_runtime() -> None:
    finished_at = datetime(2026, 9, 4, 12, 30, tzinfo=UTC)

    assert terminal_runtime_metadata(
        finished_at=finished_at,
        result={"runtime_seconds": 2.5},
    ) == {
        "run_finished_at": "2026-09-04T12:30:00+00:00",
        "runtime_seconds": 2.5,
        "runtime_basis": "worker_execution_segment_monotonic",
    }
    assert terminal_runtime_metadata(
        finished_at=finished_at,
        result={"runtime_seconds": float("nan")},
    ) == {"run_finished_at": "2026-09-04T12:30:00+00:00"}


def test_terminal_estimate_uses_larger_persisted_iteration_count() -> None:
    finished_at = datetime(2026, 9, 4, 12, 30, tzinfo=UTC)
    result = {
        "algorithm": "vqe",
        "energy": -1.2,
        "iterations": 4,
        "runtime_seconds": 6.0,
    }
    normalized = normalize_result_for_persistence(result)

    estimate = build_terminal_latest_estimate(
        result=result,
        finished_at=finished_at,
        latest_estimate={
            "algorithm": "vqe",
            "estimated_total_iterations": 10,
            "estimated_remaining_iterations": 8,
        },
        normalized_result=normalized,
    )

    assert estimate == {
        "source": "telemetry",
        "algorithm": "vqe",
        "estimated_total_iterations": 4,
        "estimated_remaining_iterations": 0,
        "estimated_total_seconds": 6.0,
        "estimated_remaining_seconds": 0.0,
        "confidence": 1.0,
        "updated_at": "2026-09-04T12:30:00+00:00",
        "estimated_seconds_per_iteration": 1.5,
    }


def test_terminal_estimate_preserves_nested_workload_metadata() -> None:
    finished_at = datetime(2026, 9, 4, 12, 30, tzinfo=UTC)
    result = {
        "algorithm": "sqd",
        "energy": -1.2,
        "iterations": 2,
        "runtime_seconds": 6.0,
    }
    normalized = normalize_result_for_persistence(result)

    estimate = build_terminal_latest_estimate(
        result=result,
        finished_at=finished_at,
        latest_estimate={
            "algorithm": "sqd",
            "estimated_primary_iterations": 8,
            "estimated_reference_iterations": 258,
            "estimated_total_work_units": 266,
            "work_unit_policy": (
                "sqd_recovery_rounds_plus_sampling_vqe_objective_evaluations"
            ),
            "reference_workload": "sampling_vqe",
        },
        normalized_result=normalized,
    )

    assert estimate is not None
    assert estimate["estimated_primary_iterations"] == 8
    assert estimate["estimated_reference_iterations"] == 258
    assert estimate["estimated_total_work_units"] == 266
    assert estimate["reference_workload"] == "sampling_vqe"
