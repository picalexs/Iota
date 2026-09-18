"""Selected-CI solve for the determinant union produced by paper-faithful SKQD."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import numpy as np

from worker.chemistry.algorithms.skqd.sampling import SKQDSampleUnion
from worker.chemistry.algorithms.sqd.config import SQDOptions
from worker.chemistry.algorithms.sqd.sampling import aggregate_weighted_bitstring_probabilities
from worker.chemistry.algorithms.sqd.selection import (
    bitstring_matrix_to_integers,
    selected_ci_fraction,
    selected_ci_strings_from_bitstrings,
)


@dataclass(frozen=True)
class SKQDSelectedCIOutcome:
    """Selected-CI result and auditable sample-union metadata."""

    energy: float
    spin_sq: float
    occupancies: tuple[np.ndarray, np.ndarray]
    selected_ci_strings: tuple[np.ndarray, np.ndarray]
    summary: dict[str, Any]


def _select_sampled_determinant_union(
    bitstrings: np.ndarray,
    probabilities: np.ndarray,
    *,
    options: SQDOptions,
    postselect_by_hamming_right_and_left: Callable[..., tuple[np.ndarray, np.ndarray]],
) -> tuple[np.ndarray, tuple[np.ndarray, np.ndarray], dict[str, Any]]:
    """Postselect and apply the configured limits without completing the union."""
    unique_bitstrings, unique_probabilities = aggregate_weighted_bitstring_probabilities(
        np.asarray(bitstrings, dtype=bool),
        np.asarray(probabilities, dtype=float),
    )
    selected_bits, selected_probs = postselect_by_hamming_right_and_left(
        unique_bitstrings,
        unique_probabilities.copy(),
        hamming_right=options.num_elec_a,
        hamming_left=options.num_elec_b,
    )
    if selected_bits.size == 0:
        raise ValueError("SKQD sample union postselection yielded no valid determinants")

    ci_strings, selection_summary = selected_ci_strings_from_bitstrings(
        selected_bits,
        selected_probs,
        max_dim=options.selected_ci_limits,
        open_shell=options.open_shell,
        symmetrize_spin=options.symmetrize_spin,
    )
    selected_beta = bitstring_matrix_to_integers(selected_bits[:, : options.norb])
    selected_alpha = bitstring_matrix_to_integers(selected_bits[:, options.norb :])
    union_mask = np.logical_and(
        np.isin(selected_alpha, ci_strings[0]),
        np.isin(selected_beta, ci_strings[1]),
    )
    union_bits = selected_bits[union_mask]
    if union_bits.shape[0] == 0:
        raise ValueError("SKQD selected-CI limits removed every sampled determinant")

    selected_ci_dimension = int(union_bits.shape[0])
    selection_summary = {
        **selection_summary,
        "sci_dimension": selected_ci_dimension,
        "selected_ci_dimension": selected_ci_dimension,
        "available_sci_dimension": int(selected_bits.shape[0]),
        "cap_active_for_batch": selected_ci_dimension < int(selected_bits.shape[0]),
        "selected_union_bitstrings": [
            "".join("1" if value else "0" for value in row) for row in union_bits
        ],
    }
    return union_bits, ci_strings, selection_summary


def _solve_sampled_determinant_union(
    selected_bits: np.ndarray,
    *,
    options: SQDOptions,
) -> tuple[float, tuple[np.ndarray, np.ndarray], float]:
    """Solve H in the exact sampled determinant basis.

    ``qiskit-addon-sqd.solve_fermion`` represents a Cartesian product of
    alpha and beta string lists. A Krylov sample union is not generally such
    a product, so using that API would add determinants that were not sampled.
    Build the restricted sector matrix directly instead.
    """
    from types import SimpleNamespace

    import ffsim

    from worker.chemistry.hamiltonian_action import build_hamiltonian_action
    from worker.chemistry.sector_basis import bitstring_to_address

    matrix = np.asarray(selected_bits, dtype=bool)
    norb = options.norb
    action = build_hamiltonian_action(
        SimpleNamespace(
            one_body_tensor=options.one_body,
            two_body_tensor=options.two_body,
            constant=options.hamiltonian_constant,
            num_spatial_orbitals=norb,
            num_electrons_alpha=options.num_elec_a,
            num_electrons_beta=options.num_elec_b,
        )
    )
    addresses = np.asarray(
        [
            bitstring_to_address(
                "".join("1" if value else "0" for value in row),
                norb=norb,
                nelec=(options.num_elec_a, options.num_elec_b),
            )
            for row in matrix
        ],
        dtype=np.int64,
    )
    if np.unique(addresses).size != addresses.size:
        raise ValueError("SKQD sample union contains duplicate determinant addresses")

    basis = np.zeros((action.dimension, addresses.size), dtype=complex)
    basis[addresses, np.arange(addresses.size)] = 1.0
    projected = basis.conj().T @ np.column_stack(
        [action.matvec(basis[:, index]) for index in range(addresses.size)]
    )
    projected = 0.5 * (projected + projected.conj().T)
    eigenvalues, eigenvectors = np.linalg.eigh(projected)
    coefficients = np.asarray(eigenvectors[:, int(np.argmin(eigenvalues))], dtype=complex)
    state = basis @ coefficients
    probabilities = np.abs(coefficients) ** 2

    alpha_bits = matrix[:, norb:]
    beta_bits = matrix[:, :norb]
    occupancies = (
        np.sum(probabilities[:, None] * alpha_bits, axis=0),
        np.sum(probabilities[:, None] * beta_bits, axis=0),
    )
    spin_sq = float(ffsim.spin_square(state, norb, (options.num_elec_a, options.num_elec_b)))
    return float(np.real_if_close(eigenvalues[int(np.argmin(eigenvalues))])), occupancies, spin_sq


def solve_sample_union_selected_ci(
    sample_union: SKQDSampleUnion,
    *,
    options: SQDOptions,
    rng: np.random.Generator,
    recover_configurations: Callable[..., tuple[np.ndarray, np.ndarray]] | None,
    postselect_by_hamming_right_and_left: Callable[..., tuple[np.ndarray, np.ndarray]],
    solve_fermion: Callable[..., tuple[float, Any, tuple[np.ndarray, np.ndarray], float]],
) -> SKQDSelectedCIOutcome:
    """Postselect, optionally recover, and diagonalize the sampled union.

    The published SKQD construction uses the union of sampled computational
    basis configurations as its determinant space. Exact paths use raw
    postselection. Noisy paths first solve the valid union, use its occupations
    for U(1) configuration recovery, and then solve the recovered union.
    """
    del solve_fermion
    sampled_bits = np.asarray(sample_union.merged_bitstring_matrix, dtype=bool)
    sampled_probs = np.asarray(sample_union.merged_probabilities, dtype=float)
    if sampled_bits.ndim != 2 or sampled_bits.shape[0] == 0:
        raise ValueError("SKQD sample union is empty")

    norb = sampled_bits.shape[1] // 2
    raw_valid_mask = np.logical_and(
        np.sum(sampled_bits[:, norb:], axis=1) == options.num_elec_a,
        np.sum(sampled_bits[:, :norb], axis=1) == options.num_elec_b,
    )
    raw_valid_bits = sampled_bits[raw_valid_mask]
    raw_valid_probs = sampled_probs[raw_valid_mask]
    raw_invalid_bits = sampled_bits[~raw_valid_mask]
    raw_invalid_probs = sampled_probs[~raw_valid_mask]
    raw_valid_mass = float(np.sum(raw_valid_probs))
    raw_invalid_mass = float(np.sum(raw_invalid_probs))
    if raw_valid_bits.shape[0] == 0:
        raise ValueError(
            "SKQD sample union has no raw valid-sector determinant for occupation recovery"
        )

    recovered_bits = np.empty((0, sampled_bits.shape[1]), dtype=bool)
    if recover_configurations is not None and raw_invalid_bits.shape[0] > 0:
        (
            union_bits,
            ci_strings,
            selection_summary,
            recovered_bits,
            recovery_applied,
        ) = _select_recovered_union(
            sampled_bits=sampled_bits,
            sampled_probs=sampled_probs,
            raw_valid_bits=raw_valid_bits,
            raw_valid_probs=raw_valid_probs,
            raw_invalid_bits=raw_invalid_bits,
            raw_invalid_probs=raw_invalid_probs,
            raw_invalid_mass=raw_invalid_mass,
            options=options,
            rng=rng,
            recover_configurations=recover_configurations,
            postselect_by_hamming_right_and_left=postselect_by_hamming_right_and_left,
        )
    else:
        union_bits, ci_strings, selection_summary = _select_sampled_determinant_union(
            sampled_bits,
            sampled_probs,
            options=options,
            postselect_by_hamming_right_and_left=postselect_by_hamming_right_and_left,
        )
        recovery_applied = False
    recovery_policy = (
        "postselect_then_occupancy_recovery" if recovery_applied else "postselect_only"
    )

    energy, occupancies, spin_sq = _solve_sampled_determinant_union(
        union_bits,
        options=options,
    )
    selected_ci_dimension = int(union_bits.shape[0])
    summary = {
        **options.selected_ci_limit_summary,
        **selection_summary,
        "sampled_krylov_states": len(sample_union.samples_by_state),
        "samples_per_krylov_state": [
            int(sample.bitstring_matrix.shape[0]) for sample in sample_union.samples_by_state
        ],
        "sampled_union_determinants": int(sample_union.merged_bitstring_matrix.shape[0]),
        "raw_postselected_union_determinants": int(raw_valid_bits.shape[0]),
        "postselected_union_determinants": int(selection_summary["available_sci_dimension"]),
        "selected_union_determinants": selected_ci_dimension,
        "discarded_invalid_union_determinants": int(
            raw_invalid_bits.shape[0] - recovered_bits.shape[0]
        ),
        "raw_postselection_weight": raw_valid_mass,
        "recovered_union_determinants": int(recovered_bits.shape[0]),
        "configuration_recovery_policy": recovery_policy,
        "recovery_applied": recovery_applied,
        "selected_ci_fraction": selected_ci_fraction(
            selected_ci_dimension,
            full_sci_dimension=options.selected_ci_limit_summary["full_sci_dimension"],
        ),
        "selection_source": "skqd_krylov_sample_union",
        "solve_type": "ordinary_selected_ci",
        "limiting_case": (
            "d=1_sqd_equivalent"
            if len(sample_union.samples_by_state) == 1
            else "multi_state_sample_union"
        ),
        "work_ledger": dict(sample_union.work_ledger),
    }
    return SKQDSelectedCIOutcome(
        energy=float(energy),
        spin_sq=float(spin_sq),
        occupancies=(
            np.asarray(occupancies[0], dtype=float).copy(),
            np.asarray(occupancies[1], dtype=float).copy(),
        ),
        selected_ci_strings=ci_strings,
        summary=summary,
    )


def _select_recovered_union(
    *,
    sampled_bits: np.ndarray,
    sampled_probs: np.ndarray,
    raw_valid_bits: np.ndarray,
    raw_valid_probs: np.ndarray,
    raw_invalid_bits: np.ndarray,
    raw_invalid_probs: np.ndarray,
    raw_invalid_mass: float,
    options: SQDOptions,
    rng: np.random.Generator,
    recover_configurations: Callable[..., tuple[np.ndarray, np.ndarray]],
    postselect_by_hamming_right_and_left: Callable[..., tuple[np.ndarray, np.ndarray]],
) -> tuple[np.ndarray, np.ndarray, dict[str, Any], np.ndarray, bool]:
    initial_bits, _initial_ci, _initial_summary = _select_sampled_determinant_union(
        raw_valid_bits,
        raw_valid_probs,
        options=options,
        postselect_by_hamming_right_and_left=postselect_by_hamming_right_and_left,
    )
    _, initial_occupancies, _ = _solve_sampled_determinant_union(initial_bits, options=options)
    recovered_candidate, recovered_candidate_probs = recover_configurations(
        raw_invalid_bits,
        raw_invalid_probs,
        avg_occupancies=initial_occupancies,
        num_elec_a=options.num_elec_a,
        num_elec_b=options.num_elec_b,
        rand_seed=rng,
    )
    if recovered_candidate.shape[0] > 0:
        recovered_candidate, recovered_candidate_probs = postselect_by_hamming_right_and_left(
            np.asarray(recovered_candidate, dtype=bool),
            np.asarray(recovered_candidate_probs, dtype=float).copy(),
            hamming_right=options.num_elec_a,
            hamming_left=options.num_elec_b,
        )
        recovered_candidate, recovered_candidate_probs = aggregate_weighted_bitstring_probabilities(
            np.asarray(recovered_candidate, dtype=bool),
            np.asarray(recovered_candidate_probs, dtype=float),
        )
        probability_sum = float(np.sum(recovered_candidate_probs))
        if probability_sum > 0.0:
            recovered_candidate_probs = recovered_candidate_probs / probability_sum
    if recovered_candidate.shape[0] == 0 or raw_invalid_mass <= 0.0:
        selected = _select_sampled_determinant_union(
            sampled_bits,
            sampled_probs,
            options=options,
            postselect_by_hamming_right_and_left=postselect_by_hamming_right_and_left,
        )
        return (*selected, np.empty((0, sampled_bits.shape[1]), dtype=bool), False)

    recovered_probs = np.asarray(recovered_candidate_probs, dtype=float) * raw_invalid_mass
    combined_bits = np.concatenate((raw_valid_bits, recovered_candidate), axis=0)
    combined_probs = np.concatenate((raw_valid_probs, recovered_probs), axis=0)
    selected = _select_sampled_determinant_union(
        combined_bits,
        combined_probs,
        options=options,
        postselect_by_hamming_right_and_left=postselect_by_hamming_right_and_left,
    )
    return (*selected, recovered_candidate, True)


__all__ = ["SKQDSelectedCIOutcome", "solve_sample_union_selected_ci"]
