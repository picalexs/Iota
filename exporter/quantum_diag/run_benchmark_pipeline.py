"""Terminal-first benchmark pipeline runner.

This script replaces the notebook flow end-to-end:
- smart parallel benchmark execution,
- diagnostics and summaries,
- artifact exports,
- interpretation report generation,
- visualization outputs.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import subprocess
import sys
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, cast

import matplotlib

# Force non-interactive backend for terminal execution.
matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Ensure package imports work when invoked as a script from repo root.
CURRENT_DIR = Path(__file__).parent
PROJECTS_DIR = CURRENT_DIR.parent
if str(PROJECTS_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECTS_DIR))

from quantum_diag.error_plot_contract import prepare_error_plot_data
from quantum_diag.notebook_parallel_runner import run_basis_matrix
from quantum_diag.plotting_utils import plot_convergence_rate, plot_energy_error_boxplot
from quantum_diag.results_aggregation import (
    best_method_per_molecule,
    export_csv,
    export_json,
    summarize_by_method,
    summarize_by_molecule,
)


ErrorView = Literal["absolute", "signed"]
ResourceMode = Literal["manual", "max-safe"]
ExecutionMode = Literal["serial", "parallel"]


@dataclass(frozen=True)
class PipelineProfile:
    """Configuration profile for benchmark pipeline execution."""

    name: str
    basis_aliases: list[str]
    methods: list[str]
    molecules: list[str]
    seeds: list[int]
    ansatz_types: list[str]
    optimizers: list[str]
    max_iterations: int


@dataclass(frozen=True)
class ResourceControls:
    """Concrete resource settings passed to the scheduler."""

    cpu_fraction: float
    mem_fraction: float
    mem_per_unit_gib: float
    dynamic_memory_guard: bool
    min_free_memory_gib: float


def _read_mem_available_gib() -> float | None:
    """Read MemAvailable from /proc/meminfo in GiB."""
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("MemAvailable:"):
                    mem_kib = float(line.split()[1])
                    return mem_kib / (1024.0 * 1024.0)
    except Exception:
        return None
    return None


def resolve_resource_controls(
    *,
    resource_mode: ResourceMode,
    resource_cpu_fraction: float,
    resource_mem_fraction: float,
    resource_mem_per_unit_gib: float,
    dynamic_memory_guard: bool,
    min_free_memory_gib: float | None,
) -> ResourceControls:
    """Resolve effective resource controls for scheduler execution."""
    if resource_mode == "max-safe":
        available_mem_gib = _read_mem_available_gib()
        auto_min_free = 2.5
        if isinstance(available_mem_gib, float):
            auto_min_free = max(2.5, 0.2 * available_mem_gib)

        return ResourceControls(
            cpu_fraction=1.0,
            mem_fraction=1.0,
            mem_per_unit_gib=max(1.75, float(resource_mem_per_unit_gib)),
            dynamic_memory_guard=True,
            min_free_memory_gib=float(min_free_memory_gib)
            if min_free_memory_gib is not None
            else auto_min_free,
        )

    return ResourceControls(
        cpu_fraction=float(resource_cpu_fraction),
        mem_fraction=float(resource_mem_fraction),
        mem_per_unit_gib=float(resource_mem_per_unit_gib),
        dynamic_memory_guard=bool(dynamic_memory_guard),
        min_free_memory_gib=float(min_free_memory_gib) if min_free_memory_gib is not None else 1.5,
    )


def resolve_compute_threads(*, execution_mode: ExecutionMode, requested_threads: int) -> int:
    """Resolve compute thread count for BLAS/OpenMP-backed workloads."""
    if requested_threads > 0:
        return requested_threads
    if execution_mode == "serial":
        return max(1, int(os.cpu_count() or 1))
    return 1


def _apply_compute_thread_env(thread_count: int) -> None:
    """Apply common thread env vars used by math backends."""
    value = str(max(1, int(thread_count)))
    for name in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "BLIS_NUM_THREADS",
        "RAYON_NUM_THREADS",
    ):
        os.environ[name] = value


def _threadpool_limits_context(thread_count: int):
    """Try to enforce threadpool limits at runtime when threadpoolctl is available."""
    try:
        threadpoolctl = importlib.import_module("threadpoolctl")
        threadpool_limits = getattr(threadpoolctl, "threadpool_limits")
        return threadpool_limits(limits=max(1, int(thread_count)))
    except Exception:
        return nullcontext()


def build_profile(name: str) -> PipelineProfile:
    """Build named execution profile."""
    if name == "full":
        return PipelineProfile(
            name="full",
            basis_aliases=["sto", "gto", "cgto"],
            methods=["VQE", "ADAPT-VQE", "SQD", "SKQD", "KQD", "QSE", "QFD"],
            molecules=["H2", "NH3"],
            seeds=[11, 12, 13, 14, 15],
            ansatz_types=["RealAmplitudes", "TwoLocal", "LUCJ"],
            optimizers=["COBYLA"],
            max_iterations=6,
        )

    if name == "fast":
        return PipelineProfile(
            name="fast",
            basis_aliases=["sto"],
            methods=["VQE", "KQD", "SQD"],
            molecules=["H2", "LiH"],
            seeds=[11, 17],
            ansatz_types=["RealAmplitudes"],
            optimizers=["COBYLA"],
            max_iterations=4,
        )

    # Safe remains the original bounded profile for compatibility.
    return PipelineProfile(
        name="safe",
        basis_aliases=["sto", "gto"],
        methods=["VQE", "ADAPT-VQE", "SQD"],
        molecules=["H2", "NH3"],
        seeds=[11, 12],
        ansatz_types=["RealAmplitudes", "LUCJ"],
        optimizers=["COBYLA"],
        max_iterations=4,
    )


def _runtime_col(df: pd.DataFrame) -> str | None:
    """Pick the best runtime column available for diagnostics and plotting."""
    if "algorithm_wall_time_seconds" in df.columns:
        return "algorithm_wall_time_seconds"
    if "wall_time_seconds" in df.columns:
        return "wall_time_seconds"
    return None


def _filter_success_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Keep successful rows only."""
    if "error" not in df.columns:
        return df.copy()
    return df[df["error"].isna() | (df["error"] == "")].copy()


def _coerce_converged(series: pd.Series) -> pd.Series:
    """Normalize converged column to boolean values."""
    return series.map(
        lambda x: x if isinstance(x, bool) else str(x).strip().lower() in {"true", "1", "yes"}
    )


def _export_diagnostics(
    *,
    df: pd.DataFrame,
    valid_df: pd.DataFrame,
    output_dir: Path,
) -> dict[str, Any]:
    """Compute and export diagnostics artifacts similar to notebook analysis."""
    summary_method = summarize_by_method(df)
    summary_molecule = summarize_by_molecule(df)
    best_per_molecule = best_method_per_molecule(df)

    export_csv(summary_method, str(output_dir / "summary_by_method_pipeline.csv"))
    export_csv(summary_molecule, str(output_dir / "summary_by_molecule_pipeline.csv"))
    export_csv(best_per_molecule, str(output_dir / "best_method_per_molecule_pipeline.csv"))

    runtime_col = _runtime_col(valid_df)
    diagnostics: dict[str, Any] = {
        "total_rows": int(len(df)),
        "successful_rows": int(len(valid_df)),
        "runtime_column_for_plots": runtime_col,
    }

    if not valid_df.empty and "basis_alias" in valid_df.columns:
        basis_summary = (
            valid_df.groupby("basis_alias", dropna=False)
            .agg(
                runs=("method", "count"),
                mean_energy_error=("energy_error", "mean"),
                mean_algorithm_wall_time_seconds=("algorithm_wall_time_seconds", "mean"),
            )
            .reset_index()
            .sort_values("basis_alias")
        )
        export_csv(basis_summary, str(output_dir / "summary_by_basis_alias_pipeline.csv"))

    if not valid_df.empty and {"basis_alias", "ansatz_type"}.issubset(valid_df.columns):
        ansatz_summary = (
            valid_df.groupby(["basis_alias", "ansatz_type"], dropna=False)
            .agg(
                runs=("method", "count"),
                mean_energy_error=("energy_error", "mean"),
                mean_algorithm_wall_time_seconds=("algorithm_wall_time_seconds", "mean"),
                convergence_rate=("converged", "mean"),
            )
            .reset_index()
            .sort_values(["basis_alias", "ansatz_type"])
        )
        export_csv(ansatz_summary, str(output_dir / "summary_by_basis_and_ansatz_pipeline.csv"))

    if not valid_df.empty and runtime_col is not None:
        runtime_group_cols = ["method"]
        if {"basis_alias", "ansatz_type"}.issubset(valid_df.columns):
            runtime_group_cols = ["basis_alias", "ansatz_type", "method"]

        runtime_cols = [
            col
            for col in ["algorithm_wall_time_seconds", "end_to_end_wall_time_seconds"]
            if col in valid_df.columns
        ]
        if not runtime_cols and runtime_col in valid_df.columns:
            runtime_cols = [runtime_col]

        runtime_summary = (
            valid_df.groupby(runtime_group_cols, dropna=False)[runtime_cols]
            .mean()
            .reset_index()
            .sort_values(runtime_group_cols)
        )
        export_csv(runtime_summary, str(output_dir / "summary_runtime_pipeline.csv"))

    if not valid_df.empty and {"method", "shots_used"}.issubset(valid_df.columns):
        shots_group_cols = ["method"]
        if {"basis_alias", "ansatz_type"}.issubset(valid_df.columns):
            shots_group_cols = ["basis_alias", "ansatz_type", "method"]

        shots_summary = (
            valid_df.groupby(shots_group_cols, dropna=False)["shots_used"]
            .agg(mean_shots="mean", min_shots="min", max_shots="max")
            .reset_index()
            .sort_values(shots_group_cols)
        )
        export_csv(shots_summary, str(output_dir / "summary_shots_pipeline.csv"))

    if not valid_df.empty and {"method", "energy_error"}.issubset(valid_df.columns):
        error_group_cols = ["method"]
        if {"basis_alias", "ansatz_type"}.issubset(valid_df.columns):
            error_group_cols = ["basis_alias", "ansatz_type", "method"]

        method_error = (
            valid_df.groupby(error_group_cols, dropna=False)["energy_error"]
            .mean()
            .reset_index()
            .sort_values("energy_error")
        )
        export_csv(method_error, str(output_dir / "summary_mean_error_pipeline.csv"))

        accuracy_thresholds = [1e-1, 5e-1, 1.0]
        tmp = valid_df.copy()
        for tol in accuracy_thresholds:
            tmp[f"acc_le_{tol:g}_ha"] = tmp["energy_error"].astype(float) <= tol

        acc_cols = [f"acc_le_{tol:g}_ha" for tol in accuracy_thresholds]
        accuracy_summary = (
            tmp.groupby("method", dropna=False)[acc_cols + ["energy_error"]]
            .agg({
                "energy_error": "mean",
                **{col: "mean" for col in acc_cols},
            })
            .reset_index()
            .rename(columns={"energy_error": "mean_energy_error"})
            .sort_values("mean_energy_error")
        )
        export_csv(accuracy_summary, str(output_dir / "summary_accuracy_thresholds_pipeline.csv"))

    if not valid_df.empty and {"method", "converged", "convergence_criterion", "energy_error"}.issubset(
        valid_df.columns
    ):
        vqe_rows = valid_df[valid_df["method"] == "VQE"].copy()
        if not vqe_rows.empty:
            vqe_rows["converged_bool"] = _coerce_converged(vqe_rows["converged"])
            diagnostics["vqe_strict_convergence_rate"] = float(vqe_rows["converged_bool"].mean())
            diagnostics["vqe_accuracy_rate_le_0_5_ha"] = float(
                (vqe_rows["energy_error"].astype(float) <= 0.5).mean()
            )
            diagnostics["vqe_accuracy_rate_le_1_0_ha"] = float(
                (vqe_rows["energy_error"].astype(float) <= 1.0).mean()
            )

    if {"method", "molecule", "converged"}.issubset(df.columns):
        converged_mask = _coerce_converged(df["converged"])
        non_converged = df[~converged_mask].copy()
        if not non_converged.empty:
            export_csv(non_converged, str(output_dir / "non_converged_rows_pipeline.csv"))

    (output_dir / "diagnostics_metadata_pipeline.json").write_text(
        json.dumps(diagnostics, indent=2),
        encoding="utf-8",
    )

    return diagnostics


def _plot_runtime_distribution(rows: list[dict[str, Any]], output_path: Path) -> None:
    """Generate runtime distribution plot similar to notebook cell."""
    runtime_df = pd.DataFrame(rows)
    runtime_df = _filter_success_rows(runtime_df)

    runtime_cols = [
        col
        for col in ["algorithm_wall_time_seconds", "end_to_end_wall_time_seconds"]
        if col in runtime_df.columns
    ]
    if not runtime_cols and "wall_time_seconds" in runtime_df.columns:
        runtime_cols = ["wall_time_seconds"]

    fig, ax = plt.subplots(figsize=(11, 6))
    if runtime_cols and not runtime_df.empty:
        runtime_long = runtime_df.melt(
            id_vars=["method"],
            value_vars=runtime_cols,
            var_name="runtime_kind",
            value_name="seconds",
        ).dropna()

        if not runtime_long.empty:
            grouped = runtime_long.groupby(["runtime_kind", "method"], dropna=False)["seconds"].apply(list)
            labels: list[str] = []
            data: list[list[float]] = []

            for runtime_kind in sorted(runtime_long["runtime_kind"].unique()):
                for method in sorted(runtime_long["method"].unique()):
                    key = (runtime_kind, method)
                    if key in grouped:
                        labels.append(f"{method}\n{runtime_kind}")
                        data.append(grouped[key])

            if data:
                ax.boxplot(data, tick_labels=labels)
                ax.set_yscale("log")
                ax.set_xlabel("Method / Runtime Kind")
                ax.set_ylabel("Wall Time (seconds, log scale)")
                ax.set_title("Runtime Distribution: Algorithm vs End-to-End")
                ax.grid(True, alpha=0.3, axis="y")
                plt.setp(ax.get_xticklabels(), rotation=35, ha="right")
            else:
                ax.text(0.5, 0.5, "No runtime data available", ha="center", va="center")
                ax.set_axis_off()
        else:
            ax.text(0.5, 0.5, "No runtime data available", ha="center", va="center")
            ax.set_axis_off()
    else:
        ax.text(0.5, 0.5, "No runtime data available", ha="center", va="center")
        ax.set_axis_off()

    fig.tight_layout()
    fig.savefig(output_path, dpi=110, bbox_inches="tight")
    plt.close(fig)


def _plot_error_vs_runtime(
    rows: list[dict[str, Any]],
    output_path: Path,
) -> float | None:
    """Generate error-vs-runtime scatter and return Spearman correlation if available."""
    runtime_df = pd.DataFrame(rows)
    runtime_df = _filter_success_rows(runtime_df)

    runtime_col = _runtime_col(runtime_df)
    fig, ax = plt.subplots(figsize=(11, 6))
    spearman_corr: float | None = None

    if runtime_col is not None and "energy_error" in runtime_df.columns:
        cols_needed = ["method", "basis_alias", runtime_col, "energy_error"]
        cols_needed = [col for col in cols_needed if col in runtime_df.columns]
        scatter_df = runtime_df[cols_needed].dropna().copy()

        if not scatter_df.empty:
            scatter_df["runtime_for_plot"] = scatter_df[runtime_col].astype(float).clip(lower=1e-4)
            scatter_df["energy_for_plot"] = scatter_df["energy_error"].astype(float).abs().clip(lower=1e-12)

            basis_markers = {"sto": "o", "gto": "s", "cgto": "^"}
            methods = sorted(str(method) for method in scatter_df["method"].dropna().unique())
            cmap = plt.get_cmap("tab10")
            method_colors = {
                method: cmap(idx % cmap.N)
                for idx, method in enumerate(methods)
            }

            for method_name, method_df in scatter_df.groupby("method", dropna=False):
                method_label = str(method_name)
                color = method_colors.get(method_label)

                if "basis_alias" in method_df.columns:
                    label_used = False
                    for basis_alias, basis_df in method_df.groupby("basis_alias", dropna=False):
                        marker = basis_markers.get(str(basis_alias), "o")
                        ax.scatter(
                            basis_df["runtime_for_plot"],
                            basis_df["energy_for_plot"],
                            s=34,
                            alpha=0.72,
                            marker=marker,
                            color=color,
                            label=method_label if not label_used else "_nolegend_",
                        )
                        label_used = True
                else:
                    ax.scatter(
                        method_df["runtime_for_plot"],
                        method_df["energy_for_plot"],
                        s=34,
                        alpha=0.72,
                        marker="o",
                        color=color,
                        label=method_label,
                    )

            ax.set_xscale("log")
            ax.set_yscale("log")
            ax.set_xlabel(f"{runtime_col} (seconds, log scale)")
            ax.set_ylabel("Absolute energy error (Ha, log scale)")
            ax.set_title("Accuracy vs Runtime Tradeoff")
            ax.grid(True, alpha=0.3, which="both")
            ax.legend(loc="best", fontsize=8)

            corr = scatter_df[[runtime_col, "energy_error"]].corr(method="spearman")
            if corr.shape == (2, 2):
                raw = corr.iloc[0, 1]
                if isinstance(raw, (int, float, np.floating)):
                    spearman_corr = float(raw)
                elif isinstance(raw, complex):
                    spearman_corr = float(raw.real)

    if spearman_corr is None:
        ax.text(0.5, 0.5, "No runtime/error data available", ha="center", va="center")
        ax.set_axis_off()

    fig.tight_layout()
    fig.savefig(output_path, dpi=110, bbox_inches="tight")
    plt.close(fig)
    return spearman_corr


def _generate_plots(
    *,
    rows: list[dict[str, Any]],
    output_dir: Path,
    error_view: ErrorView,
) -> dict[str, Any]:
    """Generate plots and return plot metadata."""
    plot_metadata: dict[str, Any] = {"error_view": error_view}

    plot_df = prepare_error_plot_data(rows, error_view=error_view)

    fig1 = plot_energy_error_boxplot(plot_df)
    fig1_path = output_dir / "plot_energy_error_boxplot_pipeline.png"
    fig1.savefig(fig1_path, dpi=110, bbox_inches="tight")
    plt.close(fig1)

    _plot_runtime_distribution(rows, output_dir / "plot_runtime_distribution_pipeline.png")

    fig3 = plot_convergence_rate(plot_df)
    fig3_path = output_dir / "plot_convergence_rate_pipeline.png"
    fig3.savefig(fig3_path, dpi=110, bbox_inches="tight")
    plt.close(fig3)

    spearman_corr = _plot_error_vs_runtime(rows, output_dir / "plot_error_vs_runtime_pipeline.png")
    plot_metadata["spearman_runtime_error_correlation"] = spearman_corr

    return plot_metadata


def _load_rows_from_folder(input_dir: Path) -> list[dict[str, Any]]:
    """Load benchmark rows from an existing output folder."""
    json_candidates = [
        "benchmark_rows_pipeline.json",
        "benchmark_rows_parallel.json",
        "benchmark_rows_basis.json",
    ]
    for filename in json_candidates:
        candidate = input_dir / filename
        if candidate.exists():
            payload = json.loads(candidate.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                return payload
            raise ValueError(f"Rows file is not a list of records: {candidate}")

    csv_candidates = [
        "benchmark_rows_pipeline.csv",
        "benchmark_rows_parallel.csv",
        "benchmark_rows_basis.csv",
    ]
    for filename in csv_candidates:
        candidate = input_dir / filename
        if candidate.exists():
            csv_rows = pd.read_csv(candidate).to_dict("records")
            return [{str(key): value for key, value in row.items()} for row in csv_rows]

    raise FileNotFoundError(
        "No benchmark rows artifact found. Expected one of: "
        "benchmark_rows_pipeline.(json|csv), "
        "benchmark_rows_parallel.(json|csv), "
        "benchmark_rows_basis.(json|csv)."
    )


def regenerate_plots_for_folder(
    *,
    input_dir: Path,
    output_dir: Path,
    error_view: ErrorView,
) -> int:
    """Regenerate plots from an existing benchmark output folder."""
    if not input_dir.exists() or not input_dir.is_dir():
        raise FileNotFoundError(f"Input folder does not exist or is not a directory: {input_dir}")

    rows = _load_rows_from_folder(input_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    plot_metadata = _generate_plots(rows=rows, output_dir=output_dir, error_view=error_view)
    (output_dir / "plot_metadata_regenerated.json").write_text(
        json.dumps(plot_metadata, indent=2),
        encoding="utf-8",
    )

    print("\nPlots regenerated successfully.")
    print(f"Input folder: {input_dir}")
    print(f"Output folder: {output_dir}")
    print(
        "Generated files: "
        "plot_energy_error_boxplot_pipeline.png, "
        "plot_runtime_distribution_pipeline.png, "
        "plot_convergence_rate_pipeline.png, "
        "plot_error_vs_runtime_pipeline.png"
    )

    return 0


def run_pipeline(
    *,
    profile_name: str,
    output_root: Path,
    run_tag: str | None,
    progress_every: int,
    heartbeat_seconds: float,
    worker_progress: bool,
    error_view: ErrorView,
    execution_mode: ExecutionMode,
    resource_mode: ResourceMode,
    resource_cpu_fraction: float,
    resource_mem_fraction: float,
    resource_mem_per_unit_gib: float,
    dynamic_memory_guard: bool,
    min_free_memory_gib: float | None,
    compute_threads: int,
) -> int:
    """Execute the full pipeline and return process exit code."""
    basis_alias_to_pyscf = {
        "sto": "sto-3g",
        "gto": "6-31g",
        "cgto": "cc-pvdz",
    }

    profile = build_profile(profile_name)
    resources = resolve_resource_controls(
        resource_mode=resource_mode,
        resource_cpu_fraction=resource_cpu_fraction,
        resource_mem_fraction=resource_mem_fraction,
        resource_mem_per_unit_gib=resource_mem_per_unit_gib,
        dynamic_memory_guard=dynamic_memory_guard,
        min_free_memory_gib=min_free_memory_gib,
    )
    effective_compute_threads = resolve_compute_threads(
        execution_mode=execution_mode,
        requested_threads=max(0, int(compute_threads)),
    )
    _apply_compute_thread_env(effective_compute_threads)

    output_root.mkdir(parents=True, exist_ok=True)
    if run_tag is None:
        run_tag = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_output_dir = output_root / run_tag
    run_output_dir.mkdir(parents=True, exist_ok=True)

    print(
        f"Pipeline profile={profile.name} | basis_aliases={profile.basis_aliases} | "
        f"methods={profile.methods} | molecules={profile.molecules} | seeds={profile.seeds} | "
        f"ansatz_types={profile.ansatz_types} | max_iterations={profile.max_iterations}"
    )
    print(
        "Scheduler resource target: "
        f"execution_mode={execution_mode} "
        f"mode={resource_mode} "
        f"cpu_fraction={resources.cpu_fraction:.2f} "
        f"mem_fraction={resources.mem_fraction:.2f} "
        f"mem_per_unit_gib={resources.mem_per_unit_gib:.2f} "
        f"dynamic_mem_guard={'on' if resources.dynamic_memory_guard else 'off'} "
        f"min_free_mem_gib={resources.min_free_memory_gib:.2f} "
        f"compute_threads={effective_compute_threads}"
    )
    print(f"Output directory: {run_output_dir}")

    method_resource_cost = {
        "SQD": 1,
        "VQE": 2,
        "ADAPT-VQE": 2,
        "SKQD": 3,
        "KQD": 3,
        "QFD": 4,
        "QSE": 4,
    }

    with _threadpool_limits_context(effective_compute_threads):
        rows, _, scheduler_metadata = run_basis_matrix(
            run_output_dir=run_output_dir,
            basis_alias_to_pyscf=basis_alias_to_pyscf,
            basis_aliases=profile.basis_aliases,
            methods=profile.methods,
            molecules=profile.molecules,
            seeds=profile.seeds,
            ansatz_types=profile.ansatz_types,
            optimizers=profile.optimizers,
            max_iterations=profile.max_iterations,
            method_resource_cost=method_resource_cost,
            progress_every=max(1, progress_every),
            heartbeat_seconds=max(1.0, heartbeat_seconds),
            worker_progress=worker_progress,
            resource_cpu_fraction=resources.cpu_fraction,
            resource_mem_fraction=resources.mem_fraction,
            resource_mem_per_unit_gib=resources.mem_per_unit_gib,
            dynamic_memory_guard=resources.dynamic_memory_guard,
            min_free_memory_gib=resources.min_free_memory_gib,
            force_serial=(execution_mode == "serial"),
        )

    df = pd.DataFrame(rows)
    valid_df = _filter_success_rows(df)

    export_json(rows, str(run_output_dir / "benchmark_rows_pipeline.json"))
    export_csv(df, str(run_output_dir / "benchmark_rows_pipeline.csv"))

    diagnostics = _export_diagnostics(df=df, valid_df=valid_df, output_dir=run_output_dir)
    plot_metadata = _generate_plots(rows=rows, output_dir=run_output_dir, error_view=error_view)

    runtime_metadata = {
        "runtime_measurement_mode": "algorithm-primary-with-end-to-end-secondary",
        "algorithm_runtime_total_seconds": float(df.get("algorithm_wall_time_seconds", pd.Series(dtype=float)).fillna(0).sum())
        if "algorithm_wall_time_seconds" in df.columns
        else float(df.get("wall_time_seconds", pd.Series(dtype=float)).fillna(0).sum()),
        "end_to_end_runtime_total_seconds": float(df.get("end_to_end_wall_time_seconds", pd.Series(dtype=float)).fillna(0).sum())
        if "end_to_end_wall_time_seconds" in df.columns
        else float(df.get("wall_time_seconds", pd.Series(dtype=float)).fillna(0).sum()),
        "scheduler_metadata": scheduler_metadata,
        "diagnostics": diagnostics,
        "plot_metadata": plot_metadata,
    }
    (run_output_dir / "runtime_metadata_pipeline.json").write_text(
        json.dumps(runtime_metadata, indent=2),
        encoding="utf-8",
    )

    analysis_script = CURRENT_DIR / "analyze_benchmark_report.py"
    report_path = run_output_dir / "benchmark_interpretation_pipeline.md"
    try:
        subprocess.run(
            [
                sys.executable,
                str(analysis_script),
                "--rows",
                str(run_output_dir / "benchmark_rows_pipeline.json"),
                "--output",
                str(report_path),
            ],
            check=True,
        )
        print(f"Interpretation report: {report_path}")
    except subprocess.CalledProcessError as exc:
        print(f"Warning: interpretation report generation failed ({exc}).")

    print("\nPipeline completed successfully.")
    print(f"Rows total: {len(df)}")
    print(f"Rows successful: {len(valid_df)}")
    print(f"Artifacts directory: {run_output_dir}")

    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Run full benchmark pipeline outside Jupyter notebook.",
    )
    parser.add_argument(
        "--profile",
        type=str,
        default="full",
        choices=["fast", "safe", "full"],
        help="Execution profile (default: full; fast and safe are bounded profiles).",
    )
    parser.add_argument(
        "--output-root",
        type=str,
        default=str(CURRENT_DIR / "output" / "pipeline"),
        help="Root output directory for run folders.",
    )
    parser.add_argument(
        "--run-tag",
        type=str,
        default=None,
        help="Optional explicit run tag (default: UTC timestamp).",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=2,
        help="Worker progress granularity when worker logs are enabled.",
    )
    parser.add_argument(
        "--heartbeat-seconds",
        type=float,
        default=10.0,
        help="Heartbeat interval for scheduler status output (default: 10s).",
    )
    parser.add_argument(
        "--resource-mode",
        type=str,
        default="max-safe",
        choices=["manual", "max-safe"],
        help="Resource policy (default: max-safe).",
    )
    parser.add_argument(
        "--execution-mode",
        type=str,
        default="serial",
        choices=["serial", "parallel"],
        help="Method scheduling mode (default: serial).",
    )
    parser.add_argument(
        "--resource-cpu-fraction",
        type=float,
        default=1.0,
        help="Fraction of host CPUs to use for scheduler budget (default: 1.0).",
    )
    parser.add_argument(
        "--resource-mem-fraction",
        type=float,
        default=1.0,
        help="Fraction of available RAM to use for scheduler budget (default: 1.0).",
    )
    parser.add_argument(
        "--resource-mem-per-unit-gib",
        type=float,
        default=1.0,
        help="Estimated RAM per scheduler budget unit in GiB (default: 1.0).",
    )
    parser.add_argument(
        "--compute-threads",
        type=int,
        default=0,
        help=(
            "Compute threads for BLAS/OpenMP backends. "
            "0 = auto (all CPUs in serial mode, 1 in parallel mode)."
        ),
    )
    parser.add_argument(
        "--disable-dynamic-memory-guard",
        action="store_true",
        help="Disable live memory headroom guard before method submission.",
    )
    parser.add_argument(
        "--min-free-memory-gib",
        type=float,
        default=None,
        help="Minimum free RAM headroom (GiB) to keep while submitting new work.",
    )
    parser.add_argument(
        "--worker-progress",
        action="store_true",
        help="Enable verbose worker-side per-run logs.",
    )
    parser.add_argument(
        "--error-view",
        type=str,
        default="absolute",
        choices=["absolute", "signed"],
        help="Error view used for plotting contract.",
    )
    parser.add_argument(
        "--plots-only",
        action="store_true",
        help="Skip benchmark execution and regenerate plots from an existing output folder.",
    )
    parser.add_argument(
        "--input-folder",
        type=str,
        default=None,
        help="Folder containing existing benchmark rows artifacts for --plots-only mode.",
    )
    parser.add_argument(
        "--plots-same-folder",
        action="store_true",
        help="In --plots-only mode, write regenerated plot images into --input-folder.",
    )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    args = parse_args(argv)

    if args.plots_only:
        if args.input_folder is None:
            raise SystemExit("--plots-only requires --input-folder <path>.")

        input_dir = Path(args.input_folder)
        output_dir = input_dir if args.plots_same_folder else input_dir / "plots_regenerated"
        return regenerate_plots_for_folder(
            input_dir=input_dir,
            output_dir=output_dir,
            error_view=cast(ErrorView, args.error_view),
        )

    return run_pipeline(
        profile_name=args.profile,
        output_root=Path(args.output_root),
        run_tag=args.run_tag,
        progress_every=args.progress_every,
        heartbeat_seconds=args.heartbeat_seconds,
        worker_progress=args.worker_progress,
        error_view=cast(ErrorView, args.error_view),
        execution_mode=cast(ExecutionMode, args.execution_mode),
        resource_mode=cast(ResourceMode, args.resource_mode),
        resource_cpu_fraction=args.resource_cpu_fraction,
        resource_mem_fraction=args.resource_mem_fraction,
        resource_mem_per_unit_gib=args.resource_mem_per_unit_gib,
        dynamic_memory_guard=not args.disable_dynamic_memory_guard,
        min_free_memory_gib=args.min_free_memory_gib,
        compute_threads=args.compute_threads,
    )


if __name__ == "__main__":
    raise SystemExit(main())
