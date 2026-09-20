"""Plotting utilities for benchmark results visualization."""

from __future__ import annotations

from typing import Any, Literal, Optional, TYPE_CHECKING

import numpy as np
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for testing
import matplotlib.pyplot as plt

# Initialize pandas as None to avoid unbound warnings
pd: Any = None
HAS_PANDAS = False

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    pass

# Try to import the contract module (optional for backward compatibility)
prepare_error_plot_data: Any = None
HAS_CONTRACT = False

try:
    from quantum_diag.error_plot_contract import prepare_error_plot_data
    HAS_CONTRACT = True
except ImportError:
    pass

ErrorView = Literal["absolute", "signed"]


def _get_error_column_name(df: Any) -> str:
    """Determine which column to use for error values.

    Prefers error_value (from contract) over energy_error (legacy fallback).
    """
    if HAS_PANDAS and isinstance(df, pd.DataFrame):
        if "error_value" in df.columns:
            return "error_value"
    return "energy_error"


def _coerce_converged_value(value: Any) -> bool:
    """Normalize heterogeneous converged values to booleans."""
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}


def plot_energy_error_boxplot(
    df_or_rows: Any,
    output_path: str | None = None,
    error_view: ErrorView = "absolute",  # type: ignore[assignment]
) -> Any:
    """Plot energy error distribution by method as boxplot.

    Args:
        df_or_rows: pandas DataFrame, DataFrame wrapper, or list of dicts.
        output_path: If provided, save figure to this path.
        error_view: One of 'absolute' or 'signed'.
                   - If contract-prepared data (has error_value), this is informational.
                   - If raw data (no error_value), this controls derived y-values:
                     * 'absolute': uses energy_error column or derives from contract.
                     * 'signed': derives (final_energy - reference_energy).

    Returns:
        matplotlib figure object.
    """
    # Convert to list of rows if needed
    if isinstance(df_or_rows, list):
        rows = df_or_rows
        is_dataframe = False
    elif HAS_PANDAS and isinstance(df_or_rows, pd.DataFrame):
        rows = df_or_rows.to_dict("records")
        is_dataframe = True
    else:
        # Assume it's a DataFrame wrapper
        rows = df_or_rows.rows
        is_dataframe = False

    # Check if this is raw data (no error_value column)
    has_error_value = rows and isinstance(rows[0], dict) and "error_value" in rows[0]

    # If raw data, require contract module for signed mode
    if not has_error_value:
        if error_view == "signed":
            # Signed mode MUST have contract preparation to derive signed values
            if not HAS_CONTRACT:
                raise ValueError(
                    "signed error_view requires error_plot_contract module, but it is not available. "
                    "Install the quantum_diag package or ensure prepare_error_plot_data is importable."
                )
            if not HAS_PANDAS:
                raise ValueError(
                    "signed error_view requires pandas, but it is not available. "
                    "Install pandas to use signed error_view mode."
                )
            # Prepare using contract - will raise if required columns are missing
            try:
                prepared_df = prepare_error_plot_data(rows, error_view=error_view)
                rows = prepared_df.to_dict("records")
            except (KeyError, ValueError) as e:
                raise ValueError(
                    f"signed error_view requires final_energy and reference_energy columns, "
                    f"but contract preparation failed: {e}"
                ) from e
        elif error_view == "absolute" and HAS_CONTRACT and HAS_PANDAS:
            # For absolute mode, allow optional contract preparation (backward compatible)
            try:
                prepared_df = prepare_error_plot_data(rows, error_view=error_view)
                rows = prepared_df.to_dict("records")
            except (KeyError, ValueError):
                # For absolute mode, allow fallback for backward compatibility
                pass

    # Determine error column name (prefer contract-prepared error_value)
    # Check first row to see what column is available
    error_column = "energy_error"  # default
    if rows and isinstance(rows[0], dict) and "error_value" in rows[0]:
        error_column = "error_value"

    # Group by method
    method_data = {}
    for row in rows:
        error_val = row.get(error_column)
        if error_val is not None:
            method = row["method"]
            if method not in method_data:
                method_data[method] = []
            method_data[method].append(error_val)

    # Create plot
    fig, ax = plt.subplots(figsize=(10, 6))

    if method_data:
        methods = sorted(method_data.keys())
        data_to_plot = [method_data[m] for m in methods]
        ax.boxplot(data_to_plot, tick_labels=methods)
    else:
        ax.text(0.5, 0.5, "No data available", ha="center", va="center", transform=ax.transAxes)

    ax.set_xlabel("Method")
    ax.set_ylabel("Energy Error (Hartree)")
    ax.set_title("Energy Error Distribution by Method")
    ax.grid(True, alpha=0.3)

    if output_path:
        fig.savefig(output_path, dpi=100, bbox_inches="tight")
        plt.close(fig)

    return fig


def plot_runtime_bar(
    df_or_rows: Any,
    output_path: str | None = None,
) -> Any:
    """Plot mean runtime by method as bar chart.

    Args:
        df_or_rows: pandas DataFrame, DataFrame wrapper, or list of dicts.
        output_path: If provided, save figure to this path.

    Returns:
        matplotlib figure object.
    """
    # Convert to list of rows if needed
    if isinstance(df_or_rows, list):
        rows = df_or_rows
    elif HAS_PANDAS and isinstance(df_or_rows, pd.DataFrame):
        rows = df_or_rows.to_dict("records")
    else:
        # Assume it's a DataFrame wrapper
        rows = df_or_rows.rows

    # Group by method and compute mean runtime
    method_times = {}
    method_counts = {}

    for row in rows:
        if row.get("wall_time_seconds") is not None:
            method = row["method"]
            if method not in method_times:
                method_times[method] = 0.0
                method_counts[method] = 0
            method_times[method] += row["wall_time_seconds"]
            method_counts[method] += 1

    # Compute means
    method_means = {}
    for method in method_times:
        if method_counts[method] > 0:
            method_means[method] = method_times[method] / method_counts[method]

    # Create plot
    fig, ax = plt.subplots(figsize=(10, 6))

    if method_means:
        methods = sorted(method_means.keys())
        times = [method_means[m] for m in methods]
        ax.bar(methods, times, color="steelblue")
    else:
        ax.text(0.5, 0.5, "No data available", ha="center", va="center", transform=ax.transAxes)

    ax.set_xlabel("Method")
    ax.set_ylabel("Mean Runtime (seconds)")
    ax.set_title("Mean Runtime by Method")
    ax.grid(True, alpha=0.3, axis="y")

    if output_path:
        fig.savefig(output_path, dpi=100, bbox_inches="tight")
        plt.close(fig)

    return fig


def plot_convergence_rate(
    df_or_rows: Any,
    output_path: str | None = None,
) -> Any:
    """Plot convergence rate by method as bar chart.

    Args:
        df_or_rows: pandas DataFrame, DataFrame wrapper, or list of dicts.
        output_path: If provided, save figure to this path.

    Returns:
        matplotlib figure object.
    """
    # Convert to list of rows if needed
    if isinstance(df_or_rows, list):
        rows = df_or_rows
    elif HAS_PANDAS and isinstance(df_or_rows, pd.DataFrame):
        rows = df_or_rows.to_dict("records")
    else:
        # Assume it's a DataFrame wrapper
        rows = df_or_rows.rows

    # Group by method and compute convergence rate
    method_converged = {}
    method_counts = {}

    for row in rows:
        method = row["method"]
        if method not in method_converged:
            method_converged[method] = 0
            method_counts[method] = 0

        if row.get("converged") is not None:
            method_counts[method] += 1
            if _coerce_converged_value(row["converged"]):
                method_converged[method] += 1

    # Compute rates
    method_rates = {}
    for method in method_converged:
        if method_counts[method] > 0:
            method_rates[method] = (
                method_converged[method] / method_counts[method]
            )
        else:
            method_rates[method] = 0.0

    # Create plot
    fig, ax = plt.subplots(figsize=(10, 6))

    if method_rates:
        methods = sorted(method_rates.keys())
        rates = [method_rates[m] * 100 for m in methods]  # Convert to percentage
        ax.bar(methods, rates, color="seagreen")
        ax.set_ylim(0, 100)
    else:
        ax.text(0.5, 0.5, "No data available", ha="center", va="center", transform=ax.transAxes)

    ax.set_xlabel("Method")
    ax.set_ylabel("Convergence Rate (%)")
    ax.set_title("Convergence Rate by Method")
    ax.grid(True, alpha=0.3, axis="y")

    if output_path:
        fig.savefig(output_path, dpi=100, bbox_inches="tight")
        plt.close(fig)

    return fig


def plot_faceted_error_comparison(
    df_or_rows: Any,
    output_path: str | None = None,
    error_column: str = "energy_error",
) -> Any:
    """Plot per-molecule error comparison with faceted subplots.

    Creates a grid of subplots where each subplot shows error distribution for one molecule.
    Within each subplot, points are shown per method, allowing visual comparison of method
    performance per molecule.

    Phase 2: Multi-run, multi-molecule comparison where runs are explicit and molecules
    are separated for readability.

    Args:
        df_or_rows: pandas DataFrame, DataFrame wrapper, or list of dicts.
        output_path: If provided, save figure to this path.
        error_column: Name of column containing error values. Default "energy_error".

    Returns:
        matplotlib figure object with faceted subplots (one per molecule).
    """
    # Convert to list of rows if needed
    if isinstance(df_or_rows, list):
        rows = df_or_rows
    elif HAS_PANDAS and isinstance(df_or_rows, pd.DataFrame):
        rows = df_or_rows.to_dict("records")
    else:
        # Assume it's a DataFrame wrapper
        rows = df_or_rows.rows

    # Filter for successful runs only (excluding NaN/inf errors)
    successful_rows = [
        r for r in rows
        if (r.get("error") is None and
            r.get(error_column) is not None and
            not np.isnan(r.get(error_column)) and
            not np.isinf(r.get(error_column)))
    ]

    if not successful_rows:
        # Return empty figure if no data
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(0.5, 0.5, "No successful runs available",
                ha="center", va="center", transform=ax.transAxes)
        if output_path:
            fig.savefig(output_path, dpi=100, bbox_inches="tight")
        return fig

    # Extract unique molecules, maintaining order
    molecules_seen = []
    molecules_set = set()
    for row in successful_rows:
        mol = row.get("molecule")
        if mol and mol not in molecules_set:
            molecules_seen.append(mol)
            molecules_set.add(mol)

    molecules = sorted(molecules_seen)
    num_molecules = len(molecules)

    # Create faceted subplots (1 row × num_molecules columns, or adapt for readability)
    if num_molecules <= 2:
        ncols = num_molecules
        nrows = 1
    elif num_molecules <= 4:
        ncols = 2
        nrows = (num_molecules + 1) // 2
    else:
        ncols = 3
        nrows = (num_molecules + 2) // 3

    fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(6 * ncols, 5 * nrows))

    # Flatten axes for easy iteration (handle single subplot case)
    if num_molecules == 1:
        axes_flat = [axes]
    else:
        axes_flat = axes.flatten() if hasattr(axes, 'flatten') else [axes]

    # Get unique methods for consistent coloring
    methods_set = set()
    for row in successful_rows:
        methods_set.add(row.get("method"))
    methods = sorted(methods_set)

    # Color map for methods
    colors = plt.cm.tab10(range(len(methods)))
    method_colors = {method: colors[i] for i, method in enumerate(methods)}

    # Plot each molecule in its own subplot
    for idx, molecule in enumerate(molecules):
        ax = axes_flat[idx]

        # Filter rows for this molecule
        mol_rows = [r for r in successful_rows if r.get("molecule") == molecule]

        # Group by method for plotting
        method_data = {}
        for row in mol_rows:
            method = row.get("method")
            if method not in method_data:
                method_data[method] = []
            method_data[method].append(row.get(error_column))

        # Plot points for each method using strip plot (scatter with jitter)
        x_pos = 0
        x_ticks = []
        x_labels = []

        for method in sorted(method_data.keys()):
            errors = method_data[method]
            # Add jitter for visibility
            x_vals = [x_pos + np.random.normal(0, 0.02) for _ in errors]
            ax.scatter(x_vals, errors, alpha=0.6, s=50,
                      color=method_colors[method], label=method)
            x_ticks.append(x_pos)
            x_labels.append(method)
            x_pos += 1

        ax.set_xticks(x_ticks)
        ax.set_xticklabels(x_labels, rotation=45, ha="right")
        ax.set_ylabel("Energy Error (Hartree)")
        ax.set_title(f"Molecule: {molecule}")
        ax.grid(True, alpha=0.3, axis="y")

    # Hide unused subplots
    for idx in range(num_molecules, len(axes_flat)):
        axes_flat[idx].set_visible(False)

    fig.suptitle("Energy Error Comparison by Molecule", fontsize=14, y=1.00)
    fig.tight_layout()

    if output_path:
        fig.savefig(output_path, dpi=100, bbox_inches="tight")

    return fig


def plot_run_trajectories(
    df_or_rows: Any,
    output_path: str | None = None,
    error_column: str = "energy_error",
) -> Any:
    """Plot individual run trajectories across methods and molecules.

    Creates a plot with one line per unique seed (trajectory).
    Each line shows how error varies across different (method, molecule) combinations
    for a given seed.

    Phase 2 Revision: Trajectories grouped by seed to show multi-point lines
    representing how each seed performs across method-molecule combinations.

    Args:
        df_or_rows: pandas DataFrame, DataFrame wrapper, or list of dicts.
        output_path: If provided, save figure to this path.
        error_column: Name of column containing error values. Default "energy_error".

    Returns:
        matplotlib figure object with trajectories (lines) per seed.
    """
    # Convert to list of rows if needed
    if isinstance(df_or_rows, list):
        rows = df_or_rows
    elif HAS_PANDAS and isinstance(df_or_rows, pd.DataFrame):
        rows = df_or_rows.to_dict("records")
    else:
        # Assume it's a DataFrame wrapper
        rows = df_or_rows.rows

    # Filter for successful runs only (excluding NaN/inf errors)
    successful_rows = [
        r for r in rows
        if (r.get("error") is None and
            r.get(error_column) is not None and
            not np.isnan(r.get(error_column)) and
            not np.isinf(r.get(error_column)))
    ]

    if not successful_rows:
        # Return empty figure if no data
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.text(0.5, 0.5, "No successful runs available",
                ha="center", va="center", transform=ax.transAxes)
        if output_path:
            fig.savefig(output_path, dpi=100, bbox_inches="tight")
        return fig

    # Extract unique seeds and collect trajectory data
    # Grouping by seed: each seed has a trajectory across (method, molecule) combinations
    seed_trajectories = {}  # seed -> list of (method, molecule, error) tuples

    methods_seen = []
    methods_set = set()
    molecules_seen = []
    molecules_set = set()

    for row in successful_rows:
        method = row.get("method")
        molecule = row.get("molecule")
        seed = row.get("seed")
        error = row.get(error_column)

        if method and molecule and seed is not None:
            if method not in methods_set:
                methods_seen.append(method)
                methods_set.add(method)
            if molecule not in molecules_set:
                molecules_seen.append(molecule)
                molecules_set.add(molecule)

            if seed not in seed_trajectories:
                seed_trajectories[seed] = []
            seed_trajectories[seed].append((method, molecule, error))

    # Create a sorted list of method-molecule combinations for x-axis
    methods = sorted(methods_seen)
    molecules = sorted(molecules_seen)

    # Build x-positions for each (method, molecule) tuple
    x_positions = {}
    x_pos = 0
    x_ticks = []
    x_labels = []

    for method in methods:
        for molecule in molecules:
            x_positions[(method, molecule)] = x_pos
            x_ticks.append(x_pos)
            x_labels.append(f"{method}\n{molecule}")
            x_pos += 1

    # Create plot
    fig, ax = plt.subplots(figsize=(12, 6))

    # Plot each seed trajectory as a line
    colors = plt.cm.tab20(np.linspace(0, 1, len(seed_trajectories)))

    for seed_idx, (seed, points) in enumerate(sorted(seed_trajectories.items())):
        # Sort points by method-molecule position for proper line drawing
        points_sorted = sorted(points, key=lambda p: x_positions.get((p[0], p[1]), 0))

        x_vals = [x_positions[(p[0], p[1])] for p in points_sorted]
        y_vals = [p[2] for p in points_sorted]

        # Plot line for this seed trajectory
        ax.plot(x_vals, y_vals, marker='o', alpha=0.5, linewidth=1,
               color=colors[seed_idx % len(colors)],
               label=f"seed={seed}")

    ax.set_xticks(x_ticks)
    ax.set_xticklabels(x_labels, rotation=45, ha="right")
    ax.set_ylabel("Energy Error (Hartree)")
    ax.set_title("Run Trajectories Across Methods and Molecules")
    ax.grid(True, alpha=0.3)

    # Add legend (limit to avoid too many entries)
    handles, labels = ax.get_legend_handles_labels()
    if len(handles) <= 20:
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize='small')
    else:
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize='small',
                 ncol=(len(handles) + 19) // 20)  # Multi-column for many seeds

    fig.tight_layout()

    if output_path:
        fig.savefig(output_path, dpi=100, bbox_inches="tight")

    return fig


def plot_quantile_band_panel(
    df_or_rows: Any,
    output_path: str | None = None,
    error_column: str = "energy_error",
) -> Any:
    """Plot quantile bands (Q25, Q50, Q75) for error distribution per method-molecule.

    Phase 3: Advanced comparison panel showing stability/spread via quantile bands.
    Preserves run-level semantics by computing quantiles directly from raw runs.

    Args:
        df_or_rows: pandas DataFrame, DataFrame wrapper, or list of dicts.
        output_path: If provided, save figure to this path.
        error_column: Name of column containing error values. Default "energy_error".

    Returns:
        matplotlib figure object with quantile bands.
    """
    # Convert to list of rows if needed
    if isinstance(df_or_rows, list):
        rows = df_or_rows
    elif HAS_PANDAS and isinstance(df_or_rows, pd.DataFrame):
        rows = df_or_rows.to_dict("records")
    else:
        # Assume it's a DataFrame wrapper
        rows = df_or_rows.rows

    # Filter for successful runs only
    successful_rows = [
        r for r in rows
        if (r.get("error") is None and
            r.get(error_column) is not None and
            not np.isnan(r.get(error_column)) and
            not np.isinf(r.get(error_column)))
    ]

    if not successful_rows:
        # Return empty figure if no data
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(0.5, 0.5, "No successful runs available",
                ha="center", va="center", transform=ax.transAxes)
        if output_path:
            fig.savefig(output_path, dpi=100, bbox_inches="tight")
        return fig

    # Group runs by (method, molecule)
    method_molecule_data = {}
    method_molecules = []  # Maintain order
    method_molecules_set = set()

    for row in successful_rows:
        method = row.get("method")
        molecule = row.get("molecule")
        if method and molecule:
            key = (method, molecule)
            if key not in method_molecules_set:
                method_molecules.append(key)
                method_molecules_set.add(key)

            if key not in method_molecule_data:
                method_molecule_data[key] = []
            method_molecule_data[key].append(row.get(error_column))

    if not method_molecule_data:
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(0.5, 0.5, "No method-molecule pairs found",
                ha="center", va="center", transform=ax.transAxes)
        if output_path:
            fig.savefig(output_path, dpi=100, bbox_inches="tight")
        return fig

    # Compute quantiles for each method-molecule pair
    quantile_data = {}
    for key in method_molecules:
        errors = method_molecule_data[key]
        q25 = np.percentile(errors, 25)
        q50 = np.percentile(errors, 50)  # median
        q75 = np.percentile(errors, 75)
        quantile_data[key] = {'q25': q25, 'q50': q50, 'q75': q75, 'min': min(errors), 'max': max(errors)}

    # Create plot
    fig, ax = plt.subplots(figsize=(12, 6))

    x_positions = np.arange(len(method_molecules))

    # Extract quantile values
    q25_vals = [quantile_data[key]['q25'] for key in method_molecules]
    q50_vals = [quantile_data[key]['q50'] for key in method_molecules]
    q75_vals = [quantile_data[key]['q75'] for key in method_molecules]

    # Plot shaded region for Q25-Q75 band
    ax.fill_between(x_positions, q25_vals, q75_vals, alpha=0.3, label='Q25-Q75 band')

    # Plot median line
    ax.plot(x_positions, q50_vals, 'o-', color='darkblue', linewidth=2, markersize=8, label='Median (Q50)')

    # Set x-axis labels
    x_labels = [f"{method}\n{molecule}" for method, molecule in method_molecules]
    ax.set_xticks(x_positions)
    ax.set_xticklabels(x_labels, rotation=45, ha="right")

    ax.set_ylabel("Energy Error (Hartree)")
    ax.set_title("Quantile Bands (Stability/Spread) by Method and Molecule")
    ax.grid(True, alpha=0.3, axis="y")
    ax.legend()

    fig.tight_layout()

    if output_path:
        fig.savefig(output_path, dpi=100, bbox_inches="tight")

    return fig


def plot_tail_error_panel(
    df_or_rows: Any,
    output_path: str | None = None,
    error_column: str = "energy_error",
) -> Any:
    """Plot worst (tail) errors per method-molecule combination.

    Phase 3: Advanced comparison panel highlighting worst-case runs.
    Shows the maximum error (worst run) for each method-molecule pair.

    Args:
        df_or_rows: pandas DataFrame, DataFrame wrapper, or list of dicts.
        output_path: If provided, save figure to this path.
        error_column: Name of column containing error values. Default "energy_error".

    Returns:
        matplotlib figure object with tail errors emphasized.
    """
    # Convert to list of rows if needed
    if isinstance(df_or_rows, list):
        rows = df_or_rows
    elif HAS_PANDAS and isinstance(df_or_rows, pd.DataFrame):
        rows = df_or_rows.to_dict("records")
    else:
        # Assume it's a DataFrame wrapper
        rows = df_or_rows.rows

    # Filter for successful runs only
    successful_rows = [
        r for r in rows
        if (r.get("error") is None and
            r.get(error_column) is not None and
            not np.isnan(r.get(error_column)) and
            not np.isinf(r.get(error_column)))
    ]

    if not successful_rows:
        # Return empty figure if no data
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(0.5, 0.5, "No successful runs available",
                ha="center", va="center", transform=ax.transAxes)
        if output_path:
            fig.savefig(output_path, dpi=100, bbox_inches="tight")
        return fig

    # Group runs by (method, molecule) and find worst
    method_molecule_worst = {}
    method_molecules = []  # Maintain order
    method_molecules_set = set()

    for row in successful_rows:
        method = row.get("method")
        molecule = row.get("molecule")
        error = row.get(error_column)

        if method and molecule and error is not None:
            key = (method, molecule)
            if key not in method_molecules_set:
                method_molecules.append(key)
                method_molecules_set.add(key)

            if key not in method_molecule_worst:
                method_molecule_worst[key] = {'error': error, 'seed': row.get('seed')}
            elif error > method_molecule_worst[key]['error']:
                method_molecule_worst[key] = {'error': error, 'seed': row.get('seed')}

    if not method_molecule_worst:
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(0.5, 0.5, "No method-molecule pairs found",
                ha="center", va="center", transform=ax.transAxes)
        if output_path:
            fig.savefig(output_path, dpi=100, bbox_inches="tight")
        return fig

    # Create plot
    fig, ax = plt.subplots(figsize=(12, 6))

    x_positions = np.arange(len(method_molecules))

    # Extract worst error values
    worst_errors = [method_molecule_worst[key]['error'] for key in method_molecules]

    # Plot bars for worst errors
    colors = ['#d62728' if error > np.median(worst_errors) else '#1f77b4' for error in worst_errors]
    ax.bar(x_positions, worst_errors, color=colors, alpha=0.7)

    # Set x-axis labels
    x_labels = [f"{method}\n{molecule}" for method, molecule in method_molecules]
    ax.set_xticks(x_positions)
    ax.set_xticklabels(x_labels, rotation=45, ha="right")

    ax.set_ylabel("Worst Energy Error (Hartree)")
    ax.set_title("Tail Error Panel: Worst Run per Method and Molecule")
    ax.grid(True, alpha=0.3, axis="y")

    fig.tight_layout()

    if output_path:
        fig.savefig(output_path, dpi=100, bbox_inches="tight")

    return fig


def plot_convergence_overlay(
    df_or_rows: Any,
    output_path: str | None = None,
    error_column: str = "energy_error",
) -> Any:
    """Plot energy errors with convergence status overlay.

    Phase 3: Advanced comparison panel showing raw error values with
    convergence status as an overlay annotation (not replacement).

    Displays all runs with their error values, using color/marker to
    distinguish between converged and non-converged runs.

    Args:
        df_or_rows: pandas DataFrame, DataFrame wrapper, or list of dicts.
        output_path: If provided, save figure to this path.
        error_column: Name of column containing error values. Default "energy_error".

    Returns:
        matplotlib figure object with convergence overlay.
    """
    # Convert to list of rows if needed
    if isinstance(df_or_rows, list):
        rows = df_or_rows
    elif HAS_PANDAS and isinstance(df_or_rows, pd.DataFrame):
        rows = df_or_rows.to_dict("records")
    else:
        # Assume it's a DataFrame wrapper
        rows = df_or_rows.rows

    # Separate converged and non-converged runs (keep all, not just successful)
    converged_runs = []
    non_converged_runs = []

    for row in rows:
        if row.get(error_column) is not None and not np.isnan(row.get(error_column)) and not np.isinf(row.get(error_column)):
            if row.get("converged") is True:
                converged_runs.append(row)
            else:
                non_converged_runs.append(row)

    if not converged_runs and not non_converged_runs:
        # Return empty figure if no data
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(0.5, 0.5, "No data available",
                ha="center", va="center", transform=ax.transAxes)
        if output_path:
            fig.savefig(output_path, dpi=100, bbox_inches="tight")
        return fig

    # Group by (method, molecule)
    method_molecules = []
    method_molecules_set = set()

    for row in converged_runs + non_converged_runs:
        method = row.get("method")
        molecule = row.get("molecule")
        if method and molecule:
            key = (method, molecule)
            if key not in method_molecules_set:
                method_molecules.append(key)
                method_molecules_set.add(key)

    if not method_molecules:
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(0.5, 0.5, "No method-molecule pairs found",
                ha="center", va="center", transform=ax.transAxes)
        if output_path:
            fig.savefig(output_path, dpi=100, bbox_inches="tight")
        return fig

    # Create plot
    fig, ax = plt.subplots(figsize=(12, 6))

    x_positions = np.arange(len(method_molecules))

    # Plot converged runs (blue crosses)
    for idx, (method, molecule) in enumerate(method_molecules):
        for row in converged_runs:
            if row.get("method") == method and row.get("molecule") == molecule:
                error = row.get(error_column)
                # Add jitter for visibility
                x_val = idx + np.random.normal(0, 0.03)
                ax.scatter(x_val, error, marker='o', s=100, alpha=0.6,
                          color='green', label='Converged' if idx == 0 and len(ax.collections) == 0 else '')

        # Plot non-converged runs (red x's)
        for row in non_converged_runs:
            if row.get("method") == method and row.get("molecule") == molecule:
                error = row.get(error_column)
                # Add jitter for visibility
                x_val = idx + np.random.normal(0, 0.03)
                ax.scatter(x_val, error, marker='x', s=100, alpha=0.8,
                          color='red', label='Non-converged' if idx == 0 and len(ax.collections) == 1 else '')

    # Set x-axis labels
    x_labels = [f"{method}\n{molecule}" for method, molecule in method_molecules]
    ax.set_xticks(x_positions)
    ax.set_xticklabels(x_labels, rotation=45, ha="right")

    ax.set_ylabel("Energy Error (Hartree)")
    ax.set_title("Convergence Overlay: Error Values with Convergence Status")
    ax.grid(True, alpha=0.3, axis="y")

    # Add legend
    if converged_runs and non_converged_runs:
        ax.legend(['Converged', 'Non-converged'])
    elif non_converged_runs:
        ax.legend(['Non-converged'])
    elif converged_runs:
        ax.legend(['Converged'])

    fig.tight_layout()

    if output_path:
        fig.savefig(output_path, dpi=100, bbox_inches="tight")

    return fig
