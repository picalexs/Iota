"""SQD Hartree-Fock sampling and recovery-input preparation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol

import numpy as np

from worker.chemistry.algorithms.sqd.config import SQDOptions
from worker.chemistry.algorithms.sqd.recovery import SQDDependencies
from worker.chemistry.algorithms.sqd.sampling import (
    aggregate_bitstring_frequencies,
    aggregate_weighted_bitstring_probabilities,
    bitstrings_to_matrix,
    extract_sampler_bitstrings,
    summarize_bitstring_distribution,
)
from worker.chemistry.progress import ProgressCallback


class SamplerBackend(Protocol):
    """Protocol for sampler-like backends used by SQD."""

    def run(self, *args: Any, **kwargs: Any) -> Any: ...


@dataclass
class SQDIterationSampling:
    """Intermediate sampling and postselection outputs for one SQD iteration."""

    raw_bitstring_matrix: np.ndarray
    bitstring_matrix: np.ndarray
    bitstring_counts: np.ndarray
    probabilities: np.ndarray
    accepted_bits: np.ndarray
    accepted_probs: np.ndarray
    invalid_bits: np.ndarray
    invalid_probs: np.ndarray
    recovered_bits: np.ndarray
    recovered_probs: np.ndarray
    postselection_weight: float
    selected_bits: np.ndarray
    selected_probs: np.ndarray
    last_sampled_distribution: list[dict[str, Any]]
    raw_distribution: list[dict[str, Any]]
    accepted_distribution: list[dict[str, Any]]
    invalid_distribution: list[dict[str, Any]]
    recovered_distribution: list[dict[str, Any]]
    last_selected_distribution: list[dict[str, Any]]
    selected_distribution: list[dict[str, Any]]
    recovery_applied: bool
    first_solve_source: str
    sampled_circuit: Any | None


def build_hf_reference_circuit(
    num_bits: int,
    *,
    num_elec_a: int,
    num_elec_b: int,
    rng: np.random.Generator | None = None,
) -> Any:
    """Build a Hartree-Fock reference circuit for SQD sampling.

    Qubit ordering follows the ffsim Jordan-Wigner convention:
      qubits 0..norb-1      → alpha spin-orbitals
      qubits norb..2*norb-1 → beta spin-orbitals

    Qiskit returns measured bitstrings from the highest classical bit to the
    lowest one. With alpha orbitals on low-index qubits and beta orbitals on
    high-index qubits, those strings match qiskit-addon-sqd's
    ``[beta ...][alpha ...]`` right/left convention.

    The circuit places X gates on the lowest num_elec_a alpha orbitals and the
    lowest num_elec_b beta orbitals, producing the HF Slater determinant. The
    optional ``rng`` argument remains for caller compatibility. It does not
    modify this circuit because independent single-qubit rotations do not
    preserve the target particle-number sector. A correlated sampling state
    must be supplied through a separate state-preparation path.
    """
    from qiskit import QuantumCircuit

    del rng
    norb = num_bits // 2
    circuit = QuantumCircuit(num_bits, num_bits)
    for i in range(min(num_elec_a, norb)):
        circuit.x(i)
    for i in range(min(num_elec_b, norb)):
        circuit.x(norb + i)

    circuit.measure(range(num_bits), range(num_bits))
    return circuit


def _run_sampler_attempt(
    sampler: SamplerBackend,
    circuit: Any,
    *,
    shots: int,
) -> Any:
    """Execute one sampler attempt and return the primitive result object."""
    job = sampler.run([(circuit,)], shots=shots)
    return job.result()


def _is_control_flow_exception(exc: Exception) -> bool:
    """Preserve run-control signals instead of retrying sampler submissions."""
    return exc.__class__.__name__ in {"_RunCancelled", "_RunPaused"}


def _ensure_measurements(circuit: Any, *, num_bits: int) -> Any:
    """Return a copy of a supplied circuit with one measured bit per qubit."""
    from qiskit import QuantumCircuit

    if circuit is None or not hasattr(circuit, "num_qubits"):
        raise ValueError("SQD sampling circuit factory must return a quantum circuit")
    if int(circuit.num_qubits) != num_bits:
        raise ValueError("SQD sampling circuit width must match the Hamiltonian qubits")

    if int(getattr(circuit, "num_clbits", 0)) == 0:
        measured = QuantumCircuit(num_bits, num_bits)
        measured.compose(circuit, qubits=range(num_bits), inplace=True)
    elif int(circuit.num_clbits) < num_bits:
        raise ValueError("SQD sampling circuit needs at least one classical bit per qubit")
    else:
        measured = circuit.copy()

    has_measurement = any(instruction.operation.name == "measure" for instruction in measured.data)
    if not has_measurement:
        measured.measure(range(num_bits), range(num_bits))
    return measured


def sample_bitstring_matrix(
    backend: Any,
    *,
    num_bits: int,
    total_samples: int,
    num_elec_a: int = 0,
    num_elec_b: int = 0,
    rng: np.random.Generator | None = None,
    sampling_circuit_factory: Callable[..., Any] | None = None,
    return_circuit: bool = False,
) -> np.ndarray | tuple[np.ndarray, Any]:
    """Sample backend bitstrings from HF or a supplied preparation circuit."""
    if not hasattr(backend, "run"):
        raise ValueError("SQD backend must expose a sampler run() method")
    sampler = backend  # Structural SamplerBackend protocol keeps runtime types local.

    if sampling_circuit_factory is None:
        circuit = build_hf_reference_circuit(
            num_bits, num_elec_a=num_elec_a, num_elec_b=num_elec_b, rng=rng
        )
    else:
        circuit = sampling_circuit_factory(
            num_bits=num_bits,
            num_elec_a=num_elec_a,
            num_elec_b=num_elec_b,
            rng=rng,
        )
        circuit = _ensure_measurements(circuit, num_bits=num_bits)

    last_error: Exception | None = None
    for multiplier in (1, 2, 4):
        try:
            result = _run_sampler_attempt(
                sampler,
                circuit,
                shots=max(total_samples * multiplier, 1),
            )
        except Exception as exc:  # pragma: no cover - depends on backend primitive failures
            if _is_control_flow_exception(exc):
                raise
            last_error = exc
            continue

        bitstrings = extract_sampler_bitstrings(result)
        if bitstrings is None:
            continue

        matrix = bitstrings_to_matrix(bitstrings, num_bits=num_bits)
        return (matrix, circuit) if return_circuit else matrix

    if last_error is not None:
        raise RuntimeError("SQD sampler failed to return measurement results") from last_error
    raise RuntimeError("SQD sampler returned no measurement bitstrings")


def _recover_invalid_configurations(
    *,
    iteration: int,
    raw_invalid_bits: np.ndarray,
    raw_invalid_probs: np.ndarray,
    raw_invalid_mass: float,
    avg_occupancies: tuple[np.ndarray, np.ndarray] | None,
    options: SQDOptions,
    rng: np.random.Generator,
    deps: SQDDependencies,
) -> tuple[np.ndarray, np.ndarray, bool]:
    empty_bits = np.empty((0, raw_invalid_bits.shape[1]), dtype=bool)
    empty_probs = np.empty(0, dtype=float)
    if iteration == 1 or raw_invalid_bits.shape[0] == 0:
        return empty_bits, empty_probs, False
    if avg_occupancies is None:
        raise ValueError("SQD recovery needs occupations from the preceding selected-CI solve")
    recovered_bits, recovered_probs = deps.recover_configurations(
        raw_invalid_bits,
        raw_invalid_probs,
        avg_occupancies=avg_occupancies,
        num_elec_a=options.num_elec_a,
        num_elec_b=options.num_elec_b,
        rand_seed=rng,
    )
    if recovered_bits.shape[0] == 0:
        return empty_bits, empty_probs, False
    recovered_bits, recovered_probs = deps.postselect_by_hamming_right_and_left(
        recovered_bits,
        np.asarray(recovered_probs, dtype=float).copy(),
        hamming_right=options.num_elec_a,
        hamming_left=options.num_elec_b,
    )
    if recovered_bits.shape[0] == 0:
        return empty_bits, empty_probs, False
    return recovered_bits, np.asarray(recovered_probs, dtype=float) * raw_invalid_mass, True


def _combine_sqd_configurations(
    raw_valid_bits: np.ndarray,
    raw_valid_probs: np.ndarray,
    recovered_bits: np.ndarray,
    recovered_probs: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    bit_parts = []
    probability_parts = []
    if raw_valid_bits.shape[0] > 0:
        bit_parts.append(raw_valid_bits)
        probability_parts.append(raw_valid_probs)
    if recovered_bits.shape[0] > 0:
        bit_parts.append(recovered_bits)
        probability_parts.append(recovered_probs)
    if not bit_parts:
        raise ValueError("SQD produced no valid configurations for selected-CI")
    return aggregate_weighted_bitstring_probabilities(
        np.concatenate(bit_parts, axis=0),
        np.concatenate(probability_parts, axis=0),
    )


def _first_solve_source(iteration: int, recovery_applied: bool) -> str:
    if iteration == 1:
        return "raw_valid_sector"
    return "raw_valid_sector_plus_recovered_invalid" if recovery_applied else "raw_valid_sector_only"


def run_sqd_sampling_iteration(
    *,
    iteration: int,
    backend: object,
    deps: SQDDependencies,
    options: SQDOptions,
    rng: np.random.Generator,
    avg_occupancies: tuple[np.ndarray, np.ndarray] | None,
    progress_callback: ProgressCallback | None,
    sample_bitstrings: Callable[..., np.ndarray | tuple[np.ndarray, Any]],
    sampling_circuit_factory: Callable[..., Any] | None = None,
) -> SQDIterationSampling:
    """Sample, solve raw valid rows, then recover only later invalid rows."""
    if progress_callback is not None:
        progress_callback(
            {
                "algorithm": "sqd",
                "stage": "progress",
                "step": "sampling",
                "iteration": iteration,
                "completed_iterations": iteration - 1,
                "total_iterations": options.max_iterations,
                "energy": None,
                "samples_per_batch": options.samples_per_batch,
                "num_batches": options.num_batches,
                "total_samples": options.total_samples,
                "selected_ci_max_dim": list(options.selected_ci_limits),
                "selected_ci_max_dim_source": options.selected_ci_limit_summary["max_dim_source"],
            }
        )

    sample_kwargs: dict[str, Any] = {
        "num_bits": 2 * options.norb,
        "total_samples": options.total_samples,
        "num_elec_a": options.num_elec_a,
        "num_elec_b": options.num_elec_b,
        "rng": rng,
        "return_circuit": True,
    }
    if sampling_circuit_factory is not None:
        sample_kwargs["sampling_circuit_factory"] = sampling_circuit_factory
    sampled_output = sample_bitstrings(backend, **sample_kwargs)
    if isinstance(sampled_output, tuple):
        raw_bitstring_matrix, sampled_circuit = sampled_output
    else:  # pragma: no cover - compatibility fallback for monkeypatched tests
        raw_bitstring_matrix = sampled_output
        sampled_circuit = None

    bitstring_matrix, probabilities, bitstring_counts = aggregate_bitstring_frequencies(
        raw_bitstring_matrix
    )
    last_sampled_distribution = summarize_bitstring_distribution(
        bitstring_matrix,
        probabilities,
        counts=bitstring_counts,
    )
    raw_distribution = summarize_bitstring_distribution(
        bitstring_matrix,
        probabilities,
        counts=bitstring_counts,
        limit=None,
    )

    norb = bitstring_matrix.shape[1] // 2
    valid_mask = np.logical_and(
        np.sum(bitstring_matrix[:, norb:], axis=1) == options.num_elec_a,
        np.sum(bitstring_matrix[:, :norb], axis=1) == options.num_elec_b,
    )
    raw_valid_bits = bitstring_matrix[valid_mask]
    raw_valid_probs = probabilities[valid_mask]
    raw_invalid_bits = bitstring_matrix[~valid_mask]
    raw_invalid_probs = probabilities[~valid_mask]
    raw_valid_mass = float(np.sum(raw_valid_probs))
    raw_invalid_mass = float(np.sum(raw_invalid_probs))

    accepted_bits = np.empty((0, bitstring_matrix.shape[1]), dtype=bool)
    accepted_probs = np.empty(0, dtype=float)
    if raw_valid_bits.shape[0] > 0:
        # The first selected-CI solve must see only rows that were valid before
        # recovery. The addon call only normalizes this already-valid subset.
        accepted_bits, accepted_probs = deps.postselect_by_hamming_right_and_left(
            raw_valid_bits,
            raw_valid_probs.copy(),
            hamming_right=options.num_elec_a,
            hamming_left=options.num_elec_b,
        )

    recovered_bits, recovered_probs, recovery_applied = _recover_invalid_configurations(
        iteration=iteration,
        raw_invalid_bits=raw_invalid_bits,
        raw_invalid_probs=raw_invalid_probs,
        raw_invalid_mass=raw_invalid_mass,
        avg_occupancies=avg_occupancies,
        options=options,
        rng=rng,
        deps=deps,
    )

    if iteration == 1 and raw_valid_bits.shape[0] == 0:
        raise ValueError(
            "SQD first iteration produced no raw valid-sector configurations; increase the sample budget"
        )

    combined_bits, combined_probs = _combine_sqd_configurations(
        raw_valid_bits,
        raw_valid_probs,
        recovered_bits,
        recovered_probs,
    )

    selected_bits, selected_probs = deps.postselect_by_hamming_right_and_left(
        combined_bits,
        combined_probs.copy(),
        hamming_right=options.num_elec_a,
        hamming_left=options.num_elec_b,
    )
    if selected_bits.size == 0:
        raise ValueError("SQD postselection yielded no valid bitstrings")

    if progress_callback is not None:
        progress_callback(
            {
                "algorithm": "sqd",
                "stage": "progress",
                "step": "postselection",
                "iteration": iteration,
                "completed_iterations": iteration - 1,
                "total_iterations": options.max_iterations,
                "energy": None,
                "selected_samples": int(selected_bits.shape[0]),
                "postselection_weight": round(raw_valid_mass, 8),
                "sampled_configurations": int(bitstring_matrix.shape[0]),
                "raw_valid_configurations": int(raw_valid_bits.shape[0]),
                "recovered_configurations": int(recovered_bits.shape[0]),
            }
        )

    return SQDIterationSampling(
        raw_bitstring_matrix=raw_bitstring_matrix,
        bitstring_matrix=bitstring_matrix,
        bitstring_counts=bitstring_counts,
        probabilities=probabilities,
        accepted_bits=accepted_bits,
        accepted_probs=accepted_probs,
        invalid_bits=raw_invalid_bits,
        invalid_probs=raw_invalid_probs,
        recovered_bits=recovered_bits,
        recovered_probs=recovered_probs,
        postselection_weight=raw_valid_mass,
        selected_bits=selected_bits,
        selected_probs=selected_probs,
        last_sampled_distribution=last_sampled_distribution,
        raw_distribution=raw_distribution,
        accepted_distribution=summarize_bitstring_distribution(
            accepted_bits,
            accepted_probs,
            limit=None,
        ),
        invalid_distribution=summarize_bitstring_distribution(
            raw_invalid_bits,
            raw_invalid_probs,
            limit=None,
        ),
        recovered_distribution=summarize_bitstring_distribution(
            recovered_bits,
            recovered_probs,
            limit=None,
        ),
        last_selected_distribution=summarize_bitstring_distribution(
            selected_bits,
            selected_probs,
        ),
        selected_distribution=summarize_bitstring_distribution(
            selected_bits,
            selected_probs,
            limit=None,
        ),
        recovery_applied=recovery_applied,
        first_solve_source=_first_solve_source(iteration, recovery_applied),
        sampled_circuit=sampled_circuit,
    )


__all__ = [
    "SQDIterationSampling",
    "SamplerBackend",
    "build_hf_reference_circuit",
    "run_sqd_sampling_iteration",
    "sample_bitstring_matrix",
]
