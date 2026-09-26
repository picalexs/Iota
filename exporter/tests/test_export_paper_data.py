from __future__ import annotations

import json
from pathlib import Path

from exporter.benchmark_io import write_rows_json
from exporter.export_paper_data import export_paper_data


def test_export_paper_data_writes_campaign_and_report_artifacts(tmp_path: Path) -> None:
    source = tmp_path / "paper-small"
    source.mkdir()
    (source / "benchmark.json").write_text(
        json.dumps({"campaign_id": "paper-small"}),
        encoding="utf-8",
    )
    write_rows_json(
        [
            {
                "benchmark_id": "benchmark-1",
                "entry_id": "h2:vqe:seed=11",
                "molecule": "H2",
                "algorithm": "vqe",
                "status": "completed",
                "seed": 11,
                "runtime_seconds": 1.0,
                "final_energy": -1.1,
                "reference_energy": -1.2,
                "absolute_error": 0.1,
                "reported_energy_is_valid": False,
                "benchmark_eligible": False,
            }
        ],
        source / "runs.json",
    )

    output = tmp_path / "output"
    manifest = export_paper_data([source], output_dir=output, output_format="png")

    assert manifest["row_count"] == 1
    assert manifest["observed_row_count"] == 1
    campaign_dir = output / "campaigns" / "paper-small"
    assert (campaign_dir / "runs.json").is_file()
    assert (campaign_dir / "plots" / "plot_manifest.json").is_file()
    assert (output / "paper-report" / "report_manifest.json").is_file()
    assert (output / "manifest.json").is_file()
