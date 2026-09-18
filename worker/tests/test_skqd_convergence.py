"""Tests for the SKQD sample-union subspace-saturation convergence gate."""

from __future__ import annotations

from worker.chemistry.algorithms.skqd.convergence import evaluate_sample_union_convergence


def _prefix(sizes: list[int]) -> list[dict[str, object]]:
    return [
        {"krylov_dimension": index + 1, "selected_space_size": size}
        for index, size in enumerate(sizes)
    ]


def test_gate_reports_subspace_saturation_without_scientific_convergence() -> None:
    verdict = evaluate_sample_union_convergence(
        prefix_summaries=_prefix([4, 6, 6]),
        selected_ci_summary={
            "postselected_union_determinants": 6,
            "selected_union_determinants": 6,
            "selected_ci_fraction": 0.5,
        },
    )

    assert verdict["converged"] is False
    assert verdict["convergence_status"] == "subspace_saturated"
    assert verdict["subspace_saturated"] is True
    assert verdict["complete_selected_ci_solve"] is True
    assert verdict["full_sector_recovered"] is False
    assert verdict["final_prefix_growth_delta"] == 0


def test_gate_reports_not_converged_when_union_still_growing() -> None:
    verdict = evaluate_sample_union_convergence(
        prefix_summaries=_prefix([4, 6, 9]),
        selected_ci_summary={
            "postselected_union_determinants": 9,
            "selected_union_determinants": 9,
            "selected_ci_fraction": 0.4,
        },
    )

    assert verdict["converged"] is False
    assert verdict["convergence_status"] == "sampling_convergence_not_established"
    assert verdict["subspace_saturated"] is False
    assert verdict["final_prefix_growth_delta"] == 3


def test_gate_requires_complete_solve_even_when_saturated() -> None:
    verdict = evaluate_sample_union_convergence(
        prefix_summaries=_prefix([6, 6]),
        selected_ci_summary={
            "postselected_union_determinants": 6,
            "selected_union_determinants": 4,  # selected-CI cap dropped determinants
            "selected_ci_fraction": 0.5,
        },
    )

    assert verdict["converged"] is False
    assert verdict["complete_selected_ci_solve"] is False


def test_gate_reports_converged_when_full_sector_recovered() -> None:
    verdict = evaluate_sample_union_convergence(
        prefix_summaries=_prefix([3, 4]),
        selected_ci_summary={
            "postselected_union_determinants": 4,
            "selected_union_determinants": 4,
            "selected_ci_fraction": 1.0,
        },
    )

    assert verdict["converged"] is True
    assert verdict["convergence_status"] == "full_sector_recovered"
    assert verdict["full_sector_recovered"] is True


def test_gate_single_state_cannot_establish_saturation_from_growth() -> None:
    verdict = evaluate_sample_union_convergence(
        prefix_summaries=_prefix([5]),
        selected_ci_summary={
            "postselected_union_determinants": 5,
            "selected_union_determinants": 5,
            "selected_ci_fraction": 0.5,
        },
    )

    assert verdict["converged"] is False
    assert verdict["convergence_status"] == "sampling_convergence_not_established_single_state"
    assert verdict["final_prefix_growth_delta"] is None


def test_gate_single_state_full_sector_still_converges() -> None:
    verdict = evaluate_sample_union_convergence(
        prefix_summaries=_prefix([2]),
        selected_ci_summary={
            "postselected_union_determinants": 2,
            "selected_union_determinants": 2,
            "selected_ci_fraction": 1.0,
        },
    )

    assert verdict["converged"] is True
    assert verdict["convergence_status"] == "full_sector_recovered"
