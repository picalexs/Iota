#!/usr/bin/env python3
"""Create benchmark plots from an exported folder or a saved QSS benchmark."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from .benchmark_io import (
        ExporterError,
        QssApiClient,
        load_api_source,
        load_folder_source,
        source_signature,
    )
    from .benchmark_plots import render_plots
except ImportError:  # pragma: no cover - direct script execution
    from benchmark_io import ExporterError, QssApiClient, load_api_source, load_folder_source, source_signature
    from benchmark_plots import render_plots


DEFAULT_BASE_URL = "http://localhost:18000"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create plots from a benchmark folder or a saved QSS benchmark."
    )
    parser.add_argument(
        "input_dir",
        nargs="?",
        type=Path,
        help="Folder containing runs.json, runs.csv, or an exported benchmark.",
    )
    parser.add_argument("--benchmark-id", help="Saved QSS benchmark ID to read through the API.")
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"QSS API base URL for --benchmark-id. Default: {DEFAULT_BASE_URL}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Plot output directory. Defaults to <folder>/plots or benchmark_plots/<id>.",
    )
    parser.add_argument(
        "--error-view",
        choices=("absolute", "signed"),
        default="absolute",
        help="Error representation for error plots. Default: absolute.",
    )
    parser.add_argument(
        "--format",
        dest="output_format",
        choices=("png", "svg", "both"),
        default="png",
        help="Plot file format. Default: png.",
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout in seconds.")
    return parser.parse_args(argv)


def _output_dir(args: argparse.Namespace) -> Path:
    if args.output_dir is not None:
        return args.output_dir.expanduser().resolve()
    if args.benchmark_id:
        return (Path("benchmark_plots") / args.benchmark_id).resolve()
    if args.input_dir is None:
        raise ExporterError("Provide a folder or --benchmark-id")
    return (args.input_dir.expanduser().resolve() / "plots").resolve()


def plot_source(
    *,
    input_dir: Path | None = None,
    benchmark_id: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
    output_dir: Path,
    error_view: str = "absolute",
    output_format: str = "png",
    timeout: float = 30.0,
    client: QssApiClient | None = None,
) -> dict[str, Any]:
    """Load one source, render plots, and write a reproducibility manifest."""

    if (input_dir is None) == (benchmark_id is None):
        raise ExporterError("Choose exactly one source: folder or benchmark ID")

    if benchmark_id is not None:
        bundle = load_api_source(
            benchmark_id,
            base_url=base_url,
            client=client or QssApiClient(base_url, timeout=timeout),
        )
    else:
        bundle = load_folder_source(input_dir or Path("."))

    output_dir = output_dir.expanduser().resolve()
    plot_manifest = render_plots(
        bundle.rows,
        output_dir,
        error_view=error_view,
        output_format=output_format,
    )
    plot_manifest.update(
        {
            "source_type": bundle.source_type,
            "source_id": bundle.source_id,
            "source_signature": source_signature(bundle.rows),
        }
    )
    manifest_path = output_dir / "plot_manifest.json"
    manifest_path.write_text(json.dumps(plot_manifest, indent=2) + "\n", encoding="utf-8")
    result = {
        "source_type": bundle.source_type,
        "source_id": bundle.source_id,
        "output_dir": str(output_dir),
        "source_row_count": len(bundle.rows),
        "files": [*plot_manifest["files"], "plot_manifest.json"],
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
        plot_source(
            input_dir=args.input_dir,
            benchmark_id=args.benchmark_id,
            base_url=args.base_url,
            output_dir=_output_dir(args),
            error_view=args.error_view,
            output_format=args.output_format,
            timeout=max(0.1, args.timeout),
        )
    except (ExporterError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
