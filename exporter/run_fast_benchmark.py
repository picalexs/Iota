#!/usr/bin/env python3
"""Run the bounded benchmark profile with bundle-local outputs."""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path


BUNDLE_ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_ROOT = BUNDLE_ROOT / "output" / "fast"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the fast quantum-diag benchmark profile."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Exact run directory. Default: output/fast/<UTC timestamp>.",
    )
    parser.add_argument(
        "--run-tag",
        default=None,
        help="Run directory name when --output-dir is not used.",
    )
    parser.add_argument(
        "--execution-mode",
        choices=("serial", "parallel"),
        default="serial",
        help="Schedule methods serially or in parallel. Default: serial.",
    )
    parser.add_argument(
        "--compute-threads",
        type=int,
        default=0,
        help="BLAS/OpenMP threads. Use 0 for automatic selection.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=1,
        help="Print worker progress every N completed runs.",
    )
    parser.add_argument(
        "--heartbeat-seconds",
        type=float,
        default=10.0,
        help="Scheduler heartbeat interval. Default: 10 seconds.",
    )
    parser.add_argument(
        "--worker-progress",
        action="store_true",
        help="Enable verbose worker-side progress logs.",
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

    # Keep Matplotlib configuration and every generated artifact inside this
    # bundle. This also avoids writing to a user's global config directory.
    mpl_config = BUNDLE_ROOT / ".matplotlib"
    mpl_config.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_config))

    from quantum_diag.run_benchmark_pipeline import run_pipeline

    if args.output_dir is not None:
        output_dir = args.output_dir.expanduser()
        if not output_dir.is_absolute():
            output_dir = BUNDLE_ROOT / output_dir
        output_dir = output_dir.resolve()
        output_root = output_dir.parent
        run_tag = output_dir.name
    else:
        output_root = DEFAULT_OUTPUT_ROOT
        run_tag = args.run_tag or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_dir = output_root / run_tag

    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Fast profile output: {output_dir}")
    return run_pipeline(
        profile_name="fast",
        output_root=output_root,
        run_tag=run_tag,
        progress_every=max(1, args.progress_every),
        heartbeat_seconds=max(0.1, args.heartbeat_seconds),
        worker_progress=args.worker_progress,
        error_view=args.error_view,
        execution_mode=args.execution_mode,
        resource_mode="max-safe",
        resource_cpu_fraction=1.0,
        resource_mem_fraction=1.0,
        resource_mem_per_unit_gib=1.0,
        dynamic_memory_guard=True,
        min_free_memory_gib=None,
        compute_threads=args.compute_threads,
    )


if __name__ == "__main__":
    raise SystemExit(main())
