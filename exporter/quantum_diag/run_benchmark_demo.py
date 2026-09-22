"""CLI script for running benchmark matrix demo and generating artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Add parent directory to Python path for imports
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from quantum_diag.config import ExperimentSpec
from quantum_diag.benchmark_matrix import BenchmarkMatrixRunner
from quantum_diag.classical_baselines import ClassicalBaseline
from quantum_diag.test_fixtures import (
    get_h2_geometry,
    get_lih_geometry,
    get_h2o_geometry,
    get_beh2_geometry,
    get_nh3_geometry,
)
from quantum_diag.results_aggregation import (
    to_dataframe,
    summarize_by_method,
    summarize_by_molecule,
    best_method_per_molecule,
    export_csv,
    export_json,
)
from quantum_diag.plotting_utils import (
    plot_energy_error_boxplot,
    plot_runtime_bar,
    plot_convergence_rate,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: List of arguments (for testing). If None, uses sys.argv[1:].

    Returns:
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Run quantum diagonalization benchmark matrix demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with defaults (H2, VQE/KQD/SQD, seeds 42-43)
  python run_benchmark_demo.py

  # Run with custom methods and molecules
  python run_benchmark_demo.py --methods VQE,KQD,SQD --molecules H2,LiH --seeds 42,43,44

  # Run with 100 iterations and custom output directory
  python run_benchmark_demo.py --max-iterations 100 --output-dir ./results/

  # Manual stress run on NH3
  python run_benchmark_demo.py --methods VQE,SQD --molecules NH3 --seeds 11
        """,
    )

    parser.add_argument(
        "--profile",
        type=str,
        choices=["smoke", "full"],
        default="smoke",
        help="Benchmark profile preset (default: smoke)",
    )

    parser.add_argument(
        "--methods",
        type=str,
        default=None,
        help="Comma-separated list of methods (overrides profile)",
    )

    parser.add_argument(
        "--molecules",
        type=str,
        default=None,
        help="Comma-separated list of molecules (overrides profile)",
    )

    parser.add_argument(
        "--seeds",
        type=str,
        default=None,
        help="Comma-separated list of random seeds (overrides profile)",
    )

    parser.add_argument(
        "--ansatz-types",
        type=str,
        default=None,
        help="Comma-separated ansatz types (overrides profile)",
    )

    parser.add_argument(
        "--optimizers",
        type=str,
        default=None,
        help="Comma-separated optimizers (overrides profile)",
    )

    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Maximum iterations per run (overrides profile)",
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default="output",
        help="Output directory for results (default: output)",
    )

    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable live progress logs",
    )

    parser.add_argument(
        "--progress-every",
        type=int,
        default=1,
        help="Print progress every N completed runs (default: 1)",
    )

    # Parse arguments
    if argv is not None:
        args = parser.parse_args(argv)
    else:
        args = parser.parse_args()

    profile = build_profile_matrix_config(args.profile)

    def parse_csv(raw: str | None) -> list[str] | None:
        if raw is None:
            return None
        return [v.strip() for v in raw.split(",") if v.strip()]

    # Apply profile defaults first, then explicit overrides.
    methods_override = parse_csv(args.methods)
    molecules_override = parse_csv(args.molecules)
    seeds_override = parse_csv(args.seeds)
    ansatz_override = parse_csv(args.ansatz_types)
    optimizers_override = parse_csv(args.optimizers)

    args.methods = methods_override if methods_override is not None else profile["methods"]
    args.molecules = (
        molecules_override if molecules_override is not None else profile["molecules"]
    )
    args.seeds = [int(s) for s in (seeds_override if seeds_override is not None else profile["seeds"])]
    args.ansatz_types = (
        ansatz_override if ansatz_override is not None else profile["ansatz_types"]
    )
    args.optimizers = (
        optimizers_override if optimizers_override is not None else profile["optimizers"]
    )
    args.max_iterations = (
        args.max_iterations
        if args.max_iterations is not None
        else profile["max_iterations"]
    )
    args.progress = not args.no_progress

    return args


def build_profile_matrix_config(profile: str) -> dict[str, Any]:
    """Build benchmark matrix configuration for named profile.

    Returns:
        Dict with methods, molecules, seeds, ansatz types, and optimizers.
    """
    if profile == "full":
        return {
            "methods": ["VQE", "KQD", "QFD", "SQD", "SKQD", "ADAPT-VQE", "QSE"],
            "molecules": ["H2", "LiH", "H2O", "BeH2"],
            "seeds": [11, 17],
            "ansatz_types": ["RealAmplitudes"],
            "optimizers": ["COBYLA"],
            "max_iterations": 8,
        }

    # smoke default profile
    return {
        "methods": ["VQE", "KQD", "SQD"],
        "molecules": ["H2", "LiH"],
        "seeds": [11, 17],
        "ansatz_types": ["RealAmplitudes"],
        "optimizers": ["COBYLA"],
        "max_iterations": 8,
    }


def _build_reference_energy_maps(
    molecules: list[str],
    basis_set: str,
) -> tuple[dict[str, float], dict[str, str]]:
    """Build reference energy and provenance maps from classical baselines."""
    geometry_factories: dict[str, Any] = {
        "H2": get_h2_geometry,
        "LiH": get_lih_geometry,
        "H2O": get_h2o_geometry,
        "BeH2": get_beh2_geometry,
        "NH3": get_nh3_geometry,
    }
    fallback_map = {
        "H2": -1.1661,
        "LiH": -7.8824,
        "H2O": -75.0,
        "BeH2": -15.1,
    }

    baseline = ClassicalBaseline()
    reference_energy_map: dict[str, float] = {}
    reference_source_map: dict[str, str] = {}

    for molecule in molecules:
        if molecule not in geometry_factories:
            raise ValueError(
                f"Unknown molecule '{molecule}'. "
                f"Supported molecules: {list(geometry_factories.keys())}"
            )

        geom = geometry_factories[molecule]()
        try:
            if geom.active_space is not None:
                casci_result = baseline.compute_casci_energy(
                    geometry=geom,
                    basis=basis_set,
                    active_space=geom.active_space,
                )
                reference_energy_map[molecule] = float(casci_result["energy"])
                reference_source_map[molecule] = (
                    f"CASCI active_space={geom.active_space} ({basis_set})"
                )
            else:
                rhf_result = baseline.compute_rhf_energy(geometry=geom, basis=basis_set)
                reference_energy_map[molecule] = float(rhf_result["energy"])
                reference_source_map[molecule] = f"RHF ({basis_set})"
        except Exception as exc:
            if molecule not in fallback_map:
                raise
            reference_energy_map[molecule] = fallback_map[molecule]
            reference_source_map[molecule] = f"fallback proxy ({exc.__class__.__name__})"

    return reference_energy_map, reference_source_map


def run_demo(
    methods: list[str],
    molecules: list[str],
    seeds: list[int],
    ansatz_types: list[str],
    optimizers: list[str],
    max_iterations: int,
    output_dir: str = "output",
    progress: bool = True,
    progress_every: int = 1,
    basis_set: str = "sto-3g",
) -> list[dict[str, Any]]:
    """Run benchmark matrix demo and export results.

    Args:
        methods: List of method names.
        molecules: List of molecule names.
        seeds: List of random seeds.
        max_iterations: Maximum iterations for each run.
        output_dir: Directory to export results to.

    Returns:
        List of benchmark result rows.
    """
    # Ensure output directory exists
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    reference_energy_map, reference_source_map = _build_reference_energy_maps(
        molecules=molecules,
        basis_set=basis_set,
    )
    print("Validated reference energies used in this run:")
    for molecule in molecules:
        print(
            f"  {molecule:4s} = {reference_energy_map[molecule]: .8f} Ha  "
            f"[{reference_source_map[molecule]}]"
        )

    # Create base spec
    base_spec = ExperimentSpec(
        molecule_name=molecules[0],
        basis_set=basis_set,
        method="VQE",
        ansatz_type=ansatz_types[0],
        optimizer=optimizers[0],
        max_iterations=max_iterations,
        shots=1024,
        seed=seeds[0],
        backend_name="qasm_simulator",
    )

    # Create and run benchmark matrix
    runner = BenchmarkMatrixRunner(base_spec, reference_energy_map)
    rows = runner.run_matrix(
        methods=methods,
        molecules=molecules,
        seeds=seeds,
        ansatz_types=ansatz_types,
        optimizers=optimizers,
        max_iterations=max_iterations,
        progress=progress,
        progress_every=progress_every,
    )

    # Export raw rows to JSON
    json_path = output_path / "benchmark_rows.json"
    export_json(rows, str(json_path))
    print(f"✓ Exported {len(rows)} benchmark rows to {json_path}")

    algorithm_runtime_total = sum(
        float(row.get("wall_time_seconds") or 0.0)
        for row in rows
        if "error" not in row
    )
    end_to_end_runtime_total = sum(
        float(row.get("end_to_end_wall_time_seconds") or row.get("wall_time_seconds") or 0.0)
        for row in rows
        if "error" not in row
    )
    runtime_metadata = {
        "runtime_measurement_mode": "algorithm-primary-with-end-to-end-secondary",
        "algorithm_runtime_total_seconds": algorithm_runtime_total,
        "end_to_end_runtime_total_seconds": end_to_end_runtime_total,
    }
    runtime_meta_path = output_path / "runtime_metadata.json"
    with open(runtime_meta_path, "w") as f:
        json.dump(runtime_metadata, f, indent=2)
    print(f"✓ Exported runtime metadata to {runtime_meta_path}")

    # Convert to dataframe
    df = to_dataframe(rows)

    # Export raw rows to CSV
    csv_path = output_path / "benchmark_rows.csv"
    export_csv(df, str(csv_path))
    print(f"✓ Exported benchmark rows to {csv_path}")

    # Compute and export summaries
    summary_method = summarize_by_method(df)
    summary_method_path = output_path / "summary_by_method.csv"
    export_csv(summary_method, str(summary_method_path))
    print(f"✓ Exported method summary to {summary_method_path}")

    summary_molecule = summarize_by_molecule(df)
    summary_molecule_path = output_path / "summary_by_molecule.csv"
    export_csv(summary_molecule, str(summary_molecule_path))
    print(f"✓ Exported molecule summary to {summary_molecule_path}")

    # Generate plots (with error handling for edge cases)
    try:
        plot_energy_path = output_path / "plot_energy_error_boxplot.png"
        plot_energy_error_boxplot(rows, str(plot_energy_path))
        print(f"✓ Generated energy error boxplot: {plot_energy_path}")
    except Exception as e:
        print(f"⚠ Could not generate energy error boxplot: {e}")

    try:
        plot_runtime_path = output_path / "plot_runtime_bar.png"
        plot_runtime_bar(rows, str(plot_runtime_path))
        print(f"✓ Generated runtime bar chart: {plot_runtime_path}")
    except Exception as e:
        print(f"⚠ Could not generate runtime bar chart: {e}")

    try:
        plot_convergence_path = output_path / "plot_convergence_rate.png"
        plot_convergence_rate(rows, str(plot_convergence_path))
        print(f"✓ Generated convergence rate chart: {plot_convergence_path}")
    except Exception as e:
        print(f"⚠ Could not generate convergence rate chart: {e}")

    # Print summary to console
    print("\n" + "=" * 60)
    print("BENCHMARK SUMMARY")
    print("=" * 60)
    print(f"Total runs: {len(rows)}")
    successful_runs = sum(1 for row in rows if "error" not in row)
    print(f"Successful runs: {successful_runs}/{len(rows)}")
    warning_runs = sum(1 for row in rows if int(row.get("warnings_count", 0) or 0) > 0)
    maxfun_adjusted_runs = sum(1 for row in rows if row.get("cobyla_maxfun_adjusted"))
    print(f"Runs with warnings: {warning_runs}")
    print(f"Runs with COBYLA MAXFUN adjustment warnings: {maxfun_adjusted_runs}")
    print(f"Total algorithm runtime (comparable): {algorithm_runtime_total:.3f}s")
    print(f"Total end-to-end runtime (with prewarm share): {end_to_end_runtime_total:.3f}s")

    if successful_runs > 0:
        print("\nSummary by Method:")
        print("-" * 60)
        if hasattr(summary_method, "to_string"):
            print(summary_method.to_string(index=False))
        else:
            # Fallback for non-pandas
            for row in summary_method.rows:
                method = row.get('method', 'N/A')
                energy_err = row.get('mean_energy_error')
                energy_err_str = f"{energy_err:.4e}" if energy_err is not None else "N/A"
                convergence = row.get('convergence_rate')
                convergence_str = f"{convergence:.2%}" if convergence is not None else "N/A"
                print(
                    f"{method:<15} "
                    f"mean_energy_error={energy_err_str:<15} "
                    f"convergence_rate={convergence_str}"
                )

    print("\nAll results exported to:", output_path)
    print("=" * 60 + "\n")

    return rows


def main(argv: list[str] | None = None) -> int:
    """Main entry point for benchmark demo script.

    Args:
        argv: Command-line arguments (for testing).

    Returns:
        Exit code (0 for success, 1 for error).
    """
    try:
        args = parse_args(argv)

        # Validate max_iterations
        if args.max_iterations <= 0:
            print("Error: --max-iterations must be positive", file=sys.stderr)
            return 1

        # Run demo
        rows = run_demo(
            methods=args.methods,
            molecules=args.molecules,
            seeds=args.seeds,
            ansatz_types=args.ansatz_types,
            optimizers=args.optimizers,
            max_iterations=args.max_iterations,
            output_dir=args.output_dir,
            progress=args.progress,
            progress_every=args.progress_every,
        )

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
