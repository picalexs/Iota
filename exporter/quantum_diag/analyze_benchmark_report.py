"""Generate an interpretation report for benchmark rows."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any


def _load_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".json":
        with path.open() as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("JSON input must be a list of row objects")
        return [dict(row) for row in data]

    if path.suffix.lower() == ".csv":
        with path.open(newline="") as f:
            reader = csv.DictReader(f)
            return [dict(row) for row in reader]

    raise ValueError(f"Unsupported input format for {path}")


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    raw = str(value).strip()
    if raw == "" or raw.lower() in {"none", "nan"}:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"true", "1", "yes"}


def _summarize_by_method(rows: list[dict[str, Any]]) -> dict[str, dict[str, float | int]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        method = str(row.get("method", "UNKNOWN"))
        grouped[method].append(row)

    summary: dict[str, dict[str, float | int]] = {}
    for method, method_rows in grouped.items():
        errors = [_to_float(r.get("energy_error")) for r in method_rows]
        errors = [e for e in errors if e is not None]

        algo_times = [_to_float(r.get("wall_time_seconds")) for r in method_rows]
        algo_times = [t for t in algo_times if t is not None]

        e2e_times = [_to_float(r.get("end_to_end_wall_time_seconds")) for r in method_rows]
        e2e_times = [t for t in e2e_times if t is not None]

        converged_count = sum(1 for r in method_rows if _to_bool(r.get("converged")))

        summary[method] = {
            "runs": len(method_rows),
            "mean_error": mean(errors) if errors else float("nan"),
            "mean_algorithm_runtime": mean(algo_times) if algo_times else float("nan"),
            "mean_end_to_end_runtime": mean(e2e_times) if e2e_times else float("nan"),
            "converged_runs": converged_count,
        }

    return summary


def _build_markdown(rows: list[dict[str, Any]]) -> str:
    successful_rows = [row for row in rows if not row.get("error")]
    failed_rows = [row for row in rows if row.get("error")]
    method_summary = _summarize_by_method(successful_rows)

    lines: list[str] = []
    lines.append("# Quantum Diag Benchmark Interpretation")
    lines.append("")
    lines.append("## Run Overview")
    lines.append(f"- Total rows: {len(rows)}")
    lines.append(f"- Successful rows: {len(successful_rows)}")
    lines.append(f"- Failed rows: {len(failed_rows)}")

    if failed_rows:
        lines.append("- Failure reasons:")
        reason_counts: dict[str, int] = defaultdict(int)
        for row in failed_rows:
            reason = str(row.get("error", "unknown"))
            reason_counts[reason] += 1
        for reason, count in sorted(reason_counts.items(), key=lambda kv: kv[1], reverse=True):
            lines.append(f"  - {count}x {reason}")

    lines.append("")
    lines.append("## Method Summary")
    for method in sorted(method_summary.keys()):
        item = method_summary[method]
        lines.append(
            "- "
            f"{method}: runs={item['runs']}, "
            f"mean_error={item['mean_error']:.6f}, "
            f"mean_algorithm_runtime={item['mean_algorithm_runtime']:.4f}s, "
            f"mean_end_to_end_runtime={item['mean_end_to_end_runtime']:.4f}s, "
            f"converged={item['converged_runs']}/{item['runs']}"
        )

    lines.append("")
    lines.append("## Interpretation Notes")
    lines.append(
        "- SQD/SKQD correctness check: values should not collapse to the molecular core-energy baseline; "
        "if they do, the sampled subspace is degenerate or electron-sector filtering failed."
    )
    lines.append(
        "- Convergence comparison must use each row's `convergence_criterion`; methods use different stopping rules."
    )
    lines.append(
        "- Runtime comparison should use `wall_time_seconds` (algorithm-comparable) and "
        "`end_to_end_wall_time_seconds` (includes chemistry-prewarm share)."
    )
    lines.append(
        "- VQE non-convergence is often dominated by optimization budget constraints (for COBYLA, MAXFUN lower bounds)."
    )

    lines.append("")
    lines.append("## External References")
    lines.append("- SQD docs: https://qiskit.github.io/qiskit-addon-sqd/")
    lines.append(
        "- SQD chemistry tutorial: "
        "https://qiskit.github.io/qiskit-addon-sqd/tutorials/01_chemistry_hamiltonian.html"
    )
    lines.append(
        "- LiH constants (NIST): "
        "https://physics.nist.gov/PhysRefData/MolSpec/Diatomic/Html/Tables/LiH.html"
    )
    lines.append(
        "- NH3 bond reference (CCCBDB): "
        "https://cccbdb.nist.gov/listbondexp3x.asp?bi=8&descript=rNH&mi=61"
    )
    lines.append(
        "- H2O angle reference (CCCBDB): "
        "https://cccbdb.nist.gov/listangleexp3x.asp?bi=9&descript=aHOH&mi=63"
    )

    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build benchmark interpretation report")
    parser.add_argument(
        "--rows",
        type=str,
        default="output/benchmark_rows.json",
        help="Path to benchmark rows file (.json or .csv)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="output/benchmark_interpretation.md",
        help="Markdown output path",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows_path = Path(args.rows)
    output_path = Path(args.output)

    rows = _load_rows(rows_path)
    markdown = _build_markdown(rows)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown)
    print(f"Wrote benchmark interpretation report to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
