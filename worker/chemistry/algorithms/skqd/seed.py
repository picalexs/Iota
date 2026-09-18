"""Pure SQD-to-SKQD seed-state normalization helpers for the algorithm package."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from worker.chemistry.hamiltonian_action import HamiltonianAction
from worker.chemistry.sector_basis import state_from_sector_amplitudes
from worker.chemistry.types import SKQDResult


def seed_state_from_sqd_result_with_source(
    sqd_result: SKQDResult | Any,
    *,
    target_size: int,
) -> tuple[np.ndarray | None, str]:
    """Build a dense seed from the best coherent selected-CI state."""
    entries, norb, nelec, source = _selected_ci_amplitude_entries(sqd_result)
    if entries is None:
        return None, source
    if target_size != 1 << (2 * norb):
        return None, "sqd_state_dimension_mismatch"

    state = np.zeros(target_size, dtype=complex)
    for entry in entries:
        basis_index = int(str(entry["bitstring"]), 2)
        raw_amplitude = entry["amplitude"]
        amplitude = complex(float(raw_amplitude[0]), float(raw_amplitude[1]))
        state[basis_index] += amplitude
    norm = float(np.linalg.norm(state))
    if not math.isfinite(norm) or norm == 0.0:
        return None, "invalid_sqd_selected_ci_state"
    return state / norm, "sqd_best_selected_ci_coefficients"


def seed_state_from_sqd_result(
    sqd_result: SKQDResult | Any,
    *,
    target_size: int,
) -> np.ndarray | None:
    """Build a Hilbert-space seed state from SQD data."""
    state, _ = seed_state_from_sqd_result_with_source(sqd_result, target_size=target_size)
    return state


def sector_seed_state_from_sqd_result_with_source(
    sqd_result: SKQDResult | Any,
    *,
    action: HamiltonianAction,
) -> tuple[np.ndarray | None, str]:
    """Build a fixed-sector seed from the best complex selected-CI coefficients."""
    entries, norb, nelec, source = _selected_ci_amplitude_entries(sqd_result)
    if entries is None:
        return None, source
    if norb != action.norb or nelec != action.nelec:
        return None, "sqd_state_sector_mismatch"
    if action.dimension != math.comb(norb, nelec[0]) * math.comb(norb, nelec[1]):
        return None, "sqd_state_dimension_mismatch"
    try:
        state = state_from_sector_amplitudes(
            entries,
            norb=norb,
            nelec=nelec,
            dimension=action.dimension,
        )
    except (TypeError, ValueError):
        return None, "invalid_sqd_selected_ci_state"
    return state, "sqd_best_selected_ci_coefficients"


def _selected_ci_amplitude_entries(
    sqd_result: Any,
) -> tuple[list[dict[str, Any]] | None, int, tuple[int, int], str]:
    """Validate and map the best selected-CI vector to app bitstring order."""
    selected_state = getattr(sqd_result, "best_sci_state", None)
    if selected_state is None:
        return None, 0, (0, 0), "missing_sqd_selected_ci_state"

    raw_norb = getattr(selected_state, "norb", None)
    raw_nelec = getattr(selected_state, "nelec", None)
    if isinstance(raw_norb, bool) or not isinstance(raw_norb, (int, np.integer)):
        return None, 0, (0, 0), "invalid_sqd_selected_ci_state"
    norb = int(raw_norb)
    if norb < 1 or not isinstance(raw_nelec, (tuple, list)) or len(raw_nelec) != 2:
        return None, norb, (0, 0), "invalid_sqd_selected_ci_state"
    if any(isinstance(value, bool) or not isinstance(value, (int, np.integer)) for value in raw_nelec):
        return None, norb, (0, 0), "invalid_sqd_selected_ci_state"
    nelec = int(raw_nelec[0]), int(raw_nelec[1])
    if any(value < 0 or value > norb for value in nelec):
        return None, norb, nelec, "invalid_sqd_selected_ci_state"

    try:
        amplitudes = np.asarray(getattr(selected_state, "amplitudes"), dtype=complex)
        alpha_strings = np.asarray(getattr(selected_state, "ci_strs_a")).reshape(-1)
        beta_strings = np.asarray(getattr(selected_state, "ci_strs_b")).reshape(-1)
    except (AttributeError, TypeError, ValueError):
        return None, norb, nelec, "invalid_sqd_selected_ci_state"
    if (
        amplitudes.shape != (alpha_strings.size, beta_strings.size)
        or not np.all(np.isfinite(amplitudes))
    ):
        return None, norb, nelec, "invalid_sqd_selected_ci_state"

    entries: list[dict[str, Any]] = []
    determinant_limit = 1 << norb
    for alpha_index, raw_alpha in enumerate(alpha_strings):
        if isinstance(raw_alpha, (bool, np.bool_)) or not isinstance(
            raw_alpha, (int, np.integer)
        ):
            return None, norb, nelec, "invalid_sqd_selected_ci_state"
        alpha_mask = int(raw_alpha)
        if alpha_mask < 0 or alpha_mask >= determinant_limit or alpha_mask.bit_count() != nelec[0]:
            return None, norb, nelec, "invalid_sqd_selected_ci_state"
        for beta_index, raw_beta in enumerate(beta_strings):
            if isinstance(raw_beta, (bool, np.bool_)) or not isinstance(
                raw_beta, (int, np.integer)
            ):
                return None, norb, nelec, "invalid_sqd_selected_ci_state"
            beta_mask = int(raw_beta)
            if beta_mask < 0 or beta_mask >= determinant_limit or beta_mask.bit_count() != nelec[1]:
                return None, norb, nelec, "invalid_sqd_selected_ci_state"
            amplitude = complex(amplitudes[alpha_index, beta_index])
            if amplitude == 0.0:
                continue
            entries.append(
                {
                    "bitstring": f"{beta_mask:0{norb}b}{alpha_mask:0{norb}b}",
                    "amplitude": [float(amplitude.real), float(amplitude.imag)],
                }
            )
    if not entries:
        return None, norb, nelec, "invalid_sqd_selected_ci_state"
    return entries, norb, nelec, "sqd_best_selected_ci_coefficients"


__all__ = [
    "seed_state_from_sqd_result",
    "seed_state_from_sqd_result_with_source",
    "sector_seed_state_from_sqd_result_with_source",
]
