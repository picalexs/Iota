from __future__ import annotations

import json
from pathlib import Path

from exporter.benchmark_io import (
    CANONICAL_FIELDS,
    SourceBundle,
    compact_manifest,
    load_api_source,
    load_folder_source,
    normalize_api_row,
    summarize_rows,
    write_rows_csv,
    write_rows_json,
)


def _benchmark() -> dict:
    return {
        "id": "benchmark-1",
        "name": "seed campaign",
        "selectedBasis": "sto-3g",
        "entries": [
            {
                "id": "h2:vqe:seed=11",
                "algorithm": "vqe",
                "status": "completed",
                "moleculeId": "molecule-1",
                "runId": "run-1",
                "seed": 11,
                "seedRoles": ["algorithm", "transpiler"],
                "preset": {"key": "h2", "name": "H2"},
            }
        ],
    }


def _run_export() -> dict:
    return {
        "run": {
            "id": "run-1",
            "molecule_id": "molecule-1",
            "status": "COMPLETED",
            "algorithm": "vqe",
            "basis_set": "sto-3g",
            "created_at": "2026-09-20T10:00:00Z",
            "config_json": {
                "advanced_config": {"seed": 11},
                "backend_options": {
                    "backend_name": None,
                    "seed_transpiler": 11,
                },
            },
        },
        "molecule": {"name": "H2"},
        "result": {
            "final_energy": -1.1,
            "reference_energy": -1.2,
            "signed_error": 0.1,
            "iterations": 7,
            "converged": True,
            "created_at": "2026-09-20T10:00:03Z",
            "algorithm_metrics": {
                "benchmark_provenance": {
                    "execution": {
                        "requested_shots": 4096,
                        "effective_shots": None,
                        "requested_estimator_precision": 0.015625,
                        "effective_estimator_precision": 0.015625,
                        "measurement_mode": "precision_sampled",
                        "simulator_method": "automatic",
                        "noise_source": "backend_derived",
                        "noise_fingerprint": "abc123",
                        "actual_execution_target": "aer_simulator",
                        "actual_path_class": "aer_branch_estimator",
                    }
                }
            },
        },
        "execution_segments": [{"duration_seconds": 2.5}],
    }


def test_api_normalization_selects_compact_result_and_seed_roles() -> None:
    run_export = _run_export()
    run_export["result"]["algorithm_metrics"]["convergence"] = {
        "termination_reason": "max_function_evaluations",
        "convergence_value": 0.25,
        "convergence_threshold": 1e-8,
    }
    run_export["result"]["algorithm_metrics"]["optimizer_diagnostics"] = {
        "objective_evaluations": 448,
        "effective_max_function_evaluations": 448,
    }
    row, runtime_source = normalize_api_row(
        benchmark=_benchmark(),
        entry=_benchmark()["entries"][0],
        run_export=run_export,
    )

    assert runtime_source == "execution_segments.duration_seconds"
    assert row["run_id"] == "run-1"
    assert row["seed"] == 11
    assert row["seed_roles"] == ["algorithm", "transpiler"]
    assert row["seed_algorithm"] == 11
    assert row["seed_reference"] is None
    assert row["absolute_error"] == 0.1
    assert row["runtime_seconds"] == 2.5
    assert row["requested_shots"] == 4096
    assert row["effective_shots"] is None
    assert row["effective_estimator_precision"] == 0.015625
    assert row["measurement_mode"] == "precision_sampled"
    assert row["noise_source"] == "backend_derived"
    assert row["actual_path_class"] == "aer_branch_estimator"
    assert row["termination_reason"] == "max_function_evaluations"
    assert row["convergence_value"] == 0.25
    assert row["convergence_threshold"] == 1e-8
    assert row["objective_evaluations"] == 448
    assert row["max_function_evaluations"] == 448
    assert set(row) >= set(CANONICAL_FIELDS)
    assert "raw_result" not in row
    assert "execution_segments" not in row


def test_api_normalization_keeps_sqd_algorithm_and_sampling_seeds_separate() -> None:
    benchmark = _benchmark()
    benchmark["entries"][0]["algorithm"] = "sqd"
    benchmark["entries"][0].pop("seedRoles")
    run_export = _run_export()
    run_export["run"]["algorithm"] = "sqd"
    run_export["run"]["config_json"] = {
        "advanced_config": {"seed": 11, "sampling_vqe_seed": 17},
        "backend_options": {"seed_transpiler": 23},
    }

    row, _ = normalize_api_row(
        benchmark=benchmark,
        entry=benchmark["entries"][0],
        run_export=run_export,
    )

    assert row["seed"] == 11
    assert row["seed_roles"] == ["algorithm", "sampling", "transpiler"]
    assert row["seed_algorithm"] == 11
    assert row["seed_sampling"] == 17
    assert row["seed_transpiler"] == 23


def test_api_normalization_exports_qse_reference_seed() -> None:
    benchmark = _benchmark()
    benchmark["entries"][0]["algorithm"] = "qse"
    benchmark["entries"][0].pop("seed")
    benchmark["entries"][0].pop("seedRoles")
    run_export = _run_export()
    run_export["run"]["algorithm"] = "qse"
    run_export["run"]["config_json"] = {
        "advanced_config": {"reference_method": "vqe", "vqe_reference_seed": 29},
        "backend_options": {},
    }

    row, _ = normalize_api_row(
        benchmark=benchmark,
        entry=benchmark["entries"][0],
        run_export=run_export,
    )

    assert row["seed"] == 29
    assert row["seed_roles"] == ["reference"]
    assert row["seed_reference"] == 29


def test_api_normalization_excludes_projected_diagnostics_from_comparison() -> None:
    run_export = _run_export()
    run_export["result"]["algorithm_metrics"]["benchmark_provenance"]["energy"] = {
        "reported_energy_is_valid": True,
        "projected_solve_is_diagnostic": True,
        "reported_energy_source": "projected_branch_diagnostic",
    }
    run_export["result"]["algorithm_metrics"]["convergence"] = {
        "scientific_converged": False,
        "convergence_failure_reason": "projected_metric_rank_reduced",
    }

    row, _ = normalize_api_row(
        benchmark=_benchmark(),
        entry=_benchmark()["entries"][0],
        run_export=run_export,
    )

    assert row["projected_solve_is_diagnostic"] is True
    assert row["scientific_converged"] is False
    assert row["primary_energy_source"] == "projected_branch_diagnostic"
    assert row["benchmark_eligible"] is False
    assert row["benchmark_exclusion_reason"] == "projected_solve_diagnostic"


def test_api_normalization_recomputes_legacy_qse_pool_eligibility_only_when_opted_in() -> None:
    benchmark = _benchmark()
    benchmark["entries"][0]["algorithm"] = "qse"
    run_export = _run_export()
    run_export["run"]["algorithm"] = "qse"
    run_export["result"].update(
        {
            "final_energy": -1.2,
            "reference_energy": -1.2,
            "converged": True,
        }
    )
    run_export["result"]["algorithm_metrics"].update(
        {
            "execution_mode": "sector_matrix_free",
            "reference_provenance": {"method": "CASCI", "validity_status": "valid"},
            "benchmark_provenance": {
                "benchmark_eligible": False,
                "benchmark_exclusion_reason": "scientific_convergence_not_established",
                "energy": {
                    "reported_energy_is_valid": True,
                    "projected_solve_is_diagnostic": False,
                    "scientific_converged": None,
                },
            },
            "convergence": {
                "scientific_converged": None,
                "projected_solver_converged": True,
                "projected_system_stable": True,
                "convergence_value": 1e-12,
                "convergence_threshold": 1e-8,
                "convergence_failure_reason": "scientific_completeness_evidence_unavailable",
            },
            "relative_residual": 1e-12,
            "convergence_threshold": 1e-8,
            "conditioning_summary": {
                "basis_termination_reason": "candidate_pool_exhausted"
            },
            "matrix_element_summary": {
                "basis_selection": {
                    "basis_termination_reason": "candidate_pool_exhausted",
                    "selected_specs_complete": True,
                }
            },
        }
    )

    persisted, _ = normalize_api_row(
        benchmark=benchmark,
        entry=benchmark["entries"][0],
        run_export=run_export,
    )
    recomputed, _ = normalize_api_row(
        benchmark=benchmark,
        entry=benchmark["entries"][0],
        run_export=run_export,
        recompute_eligibility=True,
    )

    assert persisted["benchmark_eligible"] is False
    assert persisted["eligibility_source"] == "persisted"
    assert recomputed["benchmark_eligible"] is True
    assert recomputed["scientific_converged"] is True
    assert recomputed["convergence_failure_reason"] is None
    assert recomputed["eligibility_source"] == "compatibility_recomputed"


def test_api_normalization_does_not_recompute_measured_qse_pool() -> None:
    benchmark = _benchmark()
    benchmark["entries"][0]["algorithm"] = "qse"
    run_export = _run_export()
    run_export["run"]["algorithm"] = "qse"
    run_export["result"]["converged"] = True
    run_export["result"]["algorithm_metrics"].update(
        {
            "execution_mode": "measured_matrix_elements",
            "reference_provenance": {"method": "CASCI", "validity_status": "valid"},
            "benchmark_provenance": {
                "benchmark_eligible": False,
                "energy": {
                    "reported_energy_is_valid": True,
                    "projected_solve_is_diagnostic": True,
                    "scientific_converged": False,
                },
            },
            "convergence": {
                "projected_solver_converged": True,
                "projected_system_stable": True,
                "convergence_value": 1e-12,
                "convergence_threshold": 1e-8,
            },
            "relative_residual": 1e-12,
            "convergence_threshold": 1e-8,
            "matrix_element_summary": {
                "basis_selection": {
                    "basis_termination_reason": "candidate_pool_exhausted",
                    "selected_specs_complete": True,
                }
            },
        }
    )

    row, _ = normalize_api_row(
        benchmark=benchmark,
        entry=benchmark["entries"][0],
        run_export=run_export,
        recompute_eligibility=True,
    )

    assert row["benchmark_eligible"] is False
    assert row["eligibility_source"] == "persisted"


class FakeApi:
    def __init__(self, benchmark: dict, run_export: dict) -> None:
        self.benchmark = benchmark
        self.run_export = run_export
        self.paths: list[str] = []

    def get(self, path: str) -> object:
        self.paths.append(path)
        if path == "/api/benchmarks/benchmark-1":
            return self.benchmark
        if path == "/api/runs/run-1/export":
            return self.run_export
        raise AssertionError(path)


def test_api_source_fetches_saved_entries_and_preserves_missing_entries() -> None:
    benchmark = _benchmark()
    benchmark["entries"].append(
        {
            "id": "h2:vqe:seed=17",
            "algorithm": "vqe",
            "status": "planned",
            "seed": 17,
            "preset": {"key": "h2", "name": "H2"},
        }
    )
    client = FakeApi(benchmark, _run_export())

    bundle = load_api_source("benchmark-1", base_url="http://unused", client=client)  # type: ignore[arg-type]

    assert client.paths == ["/api/benchmarks/benchmark-1", "/api/runs/run-1/export"]
    assert [row["entry_id"] for row in bundle.rows] == [
        "h2:vqe:seed=11",
        "h2:vqe:seed=17",
    ]
    assert bundle.rows[1]["status"] == "planned"
    assert bundle.rows[1]["run_id"] is None


def test_folder_source_accepts_canonical_json_and_csv_round_trip(tmp_path: Path) -> None:
    rows = [
        {
            "benchmark_id": "benchmark-1",
            "benchmark_name": "seed campaign",
            "entry_id": "h2:vqe:seed=11",
            "run_id": "run-1",
            "molecule_id": "molecule-1",
            "molecule": "H2",
            "algorithm": "vqe",
            "basis_set": "sto-3g",
            "backend_target": "statevector",
            "backend_name": None,
            "seed": 11,
            "seed_roles": ["algorithm"],
            "status": "completed",
            "created_at": None,
            "result_created_at": None,
            "runtime_seconds": 2.0,
            "final_energy": -1.1,
            "reference_energy": -1.2,
            "signed_error": 0.1,
            "absolute_error": 0.1,
            "iterations": 4,
            "converged": True,
            "error_message": None,
        }
    ]
    write_rows_json(rows, tmp_path / "runs.json")
    (tmp_path / "benchmark.json").write_text(json.dumps(_benchmark()), encoding="utf-8")

    loaded_json = load_folder_source(tmp_path)
    assert loaded_json.rows[0]["seed_roles"] == ["algorithm"]

    write_rows_csv(rows, tmp_path / "runs.csv")
    (tmp_path / "runs.json").unlink()
    loaded_csv = load_folder_source(tmp_path)
    assert loaded_csv.rows[0]["seed"] == 11
    assert loaded_csv.rows[0]["converged"] is True


def test_folder_source_preserves_explicit_quality_and_variant_fields(tmp_path: Path) -> None:
    rows = [
        {
            "entry_id": "h2:kqd-balanced:seed=11",
            "variant_id": "kqd-balanced",
            "variant_label": "KQD balanced",
            "variant_mode": "advanced",
            "variant_config_sha256": "config-hash",
            "molecule": "H2",
            "algorithm": "kqd",
            "status": "completed",
            "final_energy": -1.1,
            "reference_energy": -1.2,
            "absolute_error": 0.1,
            "converged": False,
            "reported_energy_is_valid": True,
            "projected_solve_is_diagnostic": True,
            "scientific_converged": False,
            "primary_energy_source": "projected_branch_diagnostic",
            "reference_method": "CASCI",
            "reference_solver_path": "pyscf+ffsim",
            "reference_basis": "sto-3g",
            "reference_active_space": [2, 2],
            "benchmark_eligible": False,
            "benchmark_exclusion_reason": "projected_solve_diagnostic",
        }
    ]
    write_rows_csv(rows, tmp_path / "runs.csv")

    loaded = load_folder_source(tmp_path)
    row = loaded.rows[0]

    assert row["variant_label"] == "KQD balanced"
    assert row["variant_config_sha256"] == "config-hash"
    assert row["benchmark_eligible"] is False
    assert row["benchmark_exclusion_reason"] == "projected_solve_diagnostic"
    assert row["reference_method"] == "CASCI"
    assert row["reference_solver_path"] == "pyscf+ffsim"
    assert row["reference_active_space"] == [2, 2]


def test_folder_source_accepts_create_checkpoint_status_rows(tmp_path: Path) -> None:
    (tmp_path / "benchmark.json").write_text(
        json.dumps({"id": "benchmark-1", "name": "seed campaign", "selectedBasis": "sto-3g"}),
        encoding="utf-8",
    )
    (tmp_path / "submission.json").write_text(
        json.dumps(
            {
                "benchmark_id": "benchmark-1",
                "molecules": [{"id": "molecule-1", "name": "H2"}],
                "entries": [
                    {
                        "entry_id": "h2:vqe:seed=11",
                        "run_id": "run-1",
                        "seed": 11,
                        "seed_roles": ["algorithm"],
                        "status": "queued",
                        "run_config": {
                            "molecule_id": "molecule-1",
                            "algorithm": "vqe",
                            "backend_target": "statevector",
                            "basis_set_override": "sto-3g",
                        },
                        "snapshot": {
                            "id": "h2:vqe:seed=11",
                            "algorithm": "vqe",
                            "moleculeId": "molecule-1",
                            "status": "queued",
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    bundle = load_folder_source(tmp_path)

    assert bundle.rows[0]["run_id"] == "run-1"
    assert bundle.rows[0]["status"] == "queued"
    assert bundle.rows[0]["final_energy"] is None
    assert bundle.rows[0]["molecule"] == "H2"


def test_summary_uses_successful_results_only_and_handles_all_failed() -> None:
    rows = [
        {"algorithm": "vqe", "molecule": "H2", "status": "completed", "absolute_error": 0.2, "converged": True},
        {"algorithm": "vqe", "molecule": "H2", "status": "failed", "absolute_error": None, "converged": None},
        {"algorithm": "sqd", "molecule": "H2", "status": "planned", "absolute_error": None, "converged": None},
    ]

    summary = summarize_rows(rows)

    assert summary["row_count"] == 3
    assert summary["successful_result_count"] == 1
    vqe = next(item for item in summary["by_algorithm"] if item["algorithm"] == "vqe")
    assert vqe["run_count"] == 2
    assert vqe["successful_count"] == 1
    best = summary["best_algorithm_by_molecule"][0]
    assert best["algorithm"] == "vqe"

    failed_summary = summarize_rows(
        [{"algorithm": "vqe", "molecule": "H2", "status": "failed", "absolute_error": None}]
    )
    assert failed_summary["best_algorithm_by_molecule"][0]["algorithm"] is None
    assert failed_summary["best_algorithm_by_molecule"][0]["reason"]


def test_summary_excludes_completed_diagnostic_rows_from_successes() -> None:
    rows = [
        {
            "algorithm": "vqe",
            "molecule": "H2",
            "status": "completed",
            "absolute_error": 0.2,
            "converged": True,
            "benchmark_eligible": True,
        },
        {
            "algorithm": "kqd",
            "molecule": "H2",
            "status": "completed",
            "absolute_error": 0.001,
            "converged": False,
            "projected_solve_is_diagnostic": True,
            "benchmark_eligible": False,
            "benchmark_exclusion_reason": "projected_solve_diagnostic",
        },
    ]

    summary = summarize_rows(rows)

    assert summary["successful_result_count"] == 1
    assert summary["best_algorithm_by_molecule"][0]["algorithm"] == "vqe"


def test_manifest_warns_when_saved_backend_differs_from_actual_runs() -> None:
    manifest = compact_manifest(
        SourceBundle(
            benchmark={"id": "benchmark-1", "selectedBackendName": "ibm_pittsburgh"},
            rows=[{"backend_name": "ibm_boston", "status": "cancelled"}],
            source_type="folder",
            source_id="benchmark-1",
        ),
        files=[],
    )

    assert manifest["actual_backend_names"] == ["ibm_boston"]
    assert manifest["provenance_warnings"] == [
        "saved benchmark backend does not match any actual run backend"
    ]
