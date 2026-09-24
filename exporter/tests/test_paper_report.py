from __future__ import annotations

import json
from pathlib import Path

from exporter.benchmark_io import write_rows_json
from exporter.paper_report import _observation_bucket, _observed, generate_report


def _row(algorithm: str, *, eligible: bool, seed: int = 11) -> dict[str, object]:
    return {
        "benchmark_id": "benchmark-1",
        "benchmark_name": "paper test",
        "entry_id": f"h2:{algorithm}:seed={seed}",
        "variant_id": f"{algorithm}-balanced",
        "variant_label": f"{algorithm.upper()} balanced",
        "molecule": "Hydrogen (H₂)",
        "algorithm": algorithm,
        "status": "completed",
        "seed": seed,
        "runtime_seconds": 2.0,
        "final_energy": -1.1,
        "reference_energy": -1.2,
        "absolute_error": 0.1,
        "converged": eligible,
        "reported_energy_is_valid": True,
        "projected_solve_is_diagnostic": not eligible,
        "scientific_converged": eligible,
        "benchmark_eligible": eligible,
        "benchmark_exclusion_reason": None if eligible else "projected_solve_diagnostic",
    }


def test_generate_report_writes_stats_latex_and_pdf(tmp_path: Path) -> None:
    source = tmp_path / "paper-seed-role-study"
    source.mkdir()
    write_rows_json(
        [_row("sqd", eligible=True), _row("vqe", eligible=False, seed=17)],
        source / "runs.json",
    )
    (source / "benchmark.json").write_text(
        json.dumps({"id": "benchmark-1", "campaignId": "paper-seed-role-study"}),
        encoding="utf-8",
    )

    output = tmp_path / "report"
    result = generate_report([source], output, output_format="pdf")

    assert result["row_count"] == 2
    assert result["eligible_row_count"] == 1
    assert (output / "statistics.json").is_file()
    assert (output / "campaign_summary.tex").is_file()
    assert (output / "plots" / "eligibility_matrix.pdf").is_file()
    assert (output / "plots" / "accuracy_runtime.pdf").is_file()
    stats = json.loads((output / "statistics.json").read_text(encoding="utf-8"))
    assert stats["by_campaign_algorithm"][0]["eligible_count"] in {0, 1}
    manifest = json.loads((output / "report_manifest.json").read_text(encoding="utf-8"))
    assert "unvalidated" in manifest["population_definitions"]


def test_finite_non_converged_row_is_unvalidated_observation() -> None:
    row = _row("vqe", eligible=False)
    row.update(
        {
            "projected_solve_is_diagnostic": False,
            "benchmark_exclusion_reason": "not_converged",
        }
    )

    assert _observed(row)
    assert _observation_bucket(row) == "unvalidated"
