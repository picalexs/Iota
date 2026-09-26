from __future__ import annotations

import json
from pathlib import Path

import pytest

from exporter.benchmark_io import write_rows_json
from exporter.paper_report import _group_stats, _iqr_bounds, _observed, generate_report


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
    assert result["observed_row_count"] == 2
    assert result["incomplete_row_count"] == 0
    assert (output / "statistics.json").is_file()
    assert (output / "campaign_summary.tex").is_file()
    preset_summary = (output / "preset_summary.tex").read_text(encoding="utf-8")
    assert "Algorithm & Fastest & Balanced & Best accuracy & Custom deep" in preset_summary
    assert "Variant & Algorithm" not in preset_summary
    assert (output / "plots" / "campaign_populations.pdf").is_file()
    assert (output / "plots" / "accuracy_runtime.pdf").is_file()
    stats = json.loads((output / "statistics.json").read_text(encoding="utf-8"))
    assert all(item["observed_count"] == 1 for item in stats["by_campaign_algorithm"])
    assert all(item["q1_observed_runtime_seconds"] == 2.0 for item in stats["by_campaign_algorithm"])
    assert all(item["q3_observed_runtime_seconds"] == 2.0 for item in stats["by_campaign_algorithm"])
    manifest = json.loads((output / "report_manifest.json").read_text(encoding="utf-8"))
    assert "terminal" in manifest["population_definitions"]
    assert "validated" not in manifest["population_definitions"]


def test_finite_non_converged_row_is_terminal_observation() -> None:
    row = _row("vqe", eligible=False)
    row.update(
        {
            "projected_solve_is_diagnostic": False,
            "reported_energy_is_valid": False,
            "benchmark_exclusion_reason": "not_converged",
        }
    )

    assert _observed(row)


def test_group_stats_provides_iqr_bounds_for_error_and_runtime() -> None:
    rows = []
    for seed, error, runtime in zip((11, 17, 23, 29), (0.001, 0.002, 0.003, 0.004), (1, 2, 3, 4)):
        row = _row("sqd", eligible=True, seed=seed)
        row.update(absolute_error=error, runtime_seconds=runtime)
        rows.append(row)

    item = _group_stats(rows, ("algorithm",))[0]

    assert item["median_observed_absolute_error_mHa"] == pytest.approx(2.5)
    assert item["q1_observed_absolute_error_mHa"] == pytest.approx(1.75)
    assert item["q3_observed_absolute_error_mHa"] == pytest.approx(3.25)
    assert item["median_observed_runtime_seconds"] == pytest.approx(2.5)
    assert item["q1_observed_runtime_seconds"] == pytest.approx(1.75)
    assert item["q3_observed_runtime_seconds"] == pytest.approx(3.25)
    assert _iqr_bounds(
        item,
        "median_observed_absolute_error_mHa",
        "q1_observed_absolute_error_mHa",
        "q3_observed_absolute_error_mHa",
    ) == pytest.approx((2.5, 0.75, 0.75))
