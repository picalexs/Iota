"""Compact, layout-safe plots for normalized QSS benchmark rows."""

from __future__ import annotations

import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


PLOT_NAMES = (
    "error_by_algorithm",
    "convergence_by_algorithm",
    "runtime_by_algorithm",
    "error_vs_runtime",
)


def _finite(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _status_success(row: Mapping[str, Any]) -> bool:
    explicit = row.get("benchmark_eligible")
    if isinstance(explicit, bool):
        return explicit
    return (
        str(row.get("status") or "").lower() == "completed"
        and row.get("reported_energy_is_valid") is not False
        and row.get("projected_solve_is_diagnostic") is not True
        and row.get("scientific_converged") is not False
        and row.get("converged") is not False
    )


def _group_label(row: Mapping[str, Any]) -> str:
    algorithm = str(row.get("algorithm") or "UNKNOWN")
    path = str(row.get("actual_path_class") or "").strip()
    return f"{algorithm} · {path}" if path else algorithm


def _error_value(row: Mapping[str, Any], error_view: str) -> float | None:
    key = "signed_error" if error_view == "signed" else "absolute_error"
    explicit = _finite(row.get(key))
    if explicit is not None:
        return explicit
    final_energy = _finite(row.get("final_energy"))
    reference_energy = _finite(row.get("reference_energy"))
    if final_energy is None or reference_energy is None:
        return None
    error = final_energy - reference_energy
    return error if error_view == "signed" else abs(error)


def _observed(row: Mapping[str, Any], error_view: str = "absolute") -> bool:
    """Whether a completed row has a finite terminal estimate for plotting."""

    return (
        str(row.get("status") or "").lower() == "completed"
        and row.get("reported_energy_is_valid") is not False
        and _error_value(row, error_view) is not None
    )


def _observation_bucket(row: Mapping[str, Any]) -> str:
    if _status_success(row):
        return "validated"
    if row.get("projected_solve_is_diagnostic") is True:
        return "diagnostic"
    return "unvalidated"


def _group_values(
    rows: Iterable[Mapping[str, Any]],
    value_fn,
) -> dict[str, list[float]]:
    groups: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        algorithm = _group_label(row)
        value = value_fn(row)
        if value is not None:
            groups[algorithm].append(value)
    return dict(sorted(groups.items()))


def _safe_label(value: str) -> str:
    return value.replace("_", "\n")


def _boxplot(ax, groups: list[list[float]], labels: list[str]) -> None:
    """Draw a boxplot without relying on version-specific label arguments."""

    ax.boxplot(groups)
    ax.set_xticks(range(1, len(labels) + 1), [_safe_label(label) for label in labels])


def _save(fig, output_dir: Path, name: str, output_format: str) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    formats = ("png", "svg") if output_format == "both" else (output_format,)
    result: list[str] = []
    for extension in formats:
        path = output_dir / f"{name}.{extension}"
        fig.savefig(path, dpi=140, bbox_inches="tight", pad_inches=0.15)
        result.append(path.name)
    plt.close(fig)
    return result


def _empty_figure(message: str, *, width: float = 8.0):
    fig, ax = plt.subplots(figsize=(width, 4.8), constrained_layout=True)
    ax.text(0.5, 0.5, message, ha="center", va="center", transform=ax.transAxes)
    ax.set_axis_off()
    return fig


def _error_plot(rows: list[Mapping[str, Any]], error_view: str):
    observed_rows = [row for row in rows if _observed(row, error_view)]
    groups = _group_values(observed_rows, lambda row: _error_value(row, error_view))
    plotted_count = sum(len(values) for values in groups.values())
    excluded_count = len(rows) - plotted_count
    if not groups:
        return _empty_figure("No finite terminal rows with energy-error data."), 0, len(rows)
    labels = list(groups)
    fig, ax = plt.subplots(
        figsize=(max(7.5, 1.25 * len(labels) + 2.5), 5.2),
        constrained_layout=True,
    )
    _boxplot(ax, [groups[label] for label in labels], labels)
    validated_medians = []
    for label in labels:
        values = [
            value
            for row in observed_rows
            if _group_label(row) == label
            and _status_success(row)
            and (value := _error_value(row, error_view)) is not None
        ]
        validated_medians.append(sum(values) / len(values) if values else math.nan)
    ax.scatter(
        range(1, len(labels) + 1),
        validated_medians,
        color="#111111",
        marker="o",
        s=28,
        zorder=3,
        label="Validated median",
    )
    ax.set_xlabel("Algorithm · execution path")
    ax.set_ylabel(f"{'Signed' if error_view == 'signed' else 'Absolute'} energy error (Ha)")
    ax.set_title("Terminal energy error by algorithm")
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend(frameon=False)
    return fig, plotted_count, excluded_count


def _convergence_plot(rows: list[Mapping[str, Any]]):
    groups: dict[str, list[bool]] = defaultdict(list)
    for row in rows:
        if not _status_success(row) and str(row.get("status") or "").lower() != "completed":
            continue
        scientific = row.get("scientific_converged")
        converged = scientific if isinstance(scientific, bool) else row.get("converged")
        if not isinstance(converged, bool):
            continue
        groups[_group_label(row)].append(converged)
    groups = dict(sorted(groups.items()))
    if not groups:
        return _empty_figure("No completed rows with convergence data."), 0, 0
    labels = list(groups)
    rates = [100.0 * sum(values) / len(values) for values in groups.values()]
    fig, ax = plt.subplots(
        figsize=(max(7.5, 1.25 * len(labels) + 2.5), 5.2),
        constrained_layout=True,
    )
    ax.bar([_safe_label(label) for label in labels], rates, color="#2a9d8f")
    ax.set_ylim(0, 100)
    ax.set_xlabel("Algorithm · execution path")
    ax.set_ylabel("Convergence rate (%)")
    ax.set_title("Convergence by algorithm")
    ax.grid(True, axis="y", alpha=0.3)
    return fig, sum(len(values) for values in groups.values()), 0


def _runtime_plot(rows: list[Mapping[str, Any]]):
    observed_rows = [
        row
        for row in rows
        if _observed(row) and (_finite(row.get("runtime_seconds")) or 0) > 0
    ]
    groups = _group_values(
        observed_rows,
        lambda row: _finite(row.get("runtime_seconds")),
    )
    plotted_count = sum(len(values) for values in groups.values())
    excluded_count = len(rows) - plotted_count
    if not groups:
        return _empty_figure("No finite terminal rows with runtime data."), 0, len(rows)
    labels = list(groups)
    fig, ax = plt.subplots(
        figsize=(max(7.5, 1.25 * len(labels) + 2.5), 5.2),
        constrained_layout=True,
    )
    _boxplot(ax, [groups[label] for label in labels], labels)
    validated_medians = []
    for label in labels:
        values = [
            float(row["runtime_seconds"])
            for row in observed_rows
            if _group_label(row) == label
            and _status_success(row)
            and _finite(row.get("runtime_seconds")) is not None
        ]
        validated_medians.append(sum(values) / len(values) if values else math.nan)
    ax.scatter(
        range(1, len(labels) + 1),
        validated_medians,
        color="#111111",
        marker="o",
        s=28,
        zorder=3,
        label="Validated median",
    )
    positive = all(value > 0 for values in groups.values() for value in values)
    if positive:
        ax.set_yscale("log")
        ylabel = "Runtime (seconds, log scale)"
    else:
        ylabel = "Runtime (seconds)"
    ax.set_xlabel("Algorithm · execution path")
    ax.set_ylabel(ylabel)
    ax.set_title("Terminal runtime by algorithm")
    ax.grid(True, axis="y", alpha=0.3, which="both")
    ax.legend(frameon=False)
    return fig, plotted_count, excluded_count


def _error_runtime_plot(rows: list[Mapping[str, Any]], error_view: str):
    candidates = [row for row in rows if _observed(row, error_view)]
    signed_view = error_view == "signed"
    plotted: list[tuple[Mapping[str, Any], float, float]] = []
    excluded = len(rows) - len(candidates)
    for row in candidates:
        runtime = _finite(row.get("runtime_seconds"))
        error = _error_value(row, error_view)
        plotted_error = error if signed_view else abs(error) if error is not None else None
        if runtime is None or runtime <= 0 or plotted_error is None or plotted_error == 0:
            excluded += 1
            continue
        plotted.append((row, runtime, plotted_error))
    if not plotted:
        return _empty_figure("No positive runtime and error values for log plot."), 0, excluded

    algorithms = sorted({_group_label(row) for row, _, _ in plotted})
    colors = {algorithm: plt.get_cmap("tab10")(index % 10) for index, algorithm in enumerate(algorithms)}
    molecules = sorted({str(row.get("molecule") or "UNKNOWN") for row, _, _ in plotted})
    markers = {molecule: ("o", "s", "^", "D", "P", "X")[index % 6] for index, molecule in enumerate(molecules)}
    fig, ax = plt.subplots(figsize=(9.2, 5.8))
    fig.subplots_adjust(left=0.12, right=0.73, bottom=0.14, top=0.9)
    for row, runtime, error in plotted:
        algorithm = _group_label(row)
        molecule = str(row.get("molecule") or "UNKNOWN")
        ax.scatter(
            runtime,
            error,
            color=colors[algorithm],
            marker=markers[molecule],
            facecolors=(
                colors[algorithm]
                if _observation_bucket(row) == "validated"
                else "none"
            ),
            edgecolors=colors[algorithm],
            alpha=0.85 if _observation_bucket(row) == "validated" else 0.7,
            s=48,
        )
    ax.set_xscale("log")
    if signed_view:
        max_error = max(abs(error) for _, _, error in plotted)
        ax.set_yscale("symlog", linthresh=max(max_error * 1e-3, 1e-12))
        ylabel = "Signed energy error (Ha, symlog scale)"
    else:
        ax.set_yscale("log")
        ylabel = "Absolute energy error (Ha, log scale)"
    ax.set_xlabel("Runtime (seconds, log scale)")
    ax.set_ylabel(ylabel)
    ax.set_title("Terminal energy error versus runtime")
    ax.grid(True, alpha=0.3, which="both")
    algorithm_handles = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=colors[name], label=name, markersize=7)
        for name in algorithms
    ]
    molecule_handles = [
        Line2D([0], [0], marker=markers[name], color="#444", linestyle="", label=name, markersize=7)
        for name in molecules
    ]
    status_handles = [
        Line2D([0], [0], marker="o", color="#111111", markerfacecolor="#111111", linestyle="", markersize=6, label="Validated"),
        Line2D([0], [0], marker="o", color="#111111", markerfacecolor="white", linestyle="", markersize=6, label="Diagnostic / unvalidated"),
    ]
    handles = algorithm_handles + molecule_handles + status_handles
    if handles:
        ax.legend(
            handles=handles,
            loc="upper left",
            bbox_to_anchor=(1.02, 1.0),
            borderaxespad=0.0,
            title="Algorithm / molecule",
            fontsize=8,
        )
    return fig, len(plotted), excluded


def render_plots(
    rows: list[Mapping[str, Any]],
    output_dir: Path,
    *,
    error_view: str = "absolute",
    output_format: str = "png",
) -> dict[str, Any]:
    """Render the four compact plots and return a plot manifest."""

    if error_view not in {"absolute", "signed"}:
        raise ValueError("error_view must be absolute or signed")
    if output_format not in {"png", "svg", "pdf", "both"}:
        raise ValueError("output_format must be png, svg, pdf, or both")

    plots = [
        ("error_by_algorithm", lambda: _error_plot(rows, error_view)),
        ("convergence_by_algorithm", lambda: _convergence_plot(rows)),
        ("runtime_by_algorithm", lambda: _runtime_plot(rows)),
        ("error_vs_runtime", lambda: _error_runtime_plot(rows, error_view)),
    ]
    files: list[str] = []
    plot_metadata: dict[str, Any] = {}
    for name, builder in plots:
        figure, plotted_count, excluded_count = builder()
        generated = _save(figure, output_dir, name, output_format)
        files.extend(generated)
        plot_metadata[name] = {
            "files": generated,
            "plotted_count": plotted_count,
            "excluded_count": excluded_count,
        }

    return {
        "plot_schema_version": "qss-benchmark-plots.v3",
        "population_definitions": {
            "validated": "Rows marked benchmark_eligible.",
            "observed": "Completed rows with finite terminal energy error; non-converged rows remain visible.",
            "excluded": "Rows without a completed finite terminal result, or without positive runtime for runtime plots.",
        },
        "error_view": error_view,
        "output_format": output_format,
        "source_row_count": len(rows),
        "files": files,
        "plots": plot_metadata,
    }


__all__ = ["PLOT_NAMES", "render_plots"]
