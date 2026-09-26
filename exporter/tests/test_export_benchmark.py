from __future__ import annotations

import json
from pathlib import Path

from exporter.export_benchmark import export_source


class FakeApi:
    def get(self, path: str) -> object:
        if path == "/api/benchmarks/benchmark-1":
            return {
                "id": "benchmark-1",
                "name": "H2 seeds",
                "selectedBasis": "sto-3g",
                "entries": [
                    {
                        "id": "h2:vqe:seed=11",
                        "algorithm": "vqe",
                        "seed": 11,
                        "seedRoles": ["algorithm"],
                        "status": "completed",
                        "runId": "run-1",
                        "preset": {"key": "h2", "name": "H2"},
                    }
                ],
            }
        if path == "/api/runs/run-1/export":
            return {
                "run": {
                    "id": "run-1",
                    "molecule_id": "molecule-1",
                    "status": "COMPLETED",
                    "algorithm": "vqe",
                    "basis_set": "sto-3g",
                    "created_at": "2026-09-20T10:00:00Z",
                    "config_json": {"advanced_config": {"seed": 11}},
                },
                "molecule": {"name": "H2"},
                "result": {
                    "final_energy": -1.1,
                    "reference_energy": -1.2,
                    "signed_error": 0.1,
                    "iterations": 3,
                    "converged": True,
                    "created_at": "2026-09-20T10:00:01Z",
                },
                "events": [{"type": "status_changed", "payload": {"secret": "not exported"}}],
            }
        raise AssertionError(path)


def test_export_from_api_writes_compact_default_files(tmp_path: Path) -> None:
    output_dir = tmp_path / "export"
    result = export_source(
        benchmark_id="benchmark-1",
        base_url="http://unused",
        output_dir=output_dir,
        client=FakeApi(),  # type: ignore[arg-type]
    )

    assert result["row_count"] == 1
    assert result["successful_result_count"] == 1
    assert (output_dir / "runs.json").is_file()
    assert (output_dir / "runs.csv").is_file()
    assert (output_dir / "summaries" / "by_algorithm.csv").is_file()
    assert (output_dir / "summaries" / "best_algorithm_by_molecule.csv").is_file()
    assert (output_dir / "manifest.json").is_file()
    assert not (output_dir / "raw").exists()
    payload = json.loads((output_dir / "runs.json").read_text(encoding="utf-8"))
    assert payload[0]["seed"] == 11
    assert "events" not in payload[0]
    assert "raw_result" not in payload[0]


def test_export_from_api_can_opt_in_to_raw_payloads(tmp_path: Path) -> None:
    output_dir = tmp_path / "export"
    export_source(
        benchmark_id="benchmark-1",
        base_url="http://unused",
        output_dir=output_dir,
        include_raw=True,
        client=FakeApi(),  # type: ignore[arg-type]
    )

    raw_run = json.loads((output_dir / "raw" / "run_run-1.json").read_text(encoding="utf-8"))
    assert raw_run["events"][0]["payload"]["secret"] == "not exported"


def test_export_from_folder_supports_legacy_rows(tmp_path: Path) -> None:
    (tmp_path / "benchmark_rows.json").write_text(
        json.dumps(
            [
                {
                    "method": "VQE",
                    "molecule": "H2",
                    "status": "completed",
                    "energy_error": 0.2,
                    "seed": 11,
                }
            ]
        ),
        encoding="utf-8",
    )
    result = export_source(output_dir=tmp_path / "export", input_dir=tmp_path)
    assert result["source_type"] == "folder"
    rows = json.loads((tmp_path / "export" / "runs.json").read_text(encoding="utf-8"))
    assert rows[0]["algorithm"] == "vqe"
    assert rows[0]["absolute_error"] == 0.2
