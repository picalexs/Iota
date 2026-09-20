#!/usr/bin/env python3
"""Regenerate benchmark plots from an existing bundle output directory."""

from __future__ import annotations

import argparse
import os
from pathlib import Path


BUNDLE_ROOT = Path(__file__).resolve().parent


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Regenerate plots without running benchmark methods."
    )
    parser.add_argument(
        "input_dir",
        type=Path,
        help="Directory containing benchmark_rows_pipeline.json or benchmark_rows.json.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Plot output directory. Default: <input_dir>/plots_regenerated.",
    )
    parser.add_argument(
        "--error-view",
        choices=("absolute", "signed"),
        default="absolute",
        help="Error representation used by plots. Default: absolute.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    mpl_config = BUNDLE_ROOT / ".matplotlib"
    mpl_config.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_config))

    from quantum_diag.run_benchmark_pipeline import regenerate_plots_for_folder

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
        output_dir = input_dir / "plots_regenerated"
    return regenerate_plots_for_folder(
        input_dir=input_dir,
        output_dir=output_dir,
        error_view=args.error_view,
    )


if __name__ == "__main__":
    raise SystemExit(main())
