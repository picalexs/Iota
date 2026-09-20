"""Results aggregation and export utilities."""

from __future__ import annotations

import csv
import json
from typing import Any, TYPE_CHECKING

# Initialize pandas as None to avoid unbound warnings
pd: Any = None
HAS_PANDAS = False

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    pass


def to_dataframe(rows: list[dict[str, Any]]) -> Any:
    """Convert raw rows to dataframe.

    Uses pandas if available, otherwise returns a simplified wrapper.

    Args:
        rows: List of dicts with benchmark results.

    Returns:
        pandas DataFrame or simple wrapper object with compatible interface.
    """
    if HAS_PANDAS:
        return pd.DataFrame(rows)
    else:
        # Fallback: return a simple wrapper
        return SimpleDataFrame(rows)


def summarize_by_method(df: Any) -> Any:
    """Summarize metrics grouped by method.

    Args:
        df: DataFrame (pandas or wrapper).

    Returns:
        Summary DataFrame with mean/std/min/max for energy_error and wall_time,
        plus convergence_rate per method.
    """
    if HAS_PANDAS:
        # Pandas version
        summary_data = []

        for method in df["method"].unique():
            method_df = df[df["method"] == method]

            # Filter out None/NaN values for numerical calculations
            energy_errors = method_df["energy_error"].dropna()
            wall_times = method_df["wall_time_seconds"].dropna()
            converged = method_df["converged"].sum()

            convergence_rate = (
                converged / len(method_df) if len(method_df) > 0 else 0.0
            )

            summary_data.append({
                "method": method,
                "mean_energy_error": energy_errors.mean() if len(energy_errors) > 0 else None,
                "std_energy_error": energy_errors.std() if len(energy_errors) > 0 else None,
                "min_energy_error": energy_errors.min() if len(energy_errors) > 0 else None,
                "max_energy_error": energy_errors.max() if len(energy_errors) > 0 else None,
                "mean_wall_time_seconds": wall_times.mean() if len(wall_times) > 0 else None,
                "std_wall_time_seconds": wall_times.std() if len(wall_times) > 0 else None,
                "min_wall_time_seconds": wall_times.min() if len(wall_times) > 0 else None,
                "max_wall_time_seconds": wall_times.max() if len(wall_times) > 0 else None,
                "convergence_rate": convergence_rate,
            })

        return pd.DataFrame(summary_data)
    else:
        # Fallback version
        return _summarize_by_method_fallback(df)


def _summarize_by_method_fallback(df: SimpleDataFrame) -> SimpleDataFrame:
    """Fallback summarize_by_method for non-pandas."""
    rows = df.rows
    methods = set(row["method"] for row in rows)

    summary_data = []

    for method in methods:
        method_rows = [row for row in rows if row["method"] == method]

        energy_errors = [
            row["energy_error"]
            for row in method_rows
            if row.get("energy_error") is not None
        ]
        wall_times = [
            row["wall_time_seconds"]
            for row in method_rows
            if row.get("wall_time_seconds") is not None
        ]
        converged_count = sum(1 for row in method_rows if row.get("converged"))

        convergence_rate = (
            converged_count / len(method_rows) if len(method_rows) > 0 else 0.0
        )

        def mean_val(values):
            return sum(values) / len(values) if len(values) > 0 else None

        def std_val(values):
            if len(values) <= 1:
                return None
            m = mean_val(values)
            if m is None:
                return None
            variance = sum((x - m) ** 2 for x in values) / len(values)
            return variance ** 0.5

        summary_data.append({
            "method": method,
            "mean_energy_error": mean_val(energy_errors),
            "std_energy_error": std_val(energy_errors),
            "min_energy_error": min(energy_errors) if energy_errors else None,
            "max_energy_error": max(energy_errors) if energy_errors else None,
            "mean_wall_time_seconds": mean_val(wall_times),
            "std_wall_time_seconds": std_val(wall_times),
            "min_wall_time_seconds": min(wall_times) if wall_times else None,
            "max_wall_time_seconds": max(wall_times) if wall_times else None,
            "convergence_rate": convergence_rate,
        })

    return SimpleDataFrame(summary_data)


def summarize_by_molecule(df: Any) -> Any:
    """Summarize metrics grouped by molecule.

    Args:
        df: DataFrame (pandas or wrapper).

    Returns:
        Summary DataFrame.
    """
    if HAS_PANDAS:
        summary_data = []

        for molecule in df["molecule"].unique():
            mol_df = df[df["molecule"] == molecule]

            energy_errors = mol_df["energy_error"].dropna()
            wall_times = mol_df["wall_time_seconds"].dropna()
            converged = mol_df["converged"].sum()

            convergence_rate = (
                converged / len(mol_df) if len(mol_df) > 0 else 0.0
            )

            summary_data.append({
                "molecule": molecule,
                "mean_energy_error": energy_errors.mean() if len(energy_errors) > 0 else None,
                "std_energy_error": energy_errors.std() if len(energy_errors) > 0 else None,
                "mean_wall_time_seconds": wall_times.mean() if len(wall_times) > 0 else None,
                "convergence_rate": convergence_rate,
            })

        return pd.DataFrame(summary_data)
    else:
        return _summarize_by_molecule_fallback(df)


def _summarize_by_molecule_fallback(df: SimpleDataFrame) -> SimpleDataFrame:
    """Fallback summarize_by_molecule for non-pandas."""
    rows = df.rows
    molecules = set(row["molecule"] for row in rows)

    summary_data = []

    for molecule in molecules:
        mol_rows = [row for row in rows if row["molecule"] == molecule]

        energy_errors = [
            row["energy_error"]
            for row in mol_rows
            if row.get("energy_error") is not None
        ]
        wall_times = [
            row["wall_time_seconds"]
            for row in mol_rows
            if row.get("wall_time_seconds") is not None
        ]
        converged_count = sum(1 for row in mol_rows if row.get("converged"))

        convergence_rate = (
            converged_count / len(mol_rows) if len(mol_rows) > 0 else 0.0
        )

        def mean_val(values):
            return sum(values) / len(values) if len(values) > 0 else None

        summary_data.append({
            "molecule": molecule,
            "mean_energy_error": mean_val(energy_errors),
            "std_energy_error": None,
            "mean_wall_time_seconds": mean_val(wall_times),
            "convergence_rate": convergence_rate,
        })

    return SimpleDataFrame(summary_data)


def best_method_per_molecule(df: Any) -> Any:
    """Select best method per molecule by lowest mean energy error.

    Args:
        df: DataFrame (pandas or wrapper).

    Returns:
        DataFrame with one row per molecule showing best method.
    """
    if HAS_PANDAS:
        # Compute mean energy error per method and molecule
        grouped = df.groupby(["molecule", "method"])["energy_error"].mean().reset_index()
        grouped.rename(columns={"energy_error": "mean_energy_error"}, inplace=True)

        # Select best (minimum) per molecule
        best = grouped.loc[grouped.groupby("molecule")["mean_energy_error"].idxmin()]
        return best
    else:
        return _best_method_per_molecule_fallback(df)


def _best_method_per_molecule_fallback(df: SimpleDataFrame) -> SimpleDataFrame:
    """Fallback best_method_per_molecule for non-pandas."""
    rows = df.rows
    molecules = set(row["molecule"] for row in rows)

    best_rows = []

    for molecule in molecules:
        mol_rows = [row for row in rows if row["molecule"] == molecule]

        # Group by method and compute mean energy error
        method_errors = {}
        for row in mol_rows:
            method = row["method"]
            energy_error = row.get("energy_error")
            if energy_error is not None:
                if method not in method_errors:
                    method_errors[method] = []
                method_errors[method].append(energy_error)

        # Find best method (lowest mean error)
        best_method = None
        best_mean_error = None

        for method, errors in method_errors.items():
            mean_error = sum(errors) / len(errors)
            if best_mean_error is None or mean_error < best_mean_error:
                best_method = method
                best_mean_error = mean_error

        # Find a representative row for this method/molecule combo
        for row in mol_rows:
            if row["method"] == best_method:
                best_rows.append(row)
                break

    return SimpleDataFrame(best_rows)


def export_csv(df: Any, path: str) -> None:
    """Export dataframe to CSV file.

    Args:
        df: DataFrame (pandas or wrapper).
        path: File path to write to.
    """
    if HAS_PANDAS:
        df.to_csv(path, index=False)
    else:
        _export_csv_fallback(df, path)


def _export_csv_fallback(df: SimpleDataFrame, path: str) -> None:
    """Fallback CSV export for non-pandas."""
    rows = df.rows

    if not rows:
        return

    fieldnames = list(rows[0].keys())

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def export_json(rows: list[dict[str, Any]], path: str) -> None:
    """Export rows to JSON file.

    Args:
        rows: List of dicts.
        path: File path to write to.
    """
    with open(path, "w") as f:
        json.dump(rows, f, indent=2, default=str)


class SimpleDataFrame:
    """Simple DataFrame wrapper for non-pandas fallback."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        """Initialize with rows.

        Args:
            rows: List of dicts.
        """
        self.rows = rows

    @property
    def columns(self) -> list[str]:
        """Get column names."""
        if self.rows:
            return list(self.rows[0].keys())
        return []

    def __len__(self) -> int:
        """Get number of rows."""
        return len(self.rows)

    def __getitem__(self, key):
        """Support dict-like indexing."""
        if isinstance(key, str):
            # Column access
            return [row.get(key) for row in self.rows]
        else:
            # Row access
            return self.rows[key]

    def iloc(self, index: int) -> dict[str, Any]:
        """Support iloc-like indexing.

        Args:
            index: Row index.

        Returns:
            Row dict at index.
        """
        return self.rows[index]
