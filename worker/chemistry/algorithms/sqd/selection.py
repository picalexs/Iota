"""Pure selected-CI and postselection helpers for the SQD algorithm package."""

from __future__ import annotations

from math import comb
from typing import Any

import numpy as np

_DEFAULT_FULL_SELECTED_CI_DIMENSION_LIMIT = 1024
_DEFAULT_PARTIAL_SELECTED_CI_STRINGS_PER_SPIN = 32


def _default_partial_spin_limit(full_dimension: int) -> int:
    """Keep the default selected-CI space below a nontrivial full sector."""
    if full_dimension <= 1:
        return max(1, full_dimension)
    return max(1, min(_DEFAULT_PARTIAL_SELECTED_CI_STRINGS_PER_SPIN, full_dimension - 1))


def resolve_selected_ci_limits(
    raw_max_dim: object,
    *,
    norb: int,
    num_elec_a: int,
    num_elec_b: int,
) -> tuple[tuple[int, int], dict[str, Any]]:
    """Resolve selected-CI determinant-string limits for SQD batch solves."""
    full_alpha = int(comb(norb, num_elec_a))
    full_beta = int(comb(norb, num_elec_b))
    full_dimension = full_alpha * full_beta

    full_sector_requested = False
    if raw_max_dim is None:
        max_alpha = _default_partial_spin_limit(full_alpha)
        max_beta = _default_partial_spin_limit(full_beta)
        source = "default_partial_sector_cap"
    elif isinstance(raw_max_dim, str) and raw_max_dim.strip().lower() == "full":
        max_alpha, max_beta = full_alpha, full_beta
        source = "explicit_full_sector"
        full_sector_requested = True
    elif isinstance(raw_max_dim, bool):
        raise ValueError("SQD max_dim must be a positive integer or a pair of integers")
    elif isinstance(raw_max_dim, int):
        if raw_max_dim < 1:
            raise ValueError("SQD max_dim must be positive")
        max_alpha = min(full_alpha, int(raw_max_dim))
        max_beta = min(full_beta, int(raw_max_dim))
        source = "configured_scalar"
    elif (
        isinstance(raw_max_dim, (list, tuple))
        and len(raw_max_dim) == 2
        and all(isinstance(value, int) and not isinstance(value, bool) for value in raw_max_dim)
    ):
        raw_alpha, raw_beta = int(raw_max_dim[0]), int(raw_max_dim[1])
        if raw_alpha < 1 or raw_beta < 1:
            raise ValueError("SQD max_dim entries must be positive")
        max_alpha = min(full_alpha, raw_alpha)
        max_beta = min(full_beta, raw_beta)
        source = "configured_pair"
    else:
        raise ValueError("SQD max_dim must be a positive integer or a pair of integers")

    effective_dimension = int(max_alpha * max_beta)
    summary = {
        "max_dim": [int(max_alpha), int(max_beta)],
        "max_dim_source": source,
        "full_ci_strings": [full_alpha, full_beta],
        "full_sci_dimension": full_dimension,
        "default_full_sector_limit": _DEFAULT_FULL_SELECTED_CI_DIMENSION_LIMIT,
        "default_partial_ci_strings_per_spin": _DEFAULT_PARTIAL_SELECTED_CI_STRINGS_PER_SPIN,
        "full_sector_requested": full_sector_requested,
        "cap_active": effective_dimension < full_dimension,
    }
    return (int(max_alpha), int(max_beta)), summary


def bitstring_matrix_to_integers(bitstring_matrix: np.ndarray) -> np.ndarray:
    """Convert addon-order orbital occupancy rows to determinant integers."""
    matrix = np.asarray(bitstring_matrix, dtype=bool)
    if matrix.ndim != 2:
        raise ValueError("SQD determinant conversion expects a 2D bitstring matrix")

    num_bits = matrix.shape[1]
    values: list[int] = []
    for row in matrix:
        value = 0
        for bit_index, occupied in enumerate(row):
            if bool(occupied):
                value |= 1 << (num_bits - 1 - bit_index)
        values.append(value)
    return np.asarray(values, dtype=np.int64)


def top_weighted_determinants(weights: dict[int, float], limit: int) -> np.ndarray:
    """Return deterministic top-weighted determinant strings."""
    ordered = sorted(weights.items(), key=lambda item: (-float(item[1]), int(item[0])))
    selected = [int(value) for value, _weight in ordered[:limit]]
    return np.asarray(selected, dtype=np.int64)


def ordered_determinants_by_weight(weights: dict[int, float]) -> np.ndarray:
    """Return determinant strings ordered by descending marginal weight."""
    ordered = sorted(weights.items(), key=lambda item: (-float(item[1]), int(item[0])))
    return np.asarray([int(value) for value, _weight in ordered], dtype=np.int64)


def unique_with_order_preserved(values: np.ndarray) -> np.ndarray:
    """Return unique determinant strings while preserving the original priority order."""
    if values.size == 0:
        return np.asarray([], dtype=np.int64)
    _, indices = np.unique(values, return_index=True)
    indices.sort()
    return np.asarray(values[indices], dtype=np.int64)


def selected_ci_strings_from_bitstrings(
    bitstring_matrix: np.ndarray,
    probabilities: np.ndarray,
    *,
    max_dim: tuple[int, int],
    open_shell: bool,
    symmetrize_spin: bool = False,
    carryover_ci_strings: tuple[np.ndarray, np.ndarray] | None = None,
) -> tuple[tuple[np.ndarray, np.ndarray], dict[str, Any]]:
    """Build a capped selected-CI determinant space from weighted SQD bitstrings."""
    matrix = np.asarray(bitstring_matrix, dtype=bool)
    probs = np.asarray(probabilities, dtype=float).reshape(-1)
    if matrix.ndim != 2 or matrix.shape[0] == 0:
        raise ValueError("SQD selected-CI solve needs at least one bitstring")
    if probs.size != matrix.shape[0]:
        raise ValueError("SQD selected-CI probabilities must match bitstring rows")

    norb = matrix.shape[1] // 2
    left_ints = bitstring_matrix_to_integers(matrix[:, :norb])
    right_ints = bitstring_matrix_to_integers(matrix[:, norb:])
    max_alpha, max_beta = max_dim
    if carryover_ci_strings is None:
        carryover_ci_strings = (
            np.asarray([], dtype=np.int64),
            np.asarray([], dtype=np.int64),
        )
    carryover_alpha = np.asarray(carryover_ci_strings[0], dtype=np.int64).reshape(-1)
    carryover_beta = np.asarray(carryover_ci_strings[1], dtype=np.int64).reshape(-1)

    left_weights: dict[int, float] = {}
    right_weights: dict[int, float] = {}
    for left, right, probability in zip(left_ints, right_ints, probs, strict=True):
        left_weights[int(left)] = left_weights.get(int(left), 0.0) + float(probability)
        right_weights[int(right)] = right_weights.get(int(right), 0.0) + float(probability)

    # qiskit-addon-sqd uses one shared pool for closed-shell inputs. The
    # explicit flag keeps the same pool available for the legacy equal-spin
    # option, while open-shell inputs retain independent pools.
    shared_spin_pool = not open_shell or symmetrize_spin
    if shared_spin_pool:
        combined_weights = dict(left_weights)
        for determinant, weight in right_weights.items():
            combined_weights[int(determinant)] = combined_weights.get(
                int(determinant), 0.0
            ) + float(weight)
        ordered_shared = ordered_determinants_by_weight(combined_weights)
        carryover_shared = unique_with_order_preserved(
            np.concatenate((carryover_alpha, carryover_beta))
        )
        shared_limit = min(max_alpha, max_beta)
        shared_ci = unique_with_order_preserved(np.concatenate((carryover_shared, ordered_shared)))[
            :shared_limit
        ]
        ci_alpha = shared_ci
        ci_beta = shared_ci.copy()
        available_alpha = len(combined_weights)
        available_beta = len(combined_weights)
        carryover_alpha = carryover_shared
        carryover_beta = carryover_shared
    else:
        ordered_alpha = ordered_determinants_by_weight(right_weights)
        ordered_beta = ordered_determinants_by_weight(left_weights)
        ci_alpha = unique_with_order_preserved(np.concatenate((carryover_alpha, ordered_alpha)))[
            :max_alpha
        ]
        ci_beta = unique_with_order_preserved(np.concatenate((carryover_beta, ordered_beta)))[
            :max_beta
        ]
        available_alpha = len(right_weights)
        available_beta = len(left_weights)

    if ci_alpha.size == 0 or ci_beta.size == 0:
        raise ValueError("SQD selected-CI determinant cap removed every determinant")

    ci_alpha.sort()
    ci_beta.sort()
    sci_dimension = int(ci_alpha.size * ci_beta.size)
    available_dimension = int(available_alpha * available_beta)
    summary = {
        "ci_strings_alpha": int(ci_alpha.size),
        "ci_strings_beta": int(ci_beta.size),
        "available_ci_strings_alpha": int(available_alpha),
        "available_ci_strings_beta": int(available_beta),
        "sci_dimension": sci_dimension,
        "available_sci_dimension": available_dimension,
        "cap_active_for_batch": sci_dimension < available_dimension,
        "spin_symmetrized": bool(shared_spin_pool),
        "selection_pool_mode": (
            "shared_spin_pool" if shared_spin_pool else "independent_spin_pools"
        ),
        "requested_spin_symmetrization": bool(symmetrize_spin),
        "carryover_strings_alpha": int(carryover_alpha.size),
        "carryover_strings_beta": int(carryover_beta.size),
        "open_shell": bool(open_shell),
    }
    return (ci_alpha, ci_beta), summary


def extract_carryover_ci_strings(
    sci_state: Any,
    *,
    carryover_threshold: float,
    symmetrize_spin: bool,
    open_shell: bool = False,
) -> tuple[tuple[np.ndarray, np.ndarray], dict[str, Any]]:
    """Select determinant strings to retain into the next SQD recovery iteration."""
    empty = (
        np.asarray([], dtype=np.int64),
        np.asarray([], dtype=np.int64),
    )
    summary: dict[str, Any] = {
        "carryover_threshold": round(float(carryover_threshold), 8),
        "carryover_strings_alpha": 0,
        "carryover_strings_beta": 0,
        "spin_symmetrized": bool(not open_shell or symmetrize_spin),
        "selection_pool_mode": (
            "shared_spin_pool" if not open_shell or symmetrize_spin else "independent_spin_pools"
        ),
        "requested_spin_symmetrization": bool(symmetrize_spin),
    }
    if sci_state is None:
        return empty, summary

    amplitudes = np.asarray(getattr(sci_state, "amplitudes", np.asarray([])), dtype=complex)
    ci_strs_a = np.asarray(getattr(sci_state, "ci_strs_a", np.asarray([])), dtype=np.int64).reshape(
        -1
    )
    ci_strs_b = np.asarray(getattr(sci_state, "ci_strs_b", np.asarray([])), dtype=np.int64).reshape(
        -1
    )
    if amplitudes.shape != (ci_strs_a.size, ci_strs_b.size) or amplitudes.size == 0:
        return empty, summary

    absolute_vals = np.abs(amplitudes.reshape(-1))
    indices = np.argsort(absolute_vals)
    carryover_index = int(np.searchsorted(absolute_vals, carryover_threshold, sorter=indices))
    carryover_indices = indices[carryover_index:]
    if carryover_indices.size == 0:
        return empty, summary

    _, n_strings_b = amplitudes.shape
    alpha_indices, beta_indices = np.divmod(carryover_indices, n_strings_b)
    alpha_indices = np.unique(alpha_indices.astype(int))
    beta_indices = np.unique(beta_indices.astype(int))
    carryover_alpha = ci_strs_a[alpha_indices]
    carryover_beta = ci_strs_b[beta_indices]
    weights_alpha = _carryover_weights(amplitudes, alpha_indices, axis=1)
    weights_beta = _carryover_weights(amplitudes, beta_indices, axis=0)
    carryover_alpha, carryover_beta = _order_carryover_strings(
        carryover_alpha,
        carryover_beta,
        weights_alpha,
        weights_beta,
        shared=not open_shell or symmetrize_spin,
    )

    summary["carryover_strings_alpha"] = int(carryover_alpha.size)
    summary["carryover_strings_beta"] = int(carryover_beta.size)
    return (carryover_alpha, carryover_beta), summary


def _carryover_weights(
    amplitudes: np.ndarray,
    indices: np.ndarray,
    *,
    axis: int,
) -> np.ndarray:
    if indices.size == 0:
        return np.asarray([], dtype=float)
    selected = amplitudes[indices] if axis == 1 else amplitudes[:, indices]
    return np.sum(np.abs(selected) ** 2, axis=axis)


def _order_carryover_strings(
    carryover_alpha: np.ndarray,
    carryover_beta: np.ndarray,
    weights_alpha: np.ndarray,
    weights_beta: np.ndarray,
    *,
    shared: bool,
) -> tuple[np.ndarray, np.ndarray]:
    if shared:
        merged = np.concatenate((carryover_alpha, carryover_beta))
        merged_weights = np.concatenate((weights_alpha, weights_beta))
        if merged.size:
            merged = merged[np.argsort(merged_weights)[::-1]]
        shared_strings = unique_with_order_preserved(merged)
        return shared_strings, shared_strings
    if carryover_alpha.size:
        carryover_alpha = carryover_alpha[np.argsort(weights_alpha)[::-1]]
    if carryover_beta.size:
        carryover_beta = carryover_beta[np.argsort(weights_beta)[::-1]]
    return carryover_alpha, carryover_beta


def postselection_weight(
    bitstring_matrix: np.ndarray,
    probabilities: np.ndarray,
    *,
    num_elec_a: int,
    num_elec_b: int,
) -> float:
    """Return probability mass satisfying the SQD alpha/beta Hamming constraints."""
    matrix = np.asarray(bitstring_matrix, dtype=bool)
    probs = np.asarray(probabilities, dtype=float).reshape(-1)
    if matrix.ndim != 2 or matrix.shape[1] % 2 or probs.size != matrix.shape[0]:
        return 0.0
    norb = matrix.shape[1] // 2
    valid_right = np.sum(matrix[:, norb:], axis=1) == num_elec_a
    valid_left = np.sum(matrix[:, :norb], axis=1) == num_elec_b
    return float(np.sum(probs[np.logical_and(valid_right, valid_left)]))


def selected_ci_fraction(sci_dimension: float, *, full_sci_dimension: float) -> float:
    """Normalize a selected-CI dimension against the full sector size."""
    return float(sci_dimension) / max(1.0, float(full_sci_dimension))


__all__ = [
    "bitstring_matrix_to_integers",
    "extract_carryover_ci_strings",
    "ordered_determinants_by_weight",
    "postselection_weight",
    "resolve_selected_ci_limits",
    "selected_ci_strings_from_bitstrings",
    "selected_ci_fraction",
    "top_weighted_determinants",
    "unique_with_order_preserved",
]
