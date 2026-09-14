"""Tests for SKQD's ordinary selected-CI determinant-union solve."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from worker.chemistry.algorithms.skqd.diagnostics import build_skqd_prefix_summaries
from worker.chemistry.algorithms.skqd.sampling import SKQDKrylovSample, SKQDSampleUnion
from worker.chemistry.algorithms.skqd.selected_ci import solve_sample_union_selected_ci
from worker.chemistry.algorithms.sqd.config import resolve_sqd_options
from worker.chemistry.algorithms.sqd.recovery import run_selected_ci_batches


def _options() -> object:
    hamiltonian = type(
        "Hamiltonian",
        (),
        {
            "num_spatial_orbitals": 2,
            "num_electrons_alpha": 1,
            "num_electrons_beta": 1,
            "one_body_tensor": np.zeros((2, 2)),
            "two_body_tensor": np.zeros((2, 2, 2, 2)),
            "constant": -0.25,
        },
    )()
    return resolve_sqd_options(
        {"algorithm": "sqd", "max_dim": "full"},
        hamiltonian,
    )


def test_selected_ci_solves_the_actual_union_without_cartesian_completion() -> None:
    sample = np.asarray(
        [
            [False, True, False, True],
            [True, False, False, True],
        ],
        dtype=bool,
    )
    sample_union = SKQDSampleUnion(
        samples_by_state=(
            SKQDKrylovSample(0, 0.0, sample[:1]),
            SKQDKrylovSample(1, 0.2, sample[1:]),
        ),
        merged_bitstring_matrix=sample,
        merged_probabilities=np.asarray([0.5, 0.5]),
        merged_counts=np.asarray([1, 1]),
        provenance=(),
    )

    def postselect(bits, probabilities, **kwargs):
        del kwargs
        return bits, probabilities

    outcome = solve_sample_union_selected_ci(
        sample_union,
        options=_options(),  # type: ignore[arg-type]
        rng=np.random.default_rng(1),
        recover_configurations=None,
        postselect_by_hamming_right_and_left=postselect,
        solve_fermion=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("SKQD must not use the Cartesian-product SQD solver")
        ),
    )

    assert outcome.energy == -0.25
    assert outcome.summary["sampled_krylov_states"] == 2
    assert outcome.summary["sampled_union_determinants"] == 2
    assert outcome.summary["selected_union_determinants"] == 2
    assert outcome.summary["sci_dimension"] == 2
    assert outcome.summary["solve_type"] == "ordinary_selected_ci"


def test_selected_ci_marks_the_d_one_sqd_reduction() -> None:
    sample = np.asarray([[False, True, False, True]], dtype=bool)
    sample_union = SKQDSampleUnion(
        samples_by_state=(SKQDKrylovSample(0, 0.0, sample),),
        merged_bitstring_matrix=sample,
        merged_probabilities=np.asarray([1.0]),
        merged_counts=np.asarray([4]),
        provenance=(),
    )

    outcome = solve_sample_union_selected_ci(
        sample_union,
        options=_options(),  # type: ignore[arg-type]
        rng=np.random.default_rng(1),
        recover_configurations=None,
        postselect_by_hamming_right_and_left=lambda bits, probabilities, **_kwargs: (
            bits,
            probabilities,
        ),
        solve_fermion=lambda *_args, **_kwargs: (
            -1.0,
            None,
            (np.asarray([0.5, 0.5]), np.asarray([0.5, 0.5])),
            0.0,
        ),
    )

    assert outcome.summary["limiting_case"] == "d=1_sqd_equivalent"
    prefix = build_skqd_prefix_summaries(
        sample_union,
        num_elec_a=1,
        num_elec_b=1,
    )
    assert prefix[0]["krylov_dimension"] == 1
    assert prefix[0]["selected_space_size"] == outcome.summary["selected_union_determinants"]


def test_sample_union_uses_occupancy_recovery_only_for_noisy_callback() -> None:
    sample = np.asarray(
        [
            [False, True, False, True],
            [False, False, True, True],
        ],
        dtype=bool,
    )
    sample_union = SKQDSampleUnion(
        samples_by_state=(SKQDKrylovSample(0, 0.0, sample),),
        merged_bitstring_matrix=sample,
        merged_probabilities=np.asarray([0.5, 0.5]),
        merged_counts=np.asarray([1, 1]),
        provenance=(),
    )

    recovery_calls = []

    def recover(bits, probabilities, **kwargs):
        recovery_calls.append(kwargs["avg_occupancies"])
        assert bits.shape[0] == probabilities.shape[0] == 1
        return np.asarray([[True, False, False, True]], dtype=bool), np.asarray([1.0])

    def postselect(bits, probabilities, **_kwargs):
        mask = np.logical_and(
            np.sum(bits[:, 2:], axis=1) == 1,
            np.sum(bits[:, :2], axis=1) == 1,
        )
        selected = bits[mask]
        selected_probabilities = probabilities[mask]
        return selected, selected_probabilities / np.sum(selected_probabilities)

    outcome = solve_sample_union_selected_ci(
        sample_union,
        options=_options(),  # type: ignore[arg-type]
        rng=np.random.default_rng(1),
        recover_configurations=recover,
        postselect_by_hamming_right_and_left=postselect,
        solve_fermion=lambda *_args, **_kwargs: (
            -1.0,
            None,
            (np.asarray([1.0, 0.0]), np.asarray([1.0, 0.0])),
            0.0,
        ),
    )

    assert len(recovery_calls) == 1
    assert outcome.summary["configuration_recovery_policy"] == (
        "postselect_then_occupancy_recovery"
    )
    assert outcome.summary["recovery_applied"] is True
    assert outcome.summary["recovered_union_determinants"] == 1


def test_sample_union_merges_recovery_collisions_before_projection() -> None:
    sample = np.asarray(
        [
            [False, True, False, True],
            [False, False, True, True],
        ],
        dtype=bool,
    )
    sample_union = SKQDSampleUnion(
        samples_by_state=(SKQDKrylovSample(0, 0.0, sample),),
        merged_bitstring_matrix=sample,
        merged_probabilities=np.asarray([0.5, 0.5]),
        merged_counts=np.asarray([1, 1]),
        provenance=(),
    )

    def recover(_bits, _probabilities, **_kwargs):
        # Two noisy source rows can map to the same recovered determinant.
        return (
            np.asarray(
                [[False, True, False, True], [False, True, False, True]],
                dtype=bool,
            ),
            np.asarray([0.5, 0.5]),
        )

    def postselect(bits, probabilities, **_kwargs):
        mask = np.logical_and(
            np.sum(bits[:, 2:], axis=1) == 1,
            np.sum(bits[:, :2], axis=1) == 1,
        )
        selected = bits[mask]
        selected_probabilities = probabilities[mask]
        return selected, selected_probabilities / np.sum(selected_probabilities)

    outcome = solve_sample_union_selected_ci(
        sample_union,
        options=_options(),  # type: ignore[arg-type]
        rng=np.random.default_rng(1),
        recover_configurations=recover,
        postselect_by_hamming_right_and_left=postselect,
        solve_fermion=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("SKQD must use its restricted sampled-union solver")
        ),
    )

    assert outcome.summary["selected_union_determinants"] == 1
    assert outcome.summary["recovered_union_determinants"] == 1


def test_d_one_sample_union_matches_sqd_selected_ci_batch() -> None:
    sample = np.asarray([[False, True, False, True]], dtype=bool)
    probabilities = np.asarray([1.0])
    options = _options()
    empty_carryover = (
        np.empty((0, options.norb), dtype=np.int64),
        np.empty((0, options.norb), dtype=np.int64),
    )
    occupancies = (np.asarray([0.5, 0.5]), np.asarray([0.5, 0.5]))

    def solve(*_args, **_kwargs):
        return 0.0, None, occupancies, 0.0

    sqd_dependencies = SimpleNamespace(
        subsample=lambda _bits, _probs, **_kwargs: [sample],
        solve_fermion=solve,
    )
    sqd_outcome = run_selected_ci_batches(
        iteration=1,
        deps=sqd_dependencies,
        options=options,  # type: ignore[arg-type]
        rng=np.random.default_rng(1),
        selected_bits=sample,
        selected_probs=probabilities,
        carryover_ci_strings=empty_carryover,
        progress_callback=None,
    )
    skqd_outcome = solve_sample_union_selected_ci(
        SKQDSampleUnion(
            samples_by_state=(SKQDKrylovSample(0, 0.0, sample),),
            merged_bitstring_matrix=sample,
            merged_probabilities=probabilities,
            merged_counts=np.asarray([1]),
            provenance=(),
        ),
        options=options,  # type: ignore[arg-type]
        rng=np.random.default_rng(1),
        recover_configurations=None,
        postselect_by_hamming_right_and_left=lambda bits, probs, **_kwargs: (bits, probs),
        solve_fermion=solve,
    )

    assert skqd_outcome.energy == sqd_outcome.energy_value
    assert skqd_outcome.summary["limiting_case"] == "d=1_sqd_equivalent"
