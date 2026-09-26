#!/usr/bin/env python3
"""Generate paper statistics and publication figures from QSS exports."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle
from matplotlib.ticker import NullFormatter

try:
    from .benchmark_io import ExporterError, load_folder_source
except ImportError:  # pragma: no cover - direct script execution
    from benchmark_io import ExporterError, load_folder_source


REPORT_SCHEMA_VERSION = "qss-paper-report.v3"
PALETTE = {
    "eligible": "#0072B2",
    "diagnostic": "#E69F00",
    "non_converged": "#D55E00",
    "incomplete": "#999999",
    "VQE": "#0072B2",
    "QSE": "#56B4E9",
    "KQD": "#009E73",
    "QFD": "#F0E442",
    "SQD": "#D55E00",
    "SKQD": "#CC79A7",
}
CAMPAIGN_LABELS = {
    "paper-statevector-balanced-10m": "Statevector",
    "paper-aer-ideal-balanced-10m": "Ideal Aer",
    "paper-preset-comparison-4m": "Preset comparison",
    "paper-aer-noisy-core-2m": "Custom noise Aer",
    "paper-aer-noisy-reduced-2m": "Reduced noise Aer",
    "paper-aer-noisy-phoenix-2m": "Phoenix-derived Aer",
    "paper-seed-role-study": "Seed-role study",
    "paper-resource-ablation": "Resource ablation",
}
ACCURACY_RUNTIME_PANELS = (
    ("Statevector", frozenset({"paper-statevector-balanced-10m"})),
    ("Ideal Aer", frozenset({"paper-aer-ideal-balanced-10m"})),
    ("Preset comparison", frozenset({"paper-preset-comparison-4m"})),
    ("Local noise Aer", frozenset({"paper-aer-noisy-core-2m", "paper-aer-noisy-phoenix-2m"})),
    ("Seed roles", frozenset({"paper-seed-role-study"})),
    ("Resource ablation", frozenset({"paper-resource-ablation"})),
)


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _eligible(row: Mapping[str, Any]) -> bool:
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


def _error_mHa(row: Mapping[str, Any]) -> float | None:
    """Return a finite observed error for plotting, without changing eligibility."""
    explicit = _number(row.get("absolute_error"))
    if explicit is not None:
        return abs(explicit) * 1000
    final_energy = _number(row.get("final_energy"))
    reference_energy = _number(row.get("reference_energy"))
    if final_energy is None or reference_energy is None:
        return None
    return abs(final_energy - reference_energy) * 1000


def _runtime_seconds(row: Mapping[str, Any]) -> float | None:
    runtime = _number(row.get("runtime_seconds"))
    return runtime if runtime is not None and runtime > 0 else None


def _observed(row: Mapping[str, Any]) -> bool:
    """Whether a completed row has finite values that can be inspected."""
    return (
        str(row.get("status") or "").lower() == "completed"
        and row.get("reported_energy_is_valid") is not False
        and _error_mHa(row) is not None
        and _runtime_seconds(row) is not None
    )


def _observation_bucket(row: Mapping[str, Any]) -> str:
    """Classify rows for figures without treating non-convergence as failure."""
    if _eligible(row):
        return "validated"
    if not _observed(row):
        return "incomplete"
    if row.get("projected_solve_is_diagnostic") is True:
        return "diagnostic"
    return "unvalidated"


def _campaign_id(source: Mapping[str, Any], folder: Path) -> str:
    return str(
        source.get("campaignId")
        or source.get("campaign_id")
        or folder.name
    )


def _campaign_label(campaign_id: str) -> str:
    return CAMPAIGN_LABELS.get(campaign_id, campaign_id.replace("paper-", "").replace("-", " "))


def _short_molecule(value: Any) -> str:
    raw = str(value or "UNKNOWN")
    replacements = {
        "Hydrogen (H₂)": "H2",
        "Lithium Hydride (LiH)": "LiH",
        "Hydrogen Fluoride (HF)": "HF",
        "Hydrogen Chloride (HCl)": "HCl",
        "Sodium Hydride (NaH)": "NaH",
        "Water (H₂O)": "H2O",
        "Beryllium Hydride (BeH₂)": "BeH2",
        "Hydrogen Sulfide (H₂S)": "H2S",
        "Magnesium Hydride (MgH₂)": "MgH2",
        "Nitrogen (N₂)": "N2",
    }
    return replacements.get(raw, raw.replace(" ", "\n"))


def _algorithm_label(value: Any) -> str:
    return str(value or "UNKNOWN").upper()


def _variant_label(row: Mapping[str, Any]) -> str:
    return str(row.get("variant_label") or row.get("variant_id") or _algorithm_label(row.get("algorithm")))


def _variant_display(row: Mapping[str, Any]) -> str:
    """Remove the method prefix from shared preset labels for compact axes."""
    algorithm = _algorithm_label(row.get("algorithm"))
    label = _variant_label(row)
    prefix = f"{algorithm} "
    if label.upper().startswith(prefix):
        return label[len(prefix):]
    variant_id = str(row.get("variant_id") or "")
    id_prefix = f"{str(row.get('algorithm') or '').lower()}-"
    if variant_id.startswith(id_prefix):
        return variant_id[len(id_prefix):].replace("-", " ")
    return label


def _ordered_preset_labels(labels: Iterable[str]) -> list[str]:
    preferred = {name: index for index, name in enumerate(("fastest", "balanced", "best accuracy", "custom deep"))}
    return sorted(labels, key=lambda value: (preferred.get(value.lower(), len(preferred)), value.lower()))


def _resource_budget(label: Any) -> float | None:
    match = re.search(r"(?i)(\d+(?:\.\d+)?)\s*([km]?)", str(label or ""))
    if not match:
        return None
    value = float(match.group(1))
    suffix = match.group(2).lower()
    return value * {"": 1.0, "k": 1_000.0, "m": 1_000_000.0}[suffix]


def _format_budget(value: float) -> str:
    if value >= 1_000_000 and value % 1_000_000 == 0:
        return f"{value / 1_000_000:g}M"
    if value >= 1_000 and value % 1_000 == 0:
        return f"{value / 1_000:g}k"
    return f"{value:g}"


def _quantile(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + fraction * (ordered[upper] - ordered[lower])


def _status_bucket(row: Mapping[str, Any]) -> str:
    if _eligible(row):
        return "eligible"
    if str(row.get("status") or "").lower() != "completed":
        return "incomplete"
    if row.get("projected_solve_is_diagnostic") is True:
        return "diagnostic"
    if row.get("scientific_converged") is False or row.get("converged") is False:
        return "non_converged"
    return "incomplete"


def _group_stats(rows: Iterable[Mapping[str, Any]], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[tuple(str(row.get(key) or "UNKNOWN") for key in keys)].append(row)

    result: list[dict[str, Any]] = []
    for group_key, group_rows in sorted(groups.items()):
        eligible = [row for row in group_rows if _eligible(row)]
        errors = [value for row in eligible if (value := _error_mHa(row)) is not None]
        runtimes = [value for row in eligible if (value := _runtime_seconds(row)) is not None]
        observed = [row for row in group_rows if _observed(row)]
        observed_errors = [value for row in observed if (value := _error_mHa(row)) is not None]
        observed_runtimes = [value for row in observed if (value := _runtime_seconds(row)) is not None]
        bucket_counts = Counter(_status_bucket(row) for row in group_rows)
        observation_counts = Counter(_observation_bucket(row) for row in group_rows)
        record: dict[str, Any] = {key: value for key, value in zip(keys, group_key)}
        record.update(
            {
                "row_count": len(group_rows),
                "eligible_count": len(errors),
                "median_absolute_error_mHa": statistics.median(errors) if errors else None,
                "q1_absolute_error_mHa": _quantile(errors, 0.25),
                "q3_absolute_error_mHa": _quantile(errors, 0.75),
                "median_runtime_seconds": statistics.median(runtimes) if runtimes else None,
                "eligible": bucket_counts.get("eligible", 0),
                "diagnostic": bucket_counts.get("diagnostic", 0),
                "non_converged": bucket_counts.get("non_converged", 0),
                "incomplete": bucket_counts.get("incomplete", 0),
                "observed_count": len(observed_errors),
                "median_observed_absolute_error_mHa": statistics.median(observed_errors) if observed_errors else None,
                "q1_observed_absolute_error_mHa": _quantile(observed_errors, 0.25),
                "q3_observed_absolute_error_mHa": _quantile(observed_errors, 0.75),
                "median_observed_runtime_seconds": statistics.median(observed_runtimes) if observed_runtimes else None,
                "validated_observation_count": observation_counts.get("validated", 0),
                "diagnostic_observation_count": observation_counts.get("diagnostic", 0),
                "unvalidated_observation_count": observation_counts.get("unvalidated", 0),
            }
        )
        result.append(record)
    return result


def _load_sources(input_dirs: Iterable[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for input_dir in input_dirs:
        bundle = load_folder_source(input_dir)
        campaign_id = _campaign_id(bundle.benchmark, input_dir)
        for row in bundle.rows:
            records.append(dict(row, campaign_id=campaign_id, campaign_label=_campaign_label(campaign_id)))
    if not records:
        raise ExporterError("No benchmark rows were loaded")
    return records


def _write_records(records: list[Mapping[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for record in records:
        for key in record:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow({key: _csv_value(record.get(key)) for key in fieldnames})


def _csv_value(value: Any) -> Any:
    if isinstance(value, list):
        return json.dumps(value, separators=(",", ":"))
    return "" if value is None else value


def build_statistics(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    campaigns = []
    for campaign_id, campaign_rows in sorted(_group_rows(rows, "campaign_id")):
        buckets = Counter(_status_bucket(row) for row in campaign_rows)
        campaigns.append(
            {
                "campaign_id": campaign_id,
                "label": _campaign_label(campaign_id),
                "row_count": len(campaign_rows),
                "status_counts": dict(sorted(Counter(str(row.get("status") or "missing") for row in campaign_rows).items())),
                "eligibility_counts": dict(sorted(buckets.items())),
                "observation_counts": dict(
                    sorted(Counter(_observation_bucket(row) for row in campaign_rows).items())
                ),
            }
        )
    unvalidated = [row for row in rows if _observation_bucket(row) == "unvalidated"]
    unvalidated_reasons = Counter(
        str(row.get("convergence_failure_reason") or "unknown")
        for row in unvalidated
    )
    unvalidated_by_group = Counter(
        (
            str(row.get("campaign_id") or "UNKNOWN"),
            str(row.get("algorithm") or "UNKNOWN"),
            str(row.get("convergence_failure_reason") or "unknown"),
        )
        for row in unvalidated
    )
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "row_count": len(rows),
        "eligible_row_count": sum(_eligible(row) for row in rows),
        "observation_counts": dict(sorted(Counter(_observation_bucket(row) for row in rows).items())),
        "campaigns": campaigns,
        "unvalidated_reason_counts": dict(sorted(unvalidated_reasons.items())),
        "unvalidated_by_campaign_algorithm": [
            {
                "campaign_id": campaign_id,
                "algorithm": algorithm,
                "convergence_failure_reason": reason,
                "count": count,
            }
            for (campaign_id, algorithm, reason), count in sorted(unvalidated_by_group.items())
        ],
        "by_campaign_algorithm": _group_stats(rows, ("campaign_id", "algorithm")),
        "by_campaign_variant": _group_stats(rows, ("campaign_id", "variant_id")),
        "by_campaign_variant_algorithm": _group_stats(rows, ("campaign_id", "variant_label", "algorithm")),
        "by_campaign_molecule_algorithm": _group_stats(rows, ("campaign_id", "molecule", "algorithm")),
        "by_campaign_seed": _group_stats(rows, ("campaign_id", "seed")),
        "by_condition_algorithm": _group_stats(rows, ("campaign_label", "algorithm")),
        "field_presence": [
            {
                "field": field,
                "present_count": sum(row.get(field) is not None for row in rows),
                "missing_count": sum(row.get(field) is None for row in rows),
            }
            for field in (
                "variant_id",
                "variant_label",
                "seed",
                "seed_roles",
                "requested_shots",
                "effective_shots",
                "requested_estimator_precision",
                "effective_estimator_precision",
                "noise_source",
                "noise_fingerprint",
                "actual_execution_target",
                "actual_path_class",
                "reference_method",
                "reference_active_space",
                "runtime_seconds",
                "absolute_error",
                "benchmark_eligible",
                "benchmark_exclusion_reason",
            )
        ],
    }


def _group_rows(rows: Iterable[Mapping[str, Any]], key: str) -> list[tuple[str, list[Mapping[str, Any]]]]:
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(key) or "UNKNOWN")].append(row)
    return list(groups.items())


def _apply_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 8,
            "figure.dpi": 120,
            "savefig.facecolor": "white",
            "axes.facecolor": "white",
        }
    )


def _save(fig: Any, output_dir: Path, name: str, output_format: str) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    formats = ("pdf", "png") if output_format == "both" else (output_format,)
    files: list[str] = []
    for extension in formats:
        path = output_dir / f"{name}.{extension}"
        fig.savefig(path, bbox_inches="tight", pad_inches=0.12, dpi=300)
        files.append(path.name)
    plt.close(fig)
    return files


def _empty(message: str) -> Any:
    fig, ax = plt.subplots(figsize=(7.2, 4.2), constrained_layout=True)
    ax.text(0.5, 0.5, message, ha="center", va="center", transform=ax.transAxes)
    ax.set_axis_off()
    return fig


def _plot_eligibility(rows: list[Mapping[str, Any]], output_dir: Path, fmt: str) -> list[str]:
    grouped = [(key, values) for key, values in _group_rows(rows, "campaign_label")]
    if not grouped:
        return _save(_empty("No campaign rows."), output_dir, "eligibility_matrix", fmt)
    labels = [key for key, _ in grouped]
    categories = ("validated", "diagnostic", "unvalidated", "incomplete")
    colors = (PALETTE["eligible"], PALETTE["diagnostic"], PALETTE["non_converged"], PALETTE["incomplete"])
    fig, ax = plt.subplots(figsize=(8.6, 4.8), constrained_layout=True)
    bottom = [0] * len(labels)
    for category, color in zip(categories, colors):
        values = [sum(_observation_bucket(row) == category for row in group) for _, group in grouped]
        label = {
            "validated": "Validated",
            "diagnostic": "Diagnostic observation",
            "unvalidated": "Unvalidated finite observation",
            "incomplete": "Incomplete or missing",
        }[category]
        ax.bar(labels, values, bottom=bottom, label=label, color=color, edgecolor="white", linewidth=0.4)
        bottom = [left + value for left, value in zip(bottom, values)]
    ax.set_ylabel("Rows")
    ax.set_title("Campaign populations and validation status")
    ax.tick_params(axis="x", rotation=28)
    ax.legend(ncol=2, frameon=False)
    ax.grid(axis="y", alpha=0.25)
    return _save(fig, output_dir, "eligibility_matrix", fmt)


def _plot_preset(rows: list[Mapping[str, Any]], output_dir: Path, fmt: str) -> list[str]:
    selected = [
        dict(row, plot_variant=_variant_display(row))
        for row in rows
        if row.get("campaign_id") == "paper-preset-comparison-4m"
    ]
    groups = _group_stats(selected, ("plot_variant", "algorithm"))
    if not groups:
        return _save(_empty("No preset observations."), output_dir, "preset_tradeoff", fmt)
    variants = _ordered_preset_labels({str(item["plot_variant"]) for item in groups})
    algorithms = sorted({str(item["algorithm"]).lower() for item in groups})
    x = list(range(len(variants)))
    width = 0.78 / max(1, len(algorithms))
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.4), constrained_layout=True)
    for index, algorithm in enumerate(algorithms):
        values = []
        runtimes = []
        validated_values = []
        validated_runtimes = []
        for variant in variants:
            item = next((record for record in groups if record["plot_variant"] == variant and str(record["algorithm"]).lower() == algorithm), None)
            values.append(item["median_observed_absolute_error_mHa"] if item else math.nan)
            runtimes.append(item["median_observed_runtime_seconds"] if item else math.nan)
            validated_values.append(item["median_absolute_error_mHa"] if item else math.nan)
            validated_runtimes.append(item["median_runtime_seconds"] if item else math.nan)
        positions = [value - 0.39 + width / 2 + index * width for value in x]
        label = algorithm.upper()
        color = PALETTE.get(label, "#555555")
        axes[0].bar(positions, values, width=width, label=label, color=color, alpha=0.58, edgecolor="black", linewidth=0.3)
        axes[1].bar(positions, runtimes, width=width, label=label, color=color, alpha=0.58, edgecolor="black", linewidth=0.3)
        axes[0].scatter(positions, validated_values, color=color, edgecolors="black", linewidths=0.45, s=22, zorder=3)
        axes[1].scatter(positions, validated_runtimes, color=color, edgecolors="black", linewidths=0.45, s=22, zorder=3)
    axes[0].set_ylabel("Median absolute error (mHa)")
    axes[1].set_ylabel("Median runtime (s)")
    for ax in axes:
        ax.set_xticks(x, [label.replace(" ", "\n") for label in variants])
        ax.grid(axis="y", alpha=0.25)
    axes[0].set_title("Finite observed error")
    axes[1].set_title("Finite observed runtime")
    axes[0].set_yscale("symlog", linthresh=0.01)
    axes[0].set_ylim(bottom=0)
    axes[1].set_yscale("log")
    legend = [
        Line2D([0], [0], marker="o", color="black", markerfacecolor="white", linestyle="None", markersize=5, label="Validated median"),
        Patch(facecolor="#aaaaaa", edgecolor="black", alpha=0.58, label="All finite observations"),
    ]
    axes[0].legend(handles=legend, frameon=False, loc="upper left")
    axes[1].legend(frameon=False, ncol=3)
    fig.suptitle("Preset comparison: observed estimates and validated medians", fontsize=11)
    return _save(fig, output_dir, "preset_tradeoff", fmt)


def _plot_seed_sensitivity(rows: list[Mapping[str, Any]], output_dir: Path, fmt: str) -> list[str]:
    selected = [row for row in rows if row.get("campaign_id") == "paper-seed-role-study" and _observed(row) and _number(row.get("seed")) is not None]
    if not selected:
        return _save(_empty("No finite seed-role observations."), output_dir, "seed_sensitivity", fmt)
    fig, ax = plt.subplots(figsize=(7.8, 4.8), constrained_layout=True)
    algorithms = sorted({str(row.get("algorithm") or "").lower() for row in selected})
    for algorithm in algorithms:
        color = PALETTE.get(algorithm.upper(), "#555555")
        for bucket, marker in (("validated", "o"), ("diagnostic", "s"), ("unvalidated", "x")):
            points = [
                row for row in selected
                if str(row.get("algorithm") or "").lower() == algorithm
                and _observation_bucket(row) == bucket
            ]
            if not points:
                continue
            scatter_args = {
                "label": algorithm.upper() if bucket == "validated" else "_nolegend_",
                "color": color,
                "marker": marker,
                "linewidths": 0.65,
                "s": 42,
                "alpha": 1.0 if bucket == "validated" else 0.8,
            }
            if bucket != "unvalidated":
                scatter_args.update({"facecolors": color if bucket == "validated" else "none", "edgecolors": "black"})
            ax.scatter(
                [_number(row.get("seed")) for row in points],
                [_error_mHa(row) for row in points],
                **scatter_args,
            )
    ax.set_xlabel("Campaign seed")
    ax.set_ylabel("Absolute error (mHa)")
    ax.set_title("Seed sensitivity: finite observed estimates")
    ax.grid(alpha=0.25)
    handles = [
        Line2D([0], [0], marker="o", color="black", markerfacecolor="black", linestyle="None", markersize=5, label="Validated"),
        Line2D([0], [0], marker="s", color="black", markerfacecolor="white", linestyle="None", markersize=5, label="Diagnostic"),
        Line2D([0], [0], marker="x", color="black", linestyle="None", markersize=6, label="Unvalidated"),
    ]
    method_handles, method_labels = ax.get_legend_handles_labels()
    ax.legend(method_handles + handles, method_labels + [item.get_label() for item in handles], frameon=False, ncol=3)
    return _save(fig, output_dir, "seed_sensitivity", fmt)


def _plot_conditions(rows: list[Mapping[str, Any]], output_dir: Path, fmt: str) -> list[str]:
    campaign_ids = {
        "paper-statevector-balanced-10m",
        "paper-aer-ideal-balanced-10m",
        "paper-aer-noisy-core-2m",
        "paper-aer-noisy-phoenix-2m",
    }
    selected = [row for row in rows if row.get("campaign_id") in campaign_ids]
    groups = _group_stats(selected, ("campaign_label", "algorithm"))
    if not groups:
        return _save(_empty("No backend/noise observations."), output_dir, "backend_noise_comparison", fmt)
    conditions = sorted({str(item["campaign_label"]) for item in groups})
    algorithms = sorted({str(item["algorithm"]).lower() for item in groups})
    fig, ax = plt.subplots(figsize=(9.0, 4.8), constrained_layout=True)
    width = 0.78 / max(1, len(algorithms))
    x = list(range(len(conditions)))
    for index, algorithm in enumerate(algorithms):
        values = []
        validated_values = []
        for condition in conditions:
            item = next((record for record in groups if record["campaign_label"] == condition and str(record["algorithm"]).lower() == algorithm), None)
            values.append(item["median_observed_absolute_error_mHa"] if item else math.nan)
            validated_values.append(item["median_absolute_error_mHa"] if item else math.nan)
        positions = [value - 0.39 + width / 2 + index * width for value in x]
        label = algorithm.upper()
        color = PALETTE.get(label, "#555555")
        ax.bar(positions, values, width=width, label=label, color=color, alpha=0.58, edgecolor="black", linewidth=0.3)
        ax.scatter(positions, validated_values, color=color, edgecolors="black", linewidths=0.45, s=22, zorder=3)
    ax.set_xticks(x, [condition.replace(" ", "\n") for condition in conditions])
    ax.set_ylabel("Median absolute error (mHa)")
    ax.set_title("Local conditions: finite observed error")
    ax.set_yscale("symlog", linthresh=0.01)
    ax.set_ylim(bottom=0)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False, ncol=3, title="Bars: all observed; dots: validated")
    return _save(fig, output_dir, "backend_noise_comparison", fmt)


def _plot_heatmap(rows: list[Mapping[str, Any]], output_dir: Path, fmt: str) -> list[str]:
    selected = [row for row in rows if row.get("campaign_id") == "paper-statevector-balanced-10m"]
    groups = _group_stats(selected, ("algorithm", "molecule"))
    algorithms = sorted({str(item["algorithm"]).lower() for item in groups})
    molecules = sorted({str(item["molecule"]) for item in groups})
    if not algorithms or not molecules:
        return _save(_empty("No statevector observations."), output_dir, "molecule_algorithm_heatmap", fmt)
    data: list[list[float]] = []
    labels: list[list[str]] = []
    for algorithm in algorithms:
        row_values: list[float] = []
        row_labels: list[str] = []
        for molecule in molecules:
            item = next((record for record in groups if str(record["algorithm"]).lower() == algorithm and record["molecule"] == molecule), None)
            value = item["median_observed_absolute_error_mHa"] if item else None
            row_values.append(value if value is not None else math.nan)
            if value is None or not item or item["observed_count"] == 0:
                row_labels.append("—")
            else:
                status = "V" if item["eligible_count"] else "U"
                row_labels.append(f"{value:.2f}\n{status} {item['eligible_count']}/{item['observed_count']}")
        data.append(row_values)
        labels.append(row_labels)
    fig, ax = plt.subplots(figsize=(11.0, 4.7), constrained_layout=True)
    cmap = plt.get_cmap("YlGnBu").copy()
    cmap.set_bad("#f7f7f7")
    finite_values = [value for row in data for value in row if not math.isnan(value)]
    log_floor = 0.001
    plot_data = [
        [value if math.isnan(value) else max(log_floor, value) for value in row]
        for row in data
    ]
    image = ax.imshow(
        plot_data,
        aspect="auto",
        cmap=cmap,
        norm=LogNorm(vmin=log_floor, vmax=max(1.0, max(finite_values, default=1.0))),
    )
    ax.set_xticks(range(len(molecules)), [_short_molecule(value) for value in molecules])
    ax.set_yticks(range(len(algorithms)), [value.upper() for value in algorithms])
    ax.set_title("Statevector median absolute error (mHa; eligible n)")
    for i, row in enumerate(labels):
        for j, label in enumerate(row):
            ax.text(j, i, label, ha="center", va="center", fontsize=7, color="black")
            item = next((record for record in groups if str(record["algorithm"]).lower() == algorithms[i] and record["molecule"] == molecules[j]), None)
            if item and item["observed_count"] and not item["eligible_count"]:
                ax.add_patch(Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False, hatch="///", edgecolor="#555555", linewidth=0.0))
    colorbar = fig.colorbar(image, ax=ax, shrink=0.84)
    colorbar.set_label("Median finite observed error (mHa; log scale)")
    ax.set_title("Statevector error by molecule and method (V=validated, U=unvalidated)")
    return _save(fig, output_dir, "molecule_algorithm_heatmap", fmt)


def _plot_resource(rows: list[Mapping[str, Any]], output_dir: Path, fmt: str) -> list[str]:
    selected = [row for row in rows if row.get("campaign_id") == "paper-resource-ablation"]
    groups = _group_stats(selected, ("variant_label", "algorithm"))
    budget_values = {
        str(item["variant_label"]): _resource_budget(item["variant_label"])
        for item in groups
    }
    if not groups or not any(value is not None for value in budget_values.values()):
        return _save(_empty("No resource-ablation observations."), output_dir, "resource_ablation", fmt)
    algorithms = sorted({str(item["algorithm"]).lower() for item in groups})
    fig, axes = plt.subplots(len(algorithms), 2, figsize=(10.0, 3.4 * len(algorithms)), squeeze=False)
    for row_index, algorithm in enumerate(algorithms):
        algorithm_groups = [
            item for item in groups
            if str(item["algorithm"]).lower() == algorithm
            and budget_values.get(str(item["variant_label"])) is not None
        ]
        algorithm_groups.sort(key=lambda item: budget_values[str(item["variant_label"])])
        budgets = [budget_values[str(item["variant_label"])] for item in algorithm_groups]
        observed_values = [
            item["median_observed_absolute_error_mHa"] if item["observed_count"] else math.nan
            for item in algorithm_groups
        ]
        observed_runtimes = [
            item["median_observed_runtime_seconds"] if item["observed_count"] else math.nan
            for item in algorithm_groups
        ]
        validated_values = [
            item["median_absolute_error_mHa"] if item["eligible_count"] else math.nan
            for item in algorithm_groups
        ]
        validated_runtimes = [
            item["median_runtime_seconds"] if item["eligible_count"] else math.nan
            for item in algorithm_groups
        ]
        color = PALETTE.get(algorithm.upper(), "#555555")
        error_ax, runtime_ax = axes[row_index]
        error_ax.plot(budgets, observed_values, marker="x", linestyle="--", color=color, alpha=0.55)
        runtime_ax.plot(budgets, observed_runtimes, marker="x", linestyle="--", color=color, alpha=0.55)
        error_ax.plot(budgets, validated_values, marker="o", color=color)
        runtime_ax.plot(budgets, validated_runtimes, marker="o", color=color)
        budget_labels = [_format_budget(value) for value in budgets]
        for ax in (error_ax, runtime_ax):
            ax.set_xscale("log")
            ax.set_xticks(budgets, budget_labels)
            ax.xaxis.set_minor_formatter(NullFormatter())
            ax.set_xlabel("Configured sample budget (log scale)")
            ax.grid(axis="y", alpha=0.25)
        error_ax.set_ylabel("Median absolute error (mHa)")
        runtime_ax.set_ylabel("Median runtime (s)")
        error_ax.set_title(f"{algorithm.upper()}: finite observed error")
        runtime_ax.set_title(f"{algorithm.upper()}: finite observed runtime")
        error_ax.set_yscale("symlog", linthresh=0.01)
        error_ax.set_ylim(bottom=0)
        runtime_ax.set_yscale("log")
    legend = [
        Line2D([0], [0], marker="x", color="#555555", linestyle="--", label="Finite observed median"),
        Line2D([0], [0], marker="o", color="#555555", linestyle="-", label="Validated median"),
    ]
    fig.legend(handles=legend, loc="lower center", ncol=2, frameon=False, bbox_to_anchor=(0.5, 0.01))
    fig.suptitle("Resource ablation: ordered sample budgets", fontsize=12)
    fig.tight_layout(rect=(0, 0.06, 1, 0.95))
    return _save(fig, output_dir, "resource_ablation", fmt)


def _plot_accuracy_runtime(rows: list[Mapping[str, Any]], output_dir: Path, fmt: str) -> list[str]:
    """Show all finite estimates while keeping validation status explicit."""
    observed = [row for row in rows if _observed(row)]
    if not observed:
        return _save(_empty("No finite accuracy/runtime observations."), output_dir, "accuracy_runtime", fmt)

    fig, axes = plt.subplots(2, 3, figsize=(12.0, 8.4), constrained_layout=True, sharey=False)
    axes_flat = list(axes.flat)
    algorithms = sorted({str(row.get("algorithm") or "UNKNOWN").upper() for row in observed})
    for ax, (title, campaign_ids) in zip(axes_flat, ACCURACY_RUNTIME_PANELS):
        panel_rows = [row for row in observed if row.get("campaign_id") in campaign_ids]
        for algorithm in algorithms:
            color = PALETTE.get(algorithm, "#555555")
            for bucket, marker in (("validated", "o"), ("diagnostic", "s"), ("unvalidated", "x")):
                points = [
                    row for row in panel_rows
                    if str(row.get("algorithm") or "UNKNOWN").upper() == algorithm
                    and _observation_bucket(row) == bucket
                ]
                if not points:
                    continue
                scatter_args = {
                    "color": color,
                    "marker": marker,
                    "linewidths": 0.5,
                    "s": 25,
                    "alpha": 0.78 if bucket != "validated" else 0.9,
                }
                if bucket != "unvalidated":
                    scatter_args.update({"facecolors": color if bucket == "validated" else "none", "edgecolors": "black"})
                ax.scatter(
                    [_runtime_seconds(row) for row in points],
                    [_error_mHa(row) for row in points],
                    **scatter_args,
                )
        ax.axhline(1.6, color="#666666", linestyle=":", linewidth=0.8)
        ax.set_xscale("log")
        ax.set_yscale("symlog", linthresh=0.01)
        ax.set_ylim(bottom=0)
        ax.set_title(title)
        ax.set_xlabel("Runtime (s)")
        ax.set_ylabel("Absolute error (mHa)")
        ax.grid(alpha=0.22, which="both")
        if not panel_rows:
            ax.text(0.5, 0.5, "No finite observations", ha="center", va="center", transform=ax.transAxes)
    for ax in axes_flat[len(ACCURACY_RUNTIME_PANELS):]:
        ax.set_visible(False)

    method_handles = [
        Line2D([0], [0], marker="o", color=PALETTE.get(algorithm, "#555555"), linestyle="None", markersize=5, label=algorithm)
        for algorithm in algorithms
    ]
    status_handles = [
        Line2D([0], [0], marker="o", color="black", markerfacecolor="black", linestyle="None", markersize=5, label="Validated"),
        Line2D([0], [0], marker="s", color="black", markerfacecolor="white", linestyle="None", markersize=5, label="Diagnostic"),
        Line2D([0], [0], marker="x", color="black", linestyle="None", markersize=6, label="Unvalidated"),
        Line2D([0], [0], color="#666666", linestyle=":", linewidth=1, label="1.6 mHa threshold"),
    ]
    fig.legend(handles=method_handles + status_handles, loc="lower center", ncol=5, frameon=False, bbox_to_anchor=(0.5, -0.015))
    fig.suptitle("Accuracy versus runtime for finite observed estimates", fontsize=12)
    return _save(fig, output_dir, "accuracy_runtime", fmt)


def _plot_paths(rows: list[Mapping[str, Any]], output_dir: Path, fmt: str) -> list[str]:
    grouped = [(key, values) for key, values in _group_rows(rows, "campaign_label")]
    paths = sorted({str(row.get("actual_path_class") or "unknown") for row in rows})
    if not grouped or not paths:
        return _save(_empty("No execution-path observations."), output_dir, "execution_path_distribution", fmt)
    fig, ax = plt.subplots(figsize=(9.0, 4.8), constrained_layout=True)
    bottom = [0] * len(grouped)
    colors = [plt.get_cmap("viridis")(index / max(1, len(paths) - 1)) for index in range(len(paths))]
    for path, color in zip(paths, colors):
        values = [sum(str(row.get("actual_path_class") or "unknown") == path for row in rows_for_campaign) for _, rows_for_campaign in grouped]
        ax.bar([key for key, _ in grouped], values, bottom=bottom, label=path.replace("_", " "), color=color, edgecolor="white", linewidth=0.3)
        bottom = [left + value for left, value in zip(bottom, values)]
    ax.set_ylabel("Rows")
    ax.set_title("Observed execution paths")
    ax.tick_params(axis="x", rotation=28)
    ax.legend(frameon=False, bbox_to_anchor=(1.02, 1), loc="upper left")
    return _save(fig, output_dir, "execution_path_distribution", fmt)


def _latex_escape(value: Any) -> str:
    return str(value or "N/A").replace("&", r"\&").replace("_", r"\_")


def _write_latex_fragments(stats: Mapping[str, Any], output_dir: Path) -> None:
    rows = [
        "\\begin{tabular}{lrrrr}",
        "Campaign & Rows & Observed & Validated & Incomplete \\\\",
        "\\hline",
    ]
    for campaign in stats["campaigns"]:
        counts = campaign["observation_counts"]
        observed = counts.get("validated", 0) + counts.get("diagnostic", 0) + counts.get("unvalidated", 0)
        rows.append(
            f"{_latex_escape(campaign['label'])} & {campaign['row_count']} & {observed} & {counts.get('validated', 0)} & {counts.get('incomplete', 0)} "
            + r"\\"
        )
    rows.append("\\end{tabular}")
    (output_dir / "campaign_summary.tex").write_text("\n".join(rows) + "\n", encoding="utf-8")

    rows = [
        "\\begin{tabular}{@{}llrrrr@{}}",
        "Campaign & Algorithm & Observed $n$ & Validated $n$ & Observed error & Validated error \\\\",
        "\\hline",
    ]
    for item in stats["by_campaign_algorithm"]:
        observed_median = item["median_observed_absolute_error_mHa"]
        validated_median = item["median_absolute_error_mHa"]
        observed_value = f"{observed_median:.3f}" if observed_median is not None else "N/A"
        validated_value = f"{validated_median:.3f}" if validated_median is not None else "N/A"
        rows.append(
            f"{_latex_escape(_campaign_label(item['campaign_id']))} & {_latex_escape(_algorithm_label(item['algorithm']))} & {item['observed_count']} & {item['eligible_count']} & {observed_value} & {validated_value} \\\\"
        )
    rows.append("\\end{tabular}")
    (output_dir / "algorithm_summary.tex").write_text("\n".join(rows) + "\n", encoding="utf-8")

    rows = [
        "\\begin{tabular}{@{}llrrrr@{}}",
        "Variant & Algorithm & Rows & Observed & Validated & Obs. error (mHa) \\\\",
        "\\hline",
    ]
    for item in stats["by_campaign_variant_algorithm"]:
        if item["campaign_id"] != "paper-preset-comparison-4m":
            continue
        median = item["median_observed_absolute_error_mHa"]
        value = f"{median:.3f}" if median is not None else "N/A"
        rows.append(
            f"{_latex_escape(item['variant_label'])} & {_latex_escape(_algorithm_label(item['algorithm']))} & {item['row_count']} & {item['observed_count']} & {item['eligible_count']} & {value} "
            + r"\\"
        )
    rows.append("\\end{tabular}")
    (output_dir / "preset_summary.tex").write_text("\n".join(rows) + "\n", encoding="utf-8")

    rows = [
        "\\begin{tabular}{@{}lrrrr@{}}",
        "Algorithm & Rows & Observed & Validated & Median observed error (mHa) \\\\",
        "\\hline",
    ]
    for item in stats["by_campaign_algorithm"]:
        if item["campaign_id"] != "paper-statevector-balanced-10m":
            continue
        median = item["median_observed_absolute_error_mHa"]
        value = f"{median:.3f}" if median is not None else "N/A"
        rows.append(
            f"{_latex_escape(_algorithm_label(item['algorithm']))} & {item['row_count']} & {item['observed_count']} & {item['eligible_count']} & {value} "
            + r"\\"
        )
    rows.append("\\end{tabular}")
    (output_dir / "statevector_summary.tex").write_text("\n".join(rows) + "\n", encoding="utf-8")


def _accuracy_runtime_panel_counts(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    counts: list[dict[str, Any]] = []
    for label, campaign_ids in ACCURACY_RUNTIME_PANELS:
        panel_rows = [row for row in rows if row.get("campaign_id") in campaign_ids]
        counts.append(
            {
                "panel": label,
                "row_count": len(panel_rows),
                "observed_count": sum(_observed(row) for row in panel_rows),
                "validated_count": sum(_observation_bucket(row) == "validated" for row in panel_rows),
                "diagnostic_count": sum(_observation_bucket(row) == "diagnostic" for row in panel_rows),
                "unvalidated_count": sum(_observation_bucket(row) == "unvalidated" for row in panel_rows),
                "incomplete_count": sum(_observation_bucket(row) == "incomplete" for row in panel_rows),
            }
        )
    return counts


def generate_report(input_dirs: list[Path], output_dir: Path, *, output_format: str = "both") -> dict[str, Any]:
    if output_format not in {"pdf", "png", "svg", "both"}:
        raise ValueError("output_format must be pdf, png, svg, or both")
    _apply_style()
    rows = _load_sources(input_dirs)
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    stats = build_statistics(rows)
    (output_dir / "statistics.json").write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    _write_records(rows, output_dir / "rows.csv")
    for name, records in (
        ("by_campaign_algorithm", stats["by_campaign_algorithm"]),
        ("by_campaign_variant", stats["by_campaign_variant"]),
        ("by_campaign_molecule_algorithm", stats["by_campaign_molecule_algorithm"]),
        ("by_campaign_seed", stats["by_campaign_seed"]),
        ("unvalidated_by_campaign_algorithm", stats["unvalidated_by_campaign_algorithm"]),
        ("field_presence", stats["field_presence"]),
    ):
        _write_records(records, output_dir / f"{name}.csv")
    _write_latex_fragments(stats, output_dir)

    plot_dir = output_dir / "plots"
    plot_files: list[str] = []
    for builder in (
        _plot_eligibility,
        _plot_preset,
        _plot_conditions,
        _plot_seed_sensitivity,
        _plot_heatmap,
        _plot_resource,
        _plot_accuracy_runtime,
        _plot_paths,
    ):
        plot_files.extend(builder(rows, plot_dir, output_format))
    manifest = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "row_count": len(rows),
        "eligible_row_count": stats["eligible_row_count"],
        "population_definitions": {
            "validated": "Rows marked benchmark_eligible; used for accuracy and runtime aggregates.",
            "observed": "Completed rows with finite absolute error and positive runtime; plotted for diagnostic context.",
            "diagnostic": "Finite observed rows marked projected_solve_is_diagnostic; excluded from validated aggregates.",
            "unvalidated": "Finite observed rows without the validated contract, including non-converged results; not counted as eligible or as missing.",
            "incomplete": "Rows without a finite completed estimate and runtime; not plotted as accuracy observations.",
        },
        "observation_counts": dict(sorted(Counter(_observation_bucket(row) for row in rows).items())),
        "unvalidated_reason_counts": stats["unvalidated_reason_counts"],
        "accuracy_runtime_panels": _accuracy_runtime_panel_counts(rows),
        "input_dirs": [str(path.expanduser().resolve()) for path in input_dirs],
        "plot_files": sorted(plot_files),
    }
    (output_dir / "report_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate paper statistics and figures from QSS benchmark exports.")
    parser.add_argument("input_dirs", nargs="+", type=Path, help="Campaign roots or export folders.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Paper report output directory.")
    parser.add_argument("--format", dest="output_format", choices=("pdf", "png", "svg", "both"), default="both")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = generate_report(args.input_dirs, args.output_dir, output_format=args.output_format)
    except (ExporterError, OSError, ValueError) as exc:
        print(f"error: {exc}")
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
