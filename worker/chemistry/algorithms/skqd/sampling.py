"""Sample-based Krylov state preparation and determinant aggregation helpers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

from worker.chemistry.hamiltonian_action import HamiltonianAction
from worker.chemistry.sector_basis import address_to_bitstring
from worker.chemistry.state_vectors import normalize_state_vector
from worker.chemistry.time_evolution import (
    exact_time_evolution_state_from_spectrum,
    prepare_exact_time_evolution,
)


@dataclass(frozen=True)
class SKQDKrylovSample:
    """Samples and source metadata for one Krylov state."""

    krylov_index: int
    time_point: float
    bitstring_matrix: np.ndarray


@dataclass(frozen=True)
class SKQDSampleUnion:
    """All SKQD samples plus the merged determinant distribution."""

    samples_by_state: tuple[SKQDKrylovSample, ...]
    merged_bitstring_matrix: np.ndarray
    merged_probabilities: np.ndarray
    merged_counts: np.ndarray
    provenance: tuple[dict[str, Any], ...]


def _statevector_to_bitstring_matrix(
    state: np.ndarray,
    *,
    num_qubits: int,
    num_samples: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Draw computational-basis samples from a normalized statevector."""
    vector = normalize_state_vector(
        state,
        error_message="SKQD state source must be non-zero",
        expected_size=2**num_qubits,
    )
    probabilities = np.abs(vector) ** 2
    probabilities = np.asarray(probabilities / np.sum(probabilities), dtype=float)
    basis_indices = rng.choice(vector.size, size=num_samples, p=probabilities)
    bitstrings = np.zeros((num_samples, num_qubits), dtype=bool)
    for display_bit, qubit in enumerate(range(num_qubits - 1, -1, -1)):
        bitstrings[:, display_bit] = (basis_indices >> qubit) & 1
    return bitstrings


def sample_krylov_state_sources(
    state_source: Callable[[int, float], np.ndarray],
    *,
    num_states: int,
    time_step: float,
    samples_per_state: int,
    num_qubits: int,
    rng: np.random.Generator,
) -> SKQDSampleUnion:
    """Sample every requested Krylov source and retain per-state provenance."""
    if num_states < 1:
        raise ValueError("SKQD requires at least one Krylov state")
    if samples_per_state < 1:
        raise ValueError("SKQD samples_per_state must be positive")
    if num_qubits < 1:
        raise ValueError("SKQD num_qubits must be positive")

    samples_by_state: list[SKQDKrylovSample] = []
    for krylov_index in range(num_states):
        time_point = float(krylov_index * time_step)
        samples = _statevector_to_bitstring_matrix(
            state_source(krylov_index, time_point),
            num_qubits=num_qubits,
            num_samples=samples_per_state,
            rng=rng,
        )
        samples_by_state.append(
            SKQDKrylovSample(
                krylov_index=krylov_index,
                time_point=time_point,
                bitstring_matrix=samples,
            )
        )
    return merge_krylov_samples(samples_by_state)


def merge_krylov_samples(
    samples_by_state: list[SKQDKrylovSample] | tuple[SKQDKrylovSample, ...],
) -> SKQDSampleUnion:
    """Union shot-level samples while retaining their Krylov-state origin."""
    if not samples_by_state:
        raise ValueError("SKQD requires at least one sampled Krylov state")

    all_samples: list[np.ndarray] = []
    samples_per_state: list[int] = []
    for sample in samples_by_state:
        matrix = np.asarray(sample.bitstring_matrix, dtype=bool)
        if matrix.ndim != 2 or matrix.shape[0] == 0:
            raise ValueError("SKQD Krylov state has no samples")
        all_samples.append(matrix)
        samples_per_state.append(int(matrix.shape[0]))

    merged_samples = np.concatenate(all_samples, axis=0)
    unique_rows, inverse, counts = np.unique(
        merged_samples,
        axis=0,
        return_inverse=True,
        return_counts=True,
    )
    merged_probabilities = counts.astype(float) / float(merged_samples.shape[0])

    source_counts: list[dict[int, int]] = [dict() for _ in range(unique_rows.shape[0])]
    for sample_index, unique_index in enumerate(inverse):
        state_index = 0
        offset = sample_index
        for state_index, state_count in enumerate(samples_per_state):
            if offset < state_count:
                break
            offset -= state_count
        source_counts[int(unique_index)][state_index] = (
            source_counts[int(unique_index)].get(state_index, 0) + 1
        )
    provenance = tuple(
        {
            "bitstring": "".join("1" if bit else "0" for bit in row),
            "total_count": int(counts[row_index]),
            "probability": float(merged_probabilities[row_index]),
            "krylov_indices": sorted(source_counts[row_index]),
            "counts_by_krylov_index": {
                str(index): int(count)
                for index, count in sorted(source_counts[row_index].items())
            },
        }
        for row_index, row in enumerate(unique_rows)
    )
    return SKQDSampleUnion(
        samples_by_state=tuple(samples_by_state),
        merged_bitstring_matrix=unique_rows,
        merged_probabilities=merged_probabilities,
        merged_counts=counts,
        provenance=provenance,
    )


def sample_exact_krylov_states(
    operator: np.ndarray,
    reference_state: np.ndarray,
    *,
    num_states: int,
    time_step: float,
    samples_per_state: int,
    num_qubits: int,
    rng: np.random.Generator,
) -> SKQDSampleUnion:
    """Use exact matrix evolution as an explicitly labeled SKQD sample oracle."""
    reference = normalize_state_vector(
        reference_state,
        error_message="SKQD reference state must be non-zero",
        expected_size=2**num_qubits,
    )
    eigenvalues, eigenvectors = prepare_exact_time_evolution(operator)
    reference_projection = eigenvectors.conj().T @ reference

    def source(_krylov_index: int, time_point: float) -> np.ndarray:
        if np.isclose(time_point, 0.0):
            return reference
        return exact_time_evolution_state_from_spectrum(
            eigenvalues,
            eigenvectors,
            reference,
            time_step=time_point,
            state_projection=reference_projection,
        )

    return sample_krylov_state_sources(
        source,
        num_states=num_states,
        time_step=time_step,
        samples_per_state=samples_per_state,
        num_qubits=num_qubits,
        rng=rng,
    )


def sample_sector_krylov_states(
    action: HamiltonianAction,
    reference_state: np.ndarray,
    *,
    num_states: int,
    time_step: float,
    samples_per_state: int,
    rng: np.random.Generator,
) -> SKQDSampleUnion:
    """Sample exact fixed-sector Krylov states and encode determinant strings."""
    if num_states < 1:
        raise ValueError("SKQD requires at least one Krylov state")
    if samples_per_state < 1:
        raise ValueError("SKQD samples_per_state must be positive")

    reference = normalize_state_vector(
        reference_state,
        error_message="SKQD sector reference state must be non-zero",
        expected_size=action.dimension,
    )

    samples_by_state: list[SKQDKrylovSample] = []
    all_samples: list[np.ndarray] = []
    for krylov_index in range(num_states):
        time_point = float(krylov_index * time_step)
        state = (
            reference
            if np.isclose(time_point, 0.0)
            else action.time_evolve(reference, time_point=time_point)
        )
        probabilities = np.abs(state) ** 2
        probabilities = np.asarray(probabilities / np.sum(probabilities), dtype=float)
        addresses = rng.choice(action.dimension, size=samples_per_state, p=probabilities)
        samples = np.asarray(
            [
                [
                    character == "1"
                    for character in address_to_bitstring(
                        int(address), norb=action.norb, nelec=action.nelec
                    )
                ]
                for address in addresses
            ],
            dtype=bool,
        )
        samples_by_state.append(
            SKQDKrylovSample(
                krylov_index=krylov_index,
                time_point=time_point,
                bitstring_matrix=samples,
            )
        )
        all_samples.append(samples)

    merged_samples = np.concatenate(all_samples, axis=0)
    unique_rows, inverse, counts = np.unique(
        merged_samples,
        axis=0,
        return_inverse=True,
        return_counts=True,
    )
    merged_probabilities = counts.astype(float) / float(merged_samples.shape[0])
    source_counts: list[dict[int, int]] = [dict() for _ in range(unique_rows.shape[0])]
    for sample_index, unique_index in enumerate(inverse):
        state_index = sample_index // samples_per_state
        source_counts[int(unique_index)][state_index] = (
            source_counts[int(unique_index)].get(state_index, 0) + 1
        )
    provenance = tuple(
        {
            "bitstring": "".join("1" if bit else "0" for bit in row),
            "total_count": int(counts[row_index]),
            "probability": float(merged_probabilities[row_index]),
            "krylov_indices": sorted(source_counts[row_index]),
            "counts_by_krylov_index": {
                str(index): int(count)
                for index, count in sorted(source_counts[row_index].items())
            },
        }
        for row_index, row in enumerate(unique_rows)
    )
    return SKQDSampleUnion(
        samples_by_state=tuple(samples_by_state),
        merged_bitstring_matrix=unique_rows,
        merged_probabilities=merged_probabilities,
        merged_counts=counts,
        provenance=provenance,
    )


__all__ = [
    "SKQDKrylovSample",
    "SKQDSampleUnion",
    "merge_krylov_samples",
    "sample_exact_krylov_states",
    "sample_krylov_state_sources",
    "sample_sector_krylov_states",
]
