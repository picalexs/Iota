"""Error plotting contract implementation and enforcement.

This module enforces the Phase 1 error plotting contract:
- Each plotted point corresponds to exactly one raw run row (no aggregation)
- Explicit error view selector (absolute or signed)
- Consistent derivation between absolute and signed error views
- Graceful handling of empty/failed-only rows
"""

from __future__ import annotations

from typing import Any, Literal, Optional, Sequence, Mapping, TYPE_CHECKING

import pandas as pd
import numpy as np

if TYPE_CHECKING:
    from typing import TypeAlias

ErrorView: TypeAlias = Literal["absolute", "signed"]


def validate_error_plot_contract(
    df: pd.DataFrame,
    error_view: ErrorView = "absolute",
) -> pd.DataFrame:
    """Validate and prepare data for error plotting per contract.

    Contract enforcement:
    1. Each row in returned DataFrame = one raw run (no aggregation)
    2. Only successful runs included (error=None, energy_error=notNaN)
    3. Explicit error view column is derived consistently
    4. Gracefully handles empty/failed-only data

    Args:
        df: Input DataFrame with columns: method, energy_error, final_energy (for signed),
            reference_energy (for signed), and optional 'error' column marking failures.
        error_view: One of 'absolute' or 'signed'.
                   - 'absolute': uses energy_error column (pre-computed |final - reference|)
                   - 'signed': derives (final_energy - reference_energy)

    Returns:
        Validated DataFrame with processed error column. Each row = one raw run.

    Raises:
        ValueError: If error_view is not recognized
        KeyError: If required columns are missing for the requested error_view
    """
    if error_view not in ("absolute", "signed"):
        raise ValueError(f"error_view must be 'absolute' or 'signed', got {error_view}")

    # Filter for successful runs per error_view mode
    # Make a copy to avoid modifying the original
    plot_df = df.copy()

    # Handle empty DataFrame gracefully
    if len(plot_df) == 0:
        return plot_df

    # Handle missing 'error' column gracefully (assume no error = success)
    if "error" not in plot_df.columns:
        plot_df["error"] = None

    # Apply mode-aware filtering
    if error_view == "absolute":
        # For absolute mode: require non-null energy_error
        if "energy_error" not in plot_df.columns:
            raise KeyError("energy_error column required for absolute error view")
        filtered = plot_df[
            (plot_df["error"].isna()) & (plot_df["energy_error"].notna())
        ]
    elif error_view == "signed":
        # For signed mode: require non-null final_energy and reference_energy
        # Don't filter on energy_error since we derive the signed value
        filtered = plot_df[
            (plot_df["error"].isna()) &
            (plot_df["final_energy"].notna()) &
            (plot_df["reference_energy"].notna())
        ]
    else:
        # Should not reach here due to earlier validation
        raise ValueError(f"error_view must be 'absolute' or 'signed', got {error_view}")

    plot_df = filtered.copy()

    # If data is empty after filtering, return as-is (graceful empty handling)
    if len(plot_df) == 0:
        return plot_df

    # Enforce error view consistency
    if error_view == "absolute":
        # Verify energy_error exists
        if "energy_error" not in plot_df.columns:
            raise KeyError("energy_error column required for absolute error view")

        # Use pre-computed absolute error
        plot_df["error_value"] = plot_df["energy_error"]

        # Validate: all errors should be non-negative
        if (plot_df["error_value"] < 0).any():
            raise ValueError(
                "Absolute error values must be non-negative. "
                "This indicates data corruption or pre-computation error."
            )

    elif error_view == "signed":
        # Verify required columns
        required = {"final_energy", "reference_energy"}
        if not required.issubset(plot_df.columns):
            raise KeyError(
                f"signed error view requires {required}, "
                f"but got columns: {set(plot_df.columns)}"
            )

        # Derive signed error
        plot_df["error_value"] = plot_df["final_energy"] - plot_df["reference_energy"]

        # Validate consistency: |signed_error| should match |energy_error| if present and non-null
        if "energy_error" in plot_df.columns:
            # Only check rows where energy_error is non-null (it's optional in signed mode)
            has_energy_error = plot_df["energy_error"].notna()
            if has_energy_error.any():
                abs_signed = np.abs(plot_df.loc[has_energy_error, "error_value"])
                energy_error_vals = plot_df.loc[has_energy_error, "energy_error"]
                # Use isclose for floating point comparison
                if not np.allclose(abs_signed, energy_error_vals, rtol=1e-10):
                    raise ValueError(
                        "Signed error consistency violated: "
                        "|final_energy - reference_energy| != energy_error"
                    )

    return plot_df


def get_error_value(
    row: dict[str, Any] | pd.Series,  # type: ignore[name-defined]
    error_view: ErrorView = "absolute",
) -> float:
    """Extract error value from a row according to specified view.

    Args:
        row: Dictionary or Series with row data
        error_view: One of 'absolute' or 'signed'

    Returns:
        Error value in the requested view

    Raises:
        ValueError: If error_view is invalid
        KeyError: If required columns are missing
    """
    if error_view == "absolute":
        if "energy_error" not in row:
            raise KeyError("energy_error column required for absolute view")
        return float(row["energy_error"])  # type: ignore[index]

    elif error_view == "signed":
        required = {"final_energy", "reference_energy"}
        row_keys = set(row.keys() if isinstance(row, dict) else row.index)  # type: ignore[union-attr]
        if required > row_keys:
            raise KeyError(f"signed view requires {required}")
        return float(row["final_energy"] - row["reference_energy"])  # type: ignore[index]

    else:
        raise ValueError(f"error_view must be 'absolute' or 'signed', got {error_view}")


def prepare_error_plot_data(
    rows: Sequence[Mapping[str, Any]] | pd.DataFrame,
    error_view: ErrorView = "absolute",
) -> pd.DataFrame:
    """Prepare raw list of rows or DataFrame for error plotting.

    Handles conversion and validation according to error plotting contract.

    Args:
        rows: Sequence of mappings (dict-like objects) or pandas DataFrame
        error_view: 'absolute' or 'signed'

    Returns:
        Validated DataFrame ready for plotting
    """
    # Convert to DataFrame if needed
    if isinstance(rows, pd.DataFrame):
        df = rows.copy()
    else:
        df = pd.DataFrame(list(rows))

    # Apply contract validation
    return validate_error_plot_contract(df, error_view=error_view)
