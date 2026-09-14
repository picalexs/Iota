"""Fixed-particle-sector helpers for chemistry solvers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import comb
from typing import Any

import numpy as np

ElectronSector = tuple[int, int]


def validate_sector(norb: int, nelec: ElectronSector) -> ElectronSector:
    """Validate and normalize a spin-resolved electron sector."""
    n_alpha, n_beta = int(nelec[0]), int(nelec[1])
    if norb < 1:
        raise ValueError("num_spatial_orbitals must be positive")
    if n_alpha < 0 or n_beta < 0 or n_alpha > norb or n_beta > norb:
        raise ValueError("electron counts must be between 0 and num_spatial_orbitals")
    return n_alpha, n_beta


def resolve_sector_metadata(hamiltonian: object) -> tuple[int, ElectronSector]:
    """Return ``(norb, (n_alpha, n_beta))`` from a Hamiltonian bundle-like object."""
    required = ("num_spatial_orbitals", "num_electrons_alpha", "num_electrons_beta")
    missing = [name for name in required if not hasattr(hamiltonian, name)]
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise ValueError(f"Hamiltonian sector metadata is missing: {missing_list}")

    norb = int(getattr(hamiltonian, "num_spatial_orbitals"))
    nelec = validate_sector(
        norb,
        (
            int(getattr(hamiltonian, "num_electrons_alpha")),
            int(getattr(hamiltonian, "num_electrons_beta")),
        ),
    )
    return norb, nelec


def sector_dimension(norb: int, nelec: ElectronSector) -> int:
    """Return the determinant-sector dimension C(norb, n_alpha) C(norb, n_beta)."""
    n_alpha, n_beta = validate_sector(norb, nelec)
    return comb(norb, n_alpha) * comb(norb, n_beta)


def _normalize_bitstring(bitstring: object, *, num_qubits: int) -> str:
    normalized = str(bitstring).replace(" ", "")
    if len(normalized) != num_qubits or any(char not in {"0", "1"} for char in normalized):
        raise ValueError("bitstring does not match the sector qubit width")
    return normalized


def bitstring_to_address(bitstring: object, *, norb: int, nelec: ElectronSector) -> int:
    """Map a display bitstring to its ffsim sector address."""
    import ffsim

    normalized = _normalize_bitstring(bitstring, num_qubits=2 * norb)
    addresses = ffsim.strings_to_addresses([normalized], norb, validate_sector(norb, nelec))
    if len(addresses) != 1:
        raise ValueError("bitstring did not resolve to exactly one sector address")
    return int(addresses[0])


def address_to_bitstring(address: int, *, norb: int, nelec: ElectronSector) -> str:
    """Map a ffsim sector address to the app's display bitstring convention."""
    import ffsim

    dimension = sector_dimension(norb, nelec)
    if address < 0 or address >= dimension:
        raise ValueError("sector address is out of range")
    values = ffsim.addresses_to_strings(
        [int(address)],
        norb,
        validate_sector(norb, nelec),
        concatenate=True,
    )
    if values is None or len(values) != 1:
        raise ValueError("sector address did not resolve to exactly one bitstring")
    value = values[0]
    return format(int(value), f"0{2 * norb}b")


def display_bitstring_to_basis_index(bitstring: object, *, num_qubits: int) -> int:
    """Parse a display bitstring into the little-endian computational basis index."""
    return int(_normalize_bitstring(bitstring, num_qubits=num_qubits), 2)


def hartree_fock_sector_state(norb: int, nelec: ElectronSector) -> np.ndarray:
    """Return the Hartree-Fock determinant as a normalized sector vector."""
    import ffsim

    return np.asarray(ffsim.hartree_fock_state(norb, validate_sector(norb, nelec)), dtype=complex)


def state_from_bitstring_probabilities(
    distribution: Sequence[Mapping[str, Any]] | None,
    *,
    norb: int,
    nelec: ElectronSector,
    dimension: int | None = None,
) -> np.ndarray | None:
    """Build a normalized sector vector from weighted determinant bitstrings."""
    if not distribution:
        return None

    target_dimension = sector_dimension(norb, nelec) if dimension is None else int(dimension)
    state = np.zeros(target_dimension, dtype=complex)
    for entry in distribution:
        probability = entry.get("probability")
        if not isinstance(probability, (int, float)) or float(probability) <= 0.0:
            continue
        try:
            address = bitstring_to_address(entry.get("bitstring"), norb=norb, nelec=nelec)
        except ValueError:
            continue
        if address < target_dimension:
            state[address] += np.sqrt(float(probability))

    norm = float(np.linalg.norm(state))
    if np.isclose(norm, 0.0):
        return None
    return state / norm


def _parse_amplitude(value: object) -> complex:
    if isinstance(value, complex):
        return value
    if isinstance(value, (int, float)):
        return complex(float(value), 0.0)
    if isinstance(value, Mapping):
        real = value.get("real", 0.0)
        imag = value.get("imag", value.get("imaginary", 0.0))
        if isinstance(real, (int, float)) and isinstance(imag, (int, float)):
            return complex(float(real), float(imag))
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and len(value) == 2:
        real, imag = value
        if isinstance(real, (int, float)) and isinstance(imag, (int, float)):
            return complex(float(real), float(imag))
    raise ValueError("sector amplitudes must be numeric or real/imag pairs")


def state_from_sector_amplitudes(
    amplitudes: Sequence[Mapping[str, Any]] | None,
    *,
    norb: int,
    nelec: ElectronSector,
    dimension: int | None = None,
) -> np.ndarray:
    """Build a normalized sector vector from sparse determinant amplitudes."""
    if not amplitudes:
        raise ValueError("provided_sector reference requires at least one amplitude")

    target_dimension = sector_dimension(norb, nelec) if dimension is None else int(dimension)
    state = np.zeros(target_dimension, dtype=complex)
    for entry in amplitudes:
        if not isinstance(entry, Mapping):
            raise ValueError("provided_sector amplitudes must be objects")
        address = bitstring_to_address(entry.get("bitstring"), norb=norb, nelec=nelec)
        if address >= target_dimension:
            raise ValueError("provided_sector bitstring resolved outside sector dimension")
        state[address] += _parse_amplitude(entry.get("amplitude"))

    norm = float(np.linalg.norm(state))
    if np.isclose(norm, 0.0):
        raise ValueError("provided_sector amplitudes have zero norm")
    return state / norm


def largest_sector_bitstring_distribution(
    state: np.ndarray | None,
    *,
    norb: int,
    nelec: ElectronSector,
    max_entries: int = 32,
) -> list[dict[str, float | str]]:
    """Return the largest determinant probabilities from a sector vector."""
    if state is None:
        return []
    vector = np.asarray(state, dtype=complex).reshape(-1)
    if vector.size != sector_dimension(norb, nelec):
        return []

    probabilities = np.abs(vector) ** 2
    order = np.argsort(probabilities)[::-1]
    distribution: list[dict[str, float | str]] = []
    for address in order[:max_entries]:
        probability = float(probabilities[address])
        if probability <= 1e-12:
            break
        distribution.append(
            {
                "bitstring": address_to_bitstring(int(address), norb=norb, nelec=nelec),
                "probability": round(probability, 12),
            }
        )
    return distribution


def _apply_fermionic_ladder_to_index(
    basis_index: int,
    orbital: int,
    *,
    create: bool,
) -> tuple[int, int] | None:
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


def apply_fermionic_excitation_sector(
    reference_state: np.ndarray,
    *,
    create_orbitals: tuple[int, ...],
    annihilate_orbitals: tuple[int, ...],
    norb: int,
    nelec: ElectronSector,
) -> np.ndarray:
    """Apply a number-conserving fermionic excitation in the fixed sector."""
    num_qubits = 2 * norb
    dimension = sector_dimension(norb, nelec)
    vector = np.asarray(reference_state, dtype=complex).reshape(-1)
    if vector.size != dimension:
        raise ValueError("reference_state size does not match the sector dimension")

    result = np.zeros_like(vector, dtype=complex)
    operations = [(False, orbital) for orbital in annihilate_orbitals] + [
        (True, orbital) for orbital in reversed(create_orbitals)
    ]

    for address in np.flatnonzero(np.abs(vector) > 1e-14):
        basis_index = display_bitstring_to_basis_index(
            address_to_bitstring(int(address), norb=norb, nelec=nelec),
            num_qubits=num_qubits,
        )
        new_index = basis_index
        sign = 1
        valid = True
        for create, orbital in operations:
            if orbital < 0 or orbital >= num_qubits:
                valid = False
                break
            applied = _apply_fermionic_ladder_to_index(new_index, orbital, create=create)
            if applied is None:
                valid = False
                break
            new_index, phase = applied
            sign *= phase
        if not valid:
            continue
        try:
            new_address = bitstring_to_address(
                format(new_index, f"0{num_qubits}b"),
                norb=norb,
                nelec=nelec,
            )
        except ValueError:
            continue
        result[new_address] += sign * vector[address]

    return result
