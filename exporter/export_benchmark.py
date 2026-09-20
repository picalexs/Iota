#!/usr/bin/env python3
"""Export rows, summaries, and an interpretation report for one run."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


BUNDLE_ROOT = Path(__file__).resolve().parent
ROW_CANDIDATES = (
    "benchmark_rows_pipeline.json",
    "benchmark_rows.json",
    "benchmark_rows_pipeline.csv",
    "benchmark_rows.csv",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export machine-readable rows and summaries from one benchmark run."
    )
    parser.add_argument(
        "input_dir",
        type=Path,
        help="Run directory containing benchmark row JSON or CSV.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Export directory. Default: <input_dir>/export.",
    )
    return parser.parse_args(argv)


def _load_rows(input_dir: Path) -> tuple[Path, list[dict[str, Any]]]:
    for name in ROW_CANDIDATES:
        path = input_dir / name
        if not path.is_file():
            continue
        if path.suffix == ".json":
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
                raise ValueError(f"Expected a JSON list of row objects in {path}")
            return path, [dict(row) for row in value]
        with path.open(newline="", encoding="utf-8") as handle:
            return path, [dict(row) for row in csv.DictReader(handle)]
    expected = ", ".join(ROW_CANDIDATES)
    raise FileNotFoundError(f"No benchmark row file found in {input_dir}; expected {expected}")


def _write_rows_csv(rows: list[dict[str, Any]], path: Path) -> None:
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    input_dir = args.input_dir.expanduser()
    if not input_dir.is_absolute():
        input_dir = BUNDLE_ROOT / input_dir
    input_dir = input_dir.resolve()
    if args.output_dir is not None:
        output_dir = args.output_dir.expanduser()
        if not output_dir.is_absolute():
            output_dir = BUNDLE_ROOT / output_dir
        output_dir = output_dir.resolve()
    else:
        output_dir = input_dir / "export"
    output_dir.mkdir(parents=True, exist_ok=True)

    source_path, rows = _load_rows(input_dir)
    if not rows:
        raise ValueError(f"Benchmark row file is empty: {source_path}")

    from quantum_diag.analyze_benchmark_report import _build_markdown
    from quantum_diag.results_aggregation import (
        best_method_per_molecule,
        export_csv,
        summarize_by_method,
        summarize_by_molecule,
        to_dataframe,
    )

    canonical_json = output_dir / "benchmark_rows.json"
    canonical_json.write_text(json.dumps(rows, indent=2, default=str) + "\n", encoding="utf-8")
    _write_rows_csv(rows, output_dir / "benchmark_rows.csv")

    dataframe = to_dataframe(rows)
    export_csv(summarize_by_method(dataframe), str(output_dir / "summary_by_method.csv"))
    export_csv(summarize_by_molecule(dataframe), str(output_dir / "summary_by_molecule.csv"))
    try:
        export_csv(
            best_method_per_molecule(dataframe),
            str(output_dir / "best_method_per_molecule.csv"),
        )
    except (KeyError, ValueError):
        # A run with no valid error values has no meaningful best method.
        (output_dir / "best_method_per_molecule.csv").write_text(
            "molecule,method,mean_energy_error\n", encoding="utf-8"
        )

    (output_dir / "benchmark_interpretation.md").write_text(
        _build_markdown(rows), encoding="utf-8"
    )
    manifest = {
        "source": source_path.name,
        "row_count": len(rows),
        "files": sorted(path.name for path in output_dir.iterdir() if path.is_file()),
    }
    (output_dir / "export_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Exported {len(rows)} rows from {source_path}")
    print(f"Output directory: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
