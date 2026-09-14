"""Tests for read-only SKQD Krylov-prefix diagnostics."""

import numpy as np

from worker.chemistry.algorithms.skqd.diagnostics import build_skqd_prefix_summaries
from worker.chemistry.algorithms.skqd.sampling import SKQDKrylovSample, merge_krylov_samples


def test_prefix_summaries_keep_d_one_sample_union_counts() -> None:
    samples = np.asarray(
        [[False, True, False, True], [True, False, False, True]],
        dtype=bool,
    )
    sample_union = merge_krylov_samples([SKQDKrylovSample(0, 0.0, samples)])

    summaries = build_skqd_prefix_summaries(sample_union, num_elec_a=1, num_elec_b=1)

    assert summaries == [
        {
            "krylov_dimension": 1,
            "krylov_index": 0,
            "sample_count": 2,
            "union_determinant_count": 2,
            "valid_sector_mass": 1.0,
            "selected_space_size": 2,
            "selected_space_size_source": (
                "unique_raw_valid_sector_determinants_before_recovery_and_ci_cap"
            ),
        }
    ]


def test_prefix_summaries_show_multi_state_support_growth() -> None:
    first = np.asarray([[False, True, False, True]], dtype=bool)
    second = np.asarray(
        [[False, True, False, True], [True, False, False, True]],
        dtype=bool,
    )
    sample_union = merge_krylov_samples(
        [SKQDKrylovSample(0, 0.0, first), SKQDKrylovSample(1, 0.2, second)]
    )

    summaries = build_skqd_prefix_summaries(sample_union, num_elec_a=1, num_elec_b=1)

    assert [summary["krylov_dimension"] for summary in summaries] == [1, 2]
    assert [summary["sample_count"] for summary in summaries] == [1, 3]
    assert [summary["union_determinant_count"] for summary in summaries] == [1, 2]
    assert [summary["selected_space_size"] for summary in summaries] == [1, 2]
    assert [summary["valid_sector_mass"] for summary in summaries] == [1.0, 1.0]
