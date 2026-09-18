"""Ownership checks for the extracted SQD selected-CI helpers."""

from __future__ import annotations

import numpy as np

from worker.chemistry import sqd_solver
from worker.chemistry.algorithms.sqd import selection as sqd_selection


def test_sqd_solver_keeps_legacy_selection_imports_as_compatibility_aliases() -> None:
    assert sqd_solver._selected_ci_strings_from_bitstrings is (
        sqd_selection.selected_ci_strings_from_bitstrings
    )
    assert sqd_solver._resolve_selected_ci_limits is sqd_selection.resolve_selected_ci_limits
    assert sqd_solver._extract_carryover_ci_strings is sqd_selection.extract_carryover_ci_strings
    assert sqd_solver._postselection_weight is sqd_selection.postselection_weight
    assert sqd_solver._selected_ci_fraction is sqd_selection.selected_ci_fraction


def test_selected_ci_fraction_handles_empty_and_capped_sectors() -> None:
    assert sqd_selection.selected_ci_fraction(0, full_sci_dimension=100) == 0.0
    assert sqd_selection.selected_ci_fraction(25, full_sci_dimension=100) == 0.25
    assert sqd_selection.selected_ci_fraction(25, full_sci_dimension=0) == 25.0


def test_default_selected_ci_limit_stays_partial_for_nontrivial_sector() -> None:
    limits, summary = sqd_selection.resolve_selected_ci_limits(
        None,
        norb=2,
        num_elec_a=1,
        num_elec_b=1,
    )

    assert limits == (1, 1)
    assert summary["max_dim_source"] == "default_partial_sector_cap"
    assert summary["cap_active"] is True
    assert summary["full_sector_requested"] is False


def test_full_selected_ci_requires_explicit_mode() -> None:
    limits, summary = sqd_selection.resolve_selected_ci_limits(
        "full",
        norb=2,
        num_elec_a=1,
        num_elec_b=1,
    )

    assert limits == (2, 2)
    assert summary["max_dim_source"] == "explicit_full_sector"
    assert summary["full_sector_requested"] is True
    assert summary["cap_active"] is False


def test_closed_shell_selection_uses_one_shared_spin_pool() -> None:
    bitstrings = np.asarray(
        [
            [False, True, True, False],
            [True, False, True, False],
        ],
        dtype=bool,
    )

    (alpha, beta), summary = sqd_selection.selected_ci_strings_from_bitstrings(
        bitstrings,
        np.asarray([0.25, 0.75]),
        max_dim=(2, 2),
        open_shell=False,
    )

    assert alpha.tolist() == [1, 2]
    assert beta.tolist() == [1, 2]
    assert summary["selection_pool_mode"] == "shared_spin_pool"


def test_open_shell_selection_keeps_independent_spin_pools() -> None:
    bitstrings = np.asarray(
        [
            [False, True, True, False],
            [True, False, False, True],
        ],
        dtype=bool,
    )

    (alpha, beta), summary = sqd_selection.selected_ci_strings_from_bitstrings(
        bitstrings,
        np.asarray([0.25, 0.75]),
        max_dim=(2, 2),
        open_shell=True,
    )

    assert alpha.tolist() == [1, 2]
    assert beta.tolist() == [1, 2]
    assert summary["selection_pool_mode"] == "independent_spin_pools"
