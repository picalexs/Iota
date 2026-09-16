"""Pure SQD-to-SKQD seed-state normalization helpers for the algorithm package."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from worker.chemistry.hamiltonian_action import HamiltonianAction
from worker.chemistry.sector_basis import state_from_bitstring_probabilities
from worker.chemistry.types import SKQDResult


def parse_bitstring_index(bitstring: object, *, num_qubits: int) -> int | None:
    """Parse a display bitstring into the little-endian basis index."""
    normalized = str(bitstring).replace(" ", "")
    if len(normalized) != num_qubits or any(char not in {"0", "1"} for char in normalized):
        return None

    basis_index = 0
    for qubit, char in enumerate(normalized[::-1]):
        if char == "1":
            basis_index |= 1 << qubit
    return basis_index


def matches_spin_sector(
    basis_index: int,
    *,
    norb: int,
    num_elec_a: int,
    num_elec_b: int,
) -> bool:
    """Return whether a basis index has the requested alpha/beta electron counts."""
    alpha_count = sum((basis_index >> orbital) & 1 for orbital in range(norb))
    beta_count = sum((basis_index >> (norb + orbital)) & 1 for orbital in range(norb))
    return alpha_count == num_elec_a and beta_count == num_elec_b


def resolve_sqd_electron_sector(package: dict[str, Any]) -> tuple[int, int] | None:
    """Resolve a valid-looking spin-resolved electron sector from an SQD package."""
    raw_nelec = package.get("nelec")
    if not isinstance(raw_nelec, list) or len(raw_nelec) != 2:
        return None
    resolved_nelec: list[int] = []
    for value in raw_nelec:
        if isinstance(value, bool):
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError, OverflowError):
            return None
        if not math.isfinite(numeric) or not numeric.is_integer():
            return None
        resolved_nelec.append(int(value))
    return resolved_nelec[0], resolved_nelec[1]


def seed_state_from_sqd_bitstrings(
    package: dict[str, Any],
    *,
    target_size: int,
    num_qubits: int,
    norb: int,
    num_elec_a: int,
    num_elec_b: int,
) -> np.ndarray | None:
    """Build a sector-correct superposition from SQD-selected bitstring weights."""
    raw_distribution = package.get("final_bitstring_probabilities")
    if not isinstance(raw_distribution, list):
        return None

    state = np.zeros(target_size, dtype=complex)
    for entry in raw_distribution:
        if not isinstance(entry, dict):
            continue
        probability = entry.get("probability")
        if isinstance(probability, bool) or not isinstance(probability, (int, float)):
            continue
        try:
            resolved_probability = float(probability)
        except (TypeError, ValueError, OverflowError):
            continue
        if not math.isfinite(resolved_probability) or resolved_probability <= 0.0:
            continue
        basis_index = parse_bitstring_index(entry.get("bitstring"), num_qubits=num_qubits)
        if basis_index is None or basis_index >= target_size:
            continue
        if not matches_spin_sector(
            basis_index,
            norb=norb,
            num_elec_a=num_elec_a,
            num_elec_b=num_elec_b,
        ):
            continue
        state[basis_index] += np.sqrt(resolved_probability)

    norm = float(np.linalg.norm(state))
    if np.isclose(norm, 0.0):
        return None
    return state / norm


def seed_state_from_sqd_result_with_source(
    sqd_result: SKQDResult | Any,
    *,
    target_size: int,
) -> tuple[np.ndarray | None, str]:
    """Build a Hilbert-space seed state from SQD bitstrings or occupancies."""
    package = getattr(sqd_result, "sci_result_package", None)
    if not isinstance(package, dict):
        return None, "unavailable"
    raw_occupancies = package.get("final_occupancies")
    if not isinstance(raw_occupancies, list) or not raw_occupancies:
        return None, "unavailable"

    try:
        occupancies = np.asarray(raw_occupancies, dtype=float).reshape(-1)
    except (TypeError, ValueError):
        return None, "invalid_occupancies"
    if not np.all(np.isfinite(occupancies)):
        return None, "invalid_occupancies"
    num_qubits = occupancies.size
    if target_size != 2**num_qubits:
        return None, "dimension_mismatch"

    electron_sector = resolve_sqd_electron_sector(package)
    if electron_sector is None:
        return None, "missing_electron_sector"
    num_elec_a, num_elec_b = electron_sector
    norb = num_qubits // 2
    if num_qubits != 2 * norb or num_elec_a < 0 or num_elec_b < 0:
        return None, "invalid_electron_sector"
    if num_elec_a > norb or num_elec_b > norb:
        return None, "invalid_electron_sector"

    bitstring_seed = seed_state_from_sqd_bitstrings(
        package,
        target_size=target_size,
        num_qubits=num_qubits,
        norb=norb,
        num_elec_a=num_elec_a,
        num_elec_b=num_elec_b,
    )
    if bitstring_seed is not None:
        return bitstring_seed, "sqd_bitstring_probabilities"

    alpha_occupancies = occupancies[:norb]
    beta_occupancies = occupancies[norb:]
    alpha_selected = (
        np.argsort(alpha_occupancies)[-num_elec_a:] if num_elec_a else np.array([], dtype=int)
    )
    beta_selected = (
        np.argsort(beta_occupancies)[-num_elec_b:] if num_elec_b else np.array([], dtype=int)
    )

    basis_index = 0
    for qubit_idx in alpha_selected:
        basis_index |= 1 << int(qubit_idx)
    for orbital_idx in beta_selected:
        basis_index |= 1 << int(norb + orbital_idx)

    state = np.zeros(target_size, dtype=complex)
    state[basis_index] = 1.0
    return state, "sqd_occupancies"


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
    """Build a fixed-sector seed state from SQD-selected bitstrings."""
    package = getattr(sqd_result, "sci_result_package", None)
    if not isinstance(package, dict):
        return None, "unavailable"

    distribution = package.get("final_bitstring_probabilities")
    if isinstance(distribution, list):
        state = state_from_bitstring_probabilities(
            distribution,
            norb=action.norb,
            nelec=action.nelec,
            dimension=action.dimension,
        )
        if state is not None:
            return state, "sqd_bitstring_probabilities"

    return None, "unavailable"


__all__ = [
    "matches_spin_sector",
    "parse_bitstring_index",
    "resolve_sqd_electron_sector",
    "seed_state_from_sqd_bitstrings",
    "seed_state_from_sqd_result",
    "seed_state_from_sqd_result_with_source",
    "sector_seed_state_from_sqd_result_with_source",
]
