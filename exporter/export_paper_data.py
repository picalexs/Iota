#!/usr/bin/env python3
"""Export all paper campaign data and report artifacts under exporter/output."""

from __future__ import annotations

import argparse
import csv
import json
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from .benchmark_io import ExporterError
    from .export_benchmark import export_source
    from .paper_report import generate_report
    from .plot_benchmark import plot_source
except ImportError:  # pragma: no cover - direct script execution
    from benchmark_io import ExporterError
    from export_benchmark import export_source
    from paper_report import generate_report
    from plot_benchmark import plot_source


DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "output"
PAPER_CAMPAIGN_PREFIX = "paper-"
DATA_SCHEMA_VERSION = "qss-paper-data.v1"


def _campaign_id(source: Mapping[str, Any], fallback: Path) -> str:
    value = source.get("campaign_id") or source.get("campaignId")
    return str(value or fallback.name)


def _campaign_sources(source_root: Path) -> list[Path]:
    if not source_root.is_dir():
        raise ExporterError(f"Campaign source root does not exist: {source_root}")
    candidates = [
        path
        for path in sorted(source_root.glob(f"{PAPER_CAMPAIGN_PREFIX}*"))
        if path.is_dir()
        and (
            (path / "benchmark.json").is_file()
            or (path / "export").is_dir()
            or (path / "submission.json").is_file()
        )
    ]
    if not candidates:
        raise ExporterError(f"No paper campaign folders found under {source_root}")
    return candidates


def _write_rows_file(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _split_combined_report(report_dir: Path, temporary_dir: Path) -> list[Path]:
    rows_path = report_dir / "rows.csv"
    if not rows_path.is_file():
        raise ExporterError(f"Combined report has no rows.csv: {report_dir}")

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with rows_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            campaign_id = str(row.get("campaign_id") or "").strip()
            if not campaign_id:
                raise ExporterError(f"Combined report row has no campaign_id: {rows_path}")
            grouped[campaign_id].append(dict(row))

    sources: list[Path] = []
    for campaign_id, rows in sorted(grouped.items()):
        source_dir = temporary_dir / campaign_id
        source_dir.mkdir(parents=True, exist_ok=True)
        (source_dir / "benchmark.json").write_text(
            json.dumps({"campaign_id": campaign_id, "name": campaign_id}, indent=2) + "\n",
            encoding="utf-8",
        )
        _write_rows_file(source_dir / "runs.csv", rows)
        sources.append(source_dir)
    return sources


def _export_campaign(
    source_dir: Path,
    campaigns_dir: Path,
    *,
    output_format: str,
) -> dict[str, Any]:
    source_benchmark = {}
    benchmark_path = source_dir / "benchmark.json"
    if benchmark_path.is_file():
        value = json.loads(benchmark_path.read_text(encoding="utf-8"))
        if isinstance(value, Mapping):
            source_benchmark = dict(value)
    campaign_id = _campaign_id(source_benchmark, source_dir)
    campaign_dir = campaigns_dir / campaign_id
    export_source(input_dir=source_dir, output_dir=campaign_dir)
    plot_result = plot_source(
        input_dir=campaign_dir,
        output_dir=campaign_dir / "plots",
        output_format=output_format,
    )
    return {
        "campaign_id": campaign_id,
        "directory": str(campaign_dir.relative_to(campaigns_dir.parent)),
        "row_count": plot_result["source_row_count"],
        "plot_manifest": str(
            (campaign_dir / "plots" / "plot_manifest.json").relative_to(campaigns_dir.parent)
        ),
    }


def export_paper_data(
    input_dirs: Iterable[Path] | None = None,
    *,
    source_root: Path | None = None,
    combined_report_dir: Path | None = None,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    output_format: str = "both",
) -> dict[str, Any]:
    """Export campaign bundles, campaign plots, and the combined paper report."""

    selected_inputs = list(input_dirs or [])
    if sum(bool(value) for value in (selected_inputs, source_root, combined_report_dir)) != 1:
        raise ExporterError(
            "Choose exactly one source: campaign folders, --source-root, or --combined-report-dir"
        )

    output_dir = output_dir.expanduser().resolve()
    campaigns_dir = output_dir / "campaigns"
    campaigns_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="qss-paper-data-") as temporary_name:
        if combined_report_dir is not None:
            sources = _split_combined_report(
                combined_report_dir.expanduser().resolve(),
                Path(temporary_name),
            )
        elif source_root is not None:
            sources = _campaign_sources(source_root.expanduser().resolve())
        else:
            sources = [path.expanduser().resolve() for path in selected_inputs]

        campaign_records = [
            _export_campaign(source, campaigns_dir, output_format=output_format)
            for source in sources
        ]

    report_dir = output_dir / "paper-report"
    report = generate_report(
        [output_dir / record["directory"] for record in campaign_records],
        report_dir,
        output_format=output_format,
    )
    manifest = {
        "schema_version": DATA_SCHEMA_VERSION,
        "output_dir": str(output_dir),
        "campaigns": campaign_records,
        "paper_report_dir": str(report_dir.relative_to(output_dir)),
        "paper_report_manifest": str(
            (report_dir / "report_manifest.json").relative_to(output_dir)
        ),
        "row_count": report["row_count"],
        "observed_row_count": report["observed_row_count"],
        "incomplete_row_count": report["incomplete_row_count"],
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export paper campaign data and plots under exporter/output."
    )
    parser.add_argument(
        "input_dirs",
        nargs="*",
        type=Path,
        help="Campaign folders. Use --source-root or --combined-report-dir for discovery.",
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        help="Root containing paper-* campaign folders.",
    )
    parser.add_argument(
        "--combined-report-dir",
        type=Path,
        help="Migrate a previous paper report containing rows.csv.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output root. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--format",
        dest="output_format",
        choices=("pdf", "png", "svg", "both"),
        default="both",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.input_dirs and (args.source_root or args.combined_report_dir):
        print("error: choose campaign folders, --source-root, or --combined-report-dir")
        return 2
    try:
        result = export_paper_data(
            args.input_dirs,
            source_root=args.source_root,
            combined_report_dir=args.combined_report_dir,
            output_dir=args.output_dir,
            output_format=args.output_format,
        )
    except (ExporterError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}")
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
