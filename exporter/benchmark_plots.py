"""Compact, layout-safe plots for normalized QSS benchmark rows."""

from __future__ import annotations

import math
import textwrap
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


FIGURE_WIDTH_IN = 6.85
BOX_HATCHES = ("", "///", "...", r"\\", "++", "xx")
MOLECULE_MARKERS = ("o", "s", "^", "D", "P", "X", "v", "<", ">", "h", "8", "*")

PLOT_NAMES = (
    "error_by_algorithm",
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
        and _error_value(row, error_view) is not None
    )


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
    clean = value.replace("_", " ")
    return "\n".join(
        textwrap.wrap(clean, width=17, break_long_words=False, break_on_hyphens=False)
    )


def _boxplot(ax, groups: list[list[float]], labels: list[str]) -> None:
    """Draw a boxplot without relying on version-specific label arguments."""

    boxplot = ax.boxplot(
        groups,
        patch_artist=True,
        medianprops={"color": "black", "linewidth": 1.0},
        boxprops={"facecolor": "white", "edgecolor": "black", "linewidth": 0.6},
        whiskerprops={"color": "black", "linewidth": 0.6},
        capprops={"color": "black", "linewidth": 0.6},
        flierprops={
            "marker": "o",
            "markerfacecolor": "white",
            "markeredgecolor": "black",
            "markersize": 3.5,
            "markeredgewidth": 0.6,
        },
    )
    for index, box in enumerate(boxplot["boxes"]):
        box.set_hatch(BOX_HATCHES[index % len(BOX_HATCHES)])
    ax.set_xticks(range(1, len(labels) + 1), [_safe_label(label) for label in labels])


def _save(fig, output_dir: Path, name: str, output_format: str) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    formats = ("pdf", "png") if output_format == "both" else (output_format,)
    result: list[str] = []
    for extension in {"pdf", "png", "svg"} - set(formats):
        (output_dir / f"{name}.{extension}").unlink(missing_ok=True)
    for extension in formats:
        path = output_dir / f"{name}.{extension}"
        fig.savefig(path, dpi=300, bbox_inches="tight", pad_inches=0.12)
        result.append(path.name)
    plt.close(fig)
    return result


def _empty_figure(message: str, *, width: float = 8.0):
    fig, ax = plt.subplots(figsize=(min(width, FIGURE_WIDTH_IN), 3.8), constrained_layout=True)
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
        figsize=(FIGURE_WIDTH_IN, 4.1),
        constrained_layout=True,
    )
    _boxplot(ax, [groups[label] for label in labels], labels)
    ax.set_xlabel("Algorithm · execution path")
    ax.set_ylabel(
        f"{'Signed' if error_view == 'signed' else 'Absolute'} energy error (Ha; symlog scale)"
    )
    ax.set_yscale("symlog", linthresh=1e-8)
    if error_view == "absolute":
        ax.set_ylim(bottom=0)
    ax.grid(True, axis="y", alpha=0.3, which="both")
    return fig, plotted_count, excluded_count


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
        figsize=(FIGURE_WIDTH_IN, 4.1),
        constrained_layout=True,
    )
    _boxplot(ax, [groups[label] for label in labels], labels)
    positive = all(value > 0 for values in groups.values() for value in values)
    if positive:
        ax.set_yscale("log")
        ylabel = "Runtime (seconds, log scale)"
    else:
        ylabel = "Runtime (seconds)"
    ax.set_xlabel("Algorithm · execution path")
    ax.set_ylabel(ylabel)
    ax.grid(True, axis="y", alpha=0.3, which="both")
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
    markers = {
        molecule: MOLECULE_MARKERS[index % len(MOLECULE_MARKERS)]
        for index, molecule in enumerate(molecules)
    }
    fig, ax = plt.subplots(figsize=(FIGURE_WIDTH_IN, 4.8))
    fig.subplots_adjust(left=0.14, right=0.66, bottom=0.16, top=0.96)
    for row, runtime, error in plotted:
        algorithm = _group_label(row)
        molecule = str(row.get("molecule") or "UNKNOWN")
        ax.scatter(
            runtime,
            error,
            color=colors[algorithm],
            marker=markers[molecule],
            facecolors=colors[algorithm],
            edgecolors=colors[algorithm],
            alpha=0.8,
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
    ax.grid(True, alpha=0.3, which="both")
    algorithm_handles = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=colors[name], label=name, markersize=7)
        for name in algorithms
    ]
    molecule_handles = [
        Line2D([0], [0], marker=markers[name], color="#444", linestyle="", label=name, markersize=7)
        for name in molecules
    ]
    algorithm_legend = ax.legend(
        handles=algorithm_handles,
        loc="upper left",
        bbox_to_anchor=(1.02, 1.0),
        borderaxespad=0.0,
        title="Algorithm / path",
        fontsize=7,
        title_fontsize=7.5,
    )
    ax.add_artist(algorithm_legend)
    ax.legend(
        handles=molecule_handles,
        loc="lower left",
        bbox_to_anchor=(1.02, 0.0),
        borderaxespad=0.0,
        title="Molecule",
        fontsize=7,
        title_fontsize=7.5,
        ncol=1 if len(molecules) < 8 else 2,
    )
    return fig, len(plotted), excluded


def render_plots(
    rows: list[Mapping[str, Any]],
    output_dir: Path,
    *,
    error_view: str = "absolute",
    output_format: str = "png",
) -> dict[str, Any]:
    """Render the three publication-sized plots and return a plot manifest."""

    if error_view not in {"absolute", "signed"}:
        raise ValueError("error_view must be absolute or signed")
    if output_format not in {"png", "svg", "pdf", "both"}:
        raise ValueError("output_format must be png, svg, pdf, or both")
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8.5,
            "axes.labelsize": 8.5,
            "xtick.labelsize": 7.5,
            "ytick.labelsize": 7.5,
            "legend.fontsize": 7,
            "legend.title_fontsize": 7.5,
            "axes.linewidth": 0.7,
            "lines.linewidth": 1.0,
            "patch.linewidth": 0.6,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
            "savefig.facecolor": "white",
        }
    )

    plots = [
        ("error_by_algorithm", lambda: _error_plot(rows, error_view)),
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
        "plot_schema_version": "qss-benchmark-plots.v5",
        "population_definitions": {
            "terminal": "Completed rows with finite terminal energy error; convergence flags do not filter them.",
            "excluded": "Rows without a completed finite terminal result, or without positive runtime for runtime plots.",
        },
        "error_view": error_view,
        "output_format": output_format,
        "source_row_count": len(rows),
        "files": files,
        "plots": plot_metadata,
    }


__all__ = ["PLOT_NAMES", "render_plots"]
