#!/usr/bin/env python3
"""Export compact QSS benchmark rows from a folder or the live API."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from .benchmark_io import (
        EXPORT_SCHEMA_VERSION,
        ExporterError,
        QssApiClient,
        compact_benchmark,
        compact_manifest,
        load_api_source,
        load_folder_source,
        summarize_rows,
        write_rows_csv,
        write_rows_json,
        write_summary_files,
    )
except ImportError:  # pragma: no cover - direct script execution
    from benchmark_io import (
        EXPORT_SCHEMA_VERSION,
        ExporterError,
        QssApiClient,
        compact_benchmark,
        compact_manifest,
        load_api_source,
        load_folder_source,
        summarize_rows,
        write_rows_csv,
        write_rows_json,
        write_summary_files,
    )


DEFAULT_BASE_URL = "http://localhost:18000"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export compact benchmark data from a folder or a saved QSS benchmark."
    )
    parser.add_argument(
        "input_dir",
        nargs="?",
        type=Path,
        help="Folder containing benchmark rows or a create checkpoint.",
    )
    parser.add_argument("--benchmark-id", help="Saved QSS benchmark ID to fetch through the API.")
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"QSS API base URL for --benchmark-id. Default: {DEFAULT_BASE_URL}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory. Defaults to <folder>/export or benchmark_exports/<id>.",
    )
    parser.add_argument(
        "--include-raw",
        action="store_true",
        help="Save the API benchmark/run response payloads under raw/.",
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout in seconds.")
    return parser.parse_args(argv)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, default=str) + "\n", encoding="utf-8")


def _output_dir(args: argparse.Namespace) -> Path:
    if args.output_dir is not None:
        return args.output_dir.expanduser().resolve()
    if args.benchmark_id:
        return (Path("benchmark_exports") / args.benchmark_id).resolve()
    if args.input_dir is None:
        raise ExporterError("Provide a folder or --benchmark-id")
    return (args.input_dir.expanduser().resolve() / "export").resolve()


def export_source(
    *,
    input_dir: Path | None = None,
    benchmark_id: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
    output_dir: Path,
    include_raw: bool = False,
    timeout: float = 30.0,
    client: QssApiClient | None = None,
) -> dict[str, Any]:
    if (input_dir is None) == (benchmark_id is None):
        raise ExporterError("Choose exactly one source: folder or benchmark ID")

    if benchmark_id is not None:
        bundle = load_api_source(
            benchmark_id,
            base_url=base_url,
            client=client or QssApiClient(base_url, timeout=timeout),
            include_raw=include_raw,
        )
    else:
        bundle = load_folder_source(input_dir or Path("."))

    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "benchmark.json", compact_benchmark(bundle.benchmark))
    write_rows_json(bundle.rows, output_dir / "runs.json")
    write_rows_csv(bundle.rows, output_dir / "runs.csv")
    summary = summarize_rows(bundle.rows)
    write_summary_files(summary, output_dir)

    if include_raw and bundle.source_type == "api":
        raw_dir = output_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        if bundle.raw_benchmark is not None:
            _write_json(raw_dir / "benchmark.json", bundle.raw_benchmark)
        for run_id, payload in sorted(bundle.raw_runs.items()):
            _write_json(raw_dir / f"run_{run_id}.json", payload)

    files = [
        "benchmark.json",
        "runs.json",
        "runs.csv",
        "summaries/summary.json",
        "summaries/by_algorithm.csv",
        "summaries/by_algorithm_path.csv",
        "summaries/by_molecule.csv",
        "summaries/by_variant.csv",
        "summaries/by_seed.csv",
        "summaries/field_presence.csv",
        "summaries/best_algorithm_by_molecule.csv",
    ]
    if include_raw and bundle.source_type == "api":
        files.extend(
            [
                "raw/benchmark.json",
                *[f"raw/run_{run_id}.json" for run_id in sorted(bundle.raw_runs)],
            ]
        )
    manifest = compact_manifest(bundle, files=files)
    manifest["schema_version"] = EXPORT_SCHEMA_VERSION
    _write_json(output_dir / "manifest.json", manifest)
    result = {
        "source_type": bundle.source_type,
        "source_id": bundle.source_id,
        "output_dir": str(output_dir),
        "row_count": len(bundle.rows),
        "successful_result_count": summary["successful_result_count"],
        "files": files,
    }
    print(json.dumps(result, indent=2))
    return result


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.input_dir is None and args.benchmark_id is None:
        print("error: provide a folder or --benchmark-id", file=sys.stderr)
        return 2
    if args.input_dir is not None and args.benchmark_id is not None:
        print("error: choose a folder or --benchmark-id, not both", file=sys.stderr)
        return 2
    try:
        export_source(
            input_dir=args.input_dir,
            benchmark_id=args.benchmark_id,
            base_url=args.base_url,
            output_dir=_output_dir(args),
            include_raw=args.include_raw,
            timeout=max(0.1, args.timeout),
        )
    except ExporterError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
