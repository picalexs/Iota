"""Convergence gate for the SKQD sample-union path.

The published SKQD algorithm (Yu, Robledo-Moreno et al., arXiv:2501.09702,
Theorem 1) approximates the ground state once all ``L`` important bitstrings
have been sampled into the subspace. In a sample-based run there is no explicit
residual to test, so the practical convergence signal is *subspace saturation*:
adding the final Krylov state's samples no longer expands the valid-sector
determinant union, and the classical diagonalization used that entire union
(no selected-CI cap dropped determinants).

This module derives that verdict from the prefix diagnostics and the
selected-CI summary that the workflow already produces, so the sample-union
result stops reporting a hardcoded ``converged=False``.
"""

from __future__ import annotations

from typing import Any

_FULL_SECTOR_FRACTION = 1.0


def evaluate_sample_union_convergence(
    *,
    prefix_summaries: list[dict[str, Any]],
    selected_ci_summary: dict[str, Any],
) -> dict[str, Any]:
    """Return a subspace-saturation convergence verdict for a sample union.

    ``converged`` is True when the sampled determinant union has saturated and
    the diagonalization spans that entire union, or when the union already
    covers the full CI sector. The returned diagnostics explain the verdict.
    """
    krylov_states = len(prefix_summaries)
    postselected = int(selected_ci_summary.get("postselected_union_determinants", 0))
    selected = int(selected_ci_summary.get("selected_union_determinants", 0))
    selected_ci_fraction = float(selected_ci_summary.get("selected_ci_fraction", 0.0))

    # The selected-CI cap dropped nothing: the solve used the whole postselected
    # union, so the reported energy is exact on the sampled subspace.
    complete_solve = postselected > 0 and selected >= postselected

    # The sampled union already spans the entire CI sector for this problem.
    full_sector = selected_ci_fraction >= _FULL_SECTOR_FRACTION

    saturated = False
    growth_delta: int | None = None
    if krylov_states >= 2:
        final_space = int(prefix_summaries[-1].get("selected_space_size", 0))
        previous_space = int(prefix_summaries[-2].get("selected_space_size", 0))
        growth_delta = final_space - previous_space
        saturated = final_space > 0 and growth_delta == 0

    converged = bool(full_sector or (saturated and complete_solve))
    if converged:
        status = "subspace_saturated" if not full_sector else "full_sector_recovered"
    elif krylov_states < 2 and not full_sector:
        status = "sampling_convergence_not_established_single_state"
    else:
        status = "sampling_convergence_not_established"

    return {
        "converged": converged,
        "convergence_status": status,
        "subspace_saturated": bool(saturated),
        "complete_selected_ci_solve": bool(complete_solve),
        "full_sector_recovered": bool(full_sector),
        "final_prefix_growth_delta": growth_delta,
        "krylov_states": krylov_states,
        "postselected_union_determinants": postselected,
        "selected_union_determinants": selected,
        "selected_ci_fraction": selected_ci_fraction,
        "convergence_criterion": (
            "krylov_subspace_saturation_and_complete_selected_ci_solve"
        ),
    }


__all__ = ["evaluate_sample_union_convergence"]
