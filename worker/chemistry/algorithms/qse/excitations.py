"""Pure fermionic excitation helpers for the QSE algorithm."""

from __future__ import annotations

from collections.abc import Iterator
from itertools import combinations

import numpy as np


def apply_fermionic_ladder(
    basis_index: int,
    orbital: int,
    *,
    create: bool,
) -> tuple[int, int] | None:
    """Apply one Jordan-Wigner ladder operator to a computational basis index."""
    bit = 1 << orbital
    occupied = (basis_index & bit) != 0
    if create and occupied:
        return None
    if not create and not occupied:
        return None

    lower_occupancy = (basis_index & (bit - 1)).bit_count()
    sign = -1 if lower_occupancy % 2 else 1
    if create:
        return basis_index | bit, sign
    return basis_index & ~bit, sign


def apply_fermionic_excitation(
    reference_state: np.ndarray,
    *,
    create_orbitals: tuple[int, ...],
    annihilate_orbitals: tuple[int, ...],
    num_qubits: int,
) -> np.ndarray:
    """Apply a number-conserving fermionic excitation to a dense statevector."""
    result = np.zeros_like(reference_state, dtype=complex)
    # Operators act right-to-left: annihilate first, then create in reverse
    # order for a_p^† a_q^† a_s a_r style double excitations.
    operations = [(False, orbital) for orbital in annihilate_orbitals] + [
        (True, orbital) for orbital in reversed(create_orbitals)
    ]

    for basis_index, amplitude in enumerate(np.asarray(reference_state, dtype=complex)):
        if np.isclose(amplitude, 0.0):
            continue
        new_index = basis_index
        sign = 1
        valid = True
        for create, orbital in operations:
            if orbital < 0 or orbital >= num_qubits:
                valid = False
                break
            applied = apply_fermionic_ladder(new_index, orbital, create=create)
            if applied is None:
                valid = False
                break
            new_index, phase = applied
            sign *= phase
        if valid:
            result[new_index] += sign * amplitude

    return result


def fermionic_excitation_specs(
    num_qubits: int,
    *,
    excitation_level: str,
) -> Iterator[tuple[str, tuple[int, ...], tuple[int, ...]]]:
    """Return single and optional double excitation operator specifications."""
    orbitals = tuple(range(num_qubits))
    norb = num_qubits // 2 if num_qubits % 2 == 0 else None
    yield from single_excitation_specs(orbitals, norb=norb)
    if excitation_level == "singles_doubles":
        yield from double_excitation_specs(orbitals, norb=norb)


def single_excitation_specs(
    orbitals: tuple[int, ...],
    *,
    norb: int | None = None,
) -> Iterator[tuple[str, tuple[int, ...], tuple[int, ...]]]:
    """Yield every number-conserving single excitation specification."""
    for source in orbitals:
        for target in orbitals:
            if target == source:
                continue
            if norb is not None and not same_spin_count((target,), (source,), norb=norb):
                continue
            yield "single", (target,), (source,)


def double_excitation_specs(
    orbitals: tuple[int, ...],
    *,
    norb: int | None = None,
) -> Iterator[tuple[str, tuple[int, ...], tuple[int, ...]]]:
    """Yield every disjoint double excitation specification."""
    orbital_pairs = tuple(combinations(orbitals, 2))
    for sources in orbital_pairs:
        source_set = set(sources)
        for targets in orbital_pairs:
            if source_set.intersection(targets):
                continue
            if norb is not None and not same_spin_count(tuple(targets), tuple(sources), norb=norb):
                continue
            yield "double", tuple(targets), tuple(sources)


def build_sector_excitation_candidates(
    *,
    occupied: list[int],
    virtual: list[int],
    excitation_level: str,
    norb: int,
) -> list[tuple[str, tuple[int, ...], tuple[int, ...]]]:
    """Build spin-preserving single and optional double sector excitations."""
    candidates: list[tuple[str, tuple[int, ...], tuple[int, ...]]] = []
    if excitation_level == "singles_doubles":
        candidates.extend(
            ("double", tuple(targets), tuple(sources))
            for sources in combinations(occupied, 2)
            for targets in combinations(virtual, 2)
            if same_spin_count(tuple(targets), tuple(sources), norb=norb)
        )
    candidates.extend(
        ("single", (target,), (source,))
        for source in occupied
        for target in virtual
        if same_spin_count((target,), (source,), norb=norb)
    )
    return candidates


def same_spin_count(
    left: tuple[int, ...],
    right: tuple[int, ...],
    *,
    norb: int,
) -> bool:
    """Return whether two spin-orbital tuples preserve alpha/beta counts."""
    left_alpha = sum(1 for orbital in left if orbital < norb)
    right_alpha = sum(1 for orbital in right if orbital < norb)
    return left_alpha == right_alpha


__all__ = [
    "apply_fermionic_excitation",
    "apply_fermionic_ladder",
    "build_sector_excitation_candidates",
    "double_excitation_specs",
    "fermionic_excitation_specs",
    "same_spin_count",
    "single_excitation_specs",
]
