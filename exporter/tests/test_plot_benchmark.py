from __future__ import annotations

import json
from pathlib import Path

from exporter.benchmark_io import write_rows_json
from exporter.plot_benchmark import plot_source


def _rows() -> list[dict[str, object]]:
    return [
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
            "runtime_seconds": 1.0,
            "final_energy": -1.1,
            "reference_energy": -1.2,
            "signed_error": 0.1,
            "absolute_error": 0.1,
            "iterations": 4,
            "converged": True,
            "error_message": None,
        },
        {
            "benchmark_id": "benchmark-1",
            "benchmark_name": "seed campaign",
            "entry_id": "h2:sqd:seed=17",
            "run_id": "run-2",
            "molecule_id": "molecule-1",
            "molecule": "molecule_with_a_long_name_that_must_remain_visible",
            "algorithm": "sqd_with_a_long_algorithm_name",
            "basis_set": "sto-3g",
            "backend_target": "statevector",
            "backend_name": None,
            "seed": 17,
            "seed_roles": ["algorithm"],
            "status": "completed",
            "created_at": None,
            "result_created_at": None,
            "runtime_seconds": 2.0,
            "final_energy": -1.15,
            "reference_energy": -1.2,
            "signed_error": 0.05,
            "absolute_error": 0.05,
            "iterations": 5,
            "converged": False,
            "error_message": None,
        },
        {
            "benchmark_id": "benchmark-1",
            "benchmark_name": "seed campaign",
            "entry_id": "h2:vqe:seed=23",
            "run_id": None,
            "molecule_id": "molecule-1",
            "molecule": "H2",
            "algorithm": "vqe",
            "basis_set": "sto-3g",
            "backend_target": "statevector",
            "backend_name": None,
            "seed": 23,
            "seed_roles": ["algorithm"],
            "status": "planned",
            "created_at": None,
            "result_created_at": None,
            "runtime_seconds": None,
            "final_energy": None,
            "reference_energy": None,
            "signed_error": None,
            "absolute_error": None,
            "iterations": None,
            "converged": None,
            "error_message": None,
        },
    ]


def test_plot_from_folder_writes_manifest_and_all_formats(tmp_path: Path) -> None:
    source_dir = tmp_path / "export"
    source_dir.mkdir()
    write_rows_json(_rows(), source_dir / "runs.json")
    output_dir = tmp_path / "plots"

    result = plot_source(
        input_dir=source_dir,
        output_dir=output_dir,
        output_format="both",
    )

    assert result["source_type"] == "folder"
    manifest = json.loads((output_dir / "plot_manifest.json").read_text(encoding="utf-8"))
    assert manifest["source_row_count"] == 3
    assert manifest["plots"]["error_vs_runtime"]["plotted_count"] == 2
    assert manifest["plots"]["error_vs_runtime"]["excluded_count"] == 1
    assert manifest["plot_schema_version"] == "qss-benchmark-plots.v4"
    assert manifest["population_definitions"]["terminal"].startswith("Completed rows")
    assert "validated" not in manifest["population_definitions"]
    assert len(manifest["files"]) == 6
    for filename in manifest["files"]:
        path = output_dir / filename
        assert path.is_file()
        assert path.stat().st_size > 0


def test_plot_from_folder_supports_pdf_output(tmp_path: Path) -> None:
    source_dir = tmp_path / "export"
    source_dir.mkdir()
    write_rows_json(_rows(), source_dir / "runs.json")
    output_dir = tmp_path / "plots"

    plot_source(input_dir=source_dir, output_dir=output_dir, output_format="pdf")

    assert (output_dir / "error_by_algorithm.pdf").is_file()
    assert (output_dir / "error_vs_runtime.pdf").is_file()


class FakeApi:
    def get(self, path: str) -> object:
        if path == "/api/benchmarks/benchmark-1":
            return {
                "id": "benchmark-1",
                "name": "seed campaign",
                "entries": [
                    {
                        "id": "h2:vqe:seed=11",
                        "algorithm": "vqe",
                        "status": "completed",
                        "runId": "run-1",
                        "seed": 11,
                        "preset": {"key": "h2", "name": "H2"},
                    }
                ],
            }
        if path == "/api/runs/run-1/export":
            return {
                "run": {
                    "id": "run-1",
                    "algorithm": "vqe",
                    "created_at": "2026-09-20T10:00:00Z",
                    "config_json": {"advanced_config": {"seed": 11}},
                },
                "molecule": {"name": "H2"},
                "result": {
                    "final_energy": -1.1,
                    "reference_energy": -1.2,
                    "created_at": "2026-09-20T10:00:01Z",
                },
            }
        raise AssertionError(path)


def test_plot_from_api_reads_saved_benchmark_without_submission(tmp_path: Path) -> None:
    output_dir = tmp_path / "plots"
    result = plot_source(
        benchmark_id="benchmark-1",
        base_url="http://unused",
        output_dir=output_dir,
        client=FakeApi(),  # type: ignore[arg-type]
    )

    assert result["source_type"] == "api"
    assert json.loads((output_dir / "plot_manifest.json").read_text(encoding="utf-8"))["source_id"] == "benchmark-1"
