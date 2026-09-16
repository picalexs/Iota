"""Hardware-oriented projected matrix element helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from qiskit.quantum_info import SparsePauliOp

from worker.chemistry.eigensolver import solve_stabilized_generalized_eigenproblem
from worker.chemistry.matrix_element_circuits import (
    augment_system_observable as _augment_system_observable,
)
from worker.chemistry.matrix_element_circuits import (
    build_branch_state_circuit as _build_branch_state_circuit,
)
from worker.chemistry.progress import ProgressCallback
from worker.chemistry.projected_subspace import projected_matrix_converged

_MAX_HARDWARE_PROJECTED_DIM = 8
_ESTIMATOR_PUB_CHUNK_SIZE = 4
_AER_ESTIMATOR_PUB_CHUNK_SIZE = 2
_NOISY_AER_ESTIMATOR_PUB_CHUNK_SIZE = 4
_STANDARD_ERROR_COMPATIBILITY = {
    "definition": "legacy_max_across_hamiltonian_and_overlap_entries",
    "units": "mixed_hamiltonian_energy_and_dimensionless_overlap",
    "deprecated": True,
}
_STANDARD_ERROR_UNITS = {
    "max_hamiltonian_standard_error": "hamiltonian_energy_units",
    "max_overlap_standard_error": "dimensionless",
    "max_standard_error": "mixed_hamiltonian_energy_and_dimensionless_overlap",
}


@dataclass(frozen=True)
class MatrixElementEstimate:
    """Projected matrices estimated from branch-state expectation values."""

    projected_hamiltonian: np.ndarray
    overlap: np.ndarray
    summary: dict[str, Any]


def _estimator_pub_chunk_size(backend_context: Any | None) -> int:
    """Return a conservative PUB chunk size for the selected execution path."""
    backend_target = getattr(backend_context, "backend_target", None)
    if backend_target != "aer_simulator":
        return _ESTIMATOR_PUB_CHUNK_SIZE
    configured = _configured_aer_pub_chunk_size(backend_context)
    if configured is not None:
        return configured
    if getattr(backend_context, "noise_profile", None) is not None:
        return _NOISY_AER_ESTIMATOR_PUB_CHUNK_SIZE
    return _AER_ESTIMATOR_PUB_CHUNK_SIZE


def _configured_aer_pub_chunk_size(backend_context: Any | None) -> int | None:
    """Read an optional, bounded Aer PUB batch size from the run context."""
    options = getattr(backend_context, "backend_options", None)
    if not isinstance(options, dict):
        return None
    value = options.get("aer_pub_chunk_size")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return max(1, min(int(value), 32))


def estimate_projected_matrices_with_branch_estimator(
    *,
    hamiltonian: object,
    estimator: Any,
    time_points: list[float],
    trotter_steps: int,
    algorithm: str,
    backend_context: Any | None = None,
    progress_callback: ProgressCallback | None = None,
) -> MatrixElementEstimate:
    """Estimate projected H/S matrices with branch-state Estimator PUBs.

    For basis states ``|phi_i> = U(t_i)|psi0>`` and ``|phi_j> = U(t_j)|psi0>``,
    the circuit prepares ``(|0>|phi_i> + |1>|phi_j>) / sqrt(2)``. Estimating
    ``X/Y`` on the branch ancilla gives the real and imaginary transition
    matrix elements for both the identity overlap and Hamiltonian observables.
    """
    pauli_hamiltonian = _resolve_pauli_hamiltonian(hamiltonian)
    num_qubits = _resolve_num_qubits(hamiltonian, pauli_hamiltonian)
    dimension = len(time_points)
    _validate_branch_estimator_inputs(
        estimator=estimator,
        trotter_steps=trotter_steps,
        dimension=dimension,
    )
    observables = _build_branch_observables(
        pauli_hamiltonian=pauli_hamiltonian,
        num_qubits=num_qubits,
    )
    pairs = [(row, col) for row in range(dimension) for col in range(row, dimension)]
    _emit_branch_estimator_status(
        progress_callback=progress_callback,
        algorithm=algorithm,
        pairs=pairs,
        dimension=dimension,
        pauli_terms=len(pauli_hamiltonian),
        trotter_steps=trotter_steps,
        status="preparing_branch_circuits",
    )
    pubs = _build_branch_estimator_pubs(
        hamiltonian=hamiltonian,
        pauli_hamiltonian=pauli_hamiltonian,
        num_qubits=num_qubits,
        observables=observables,
        time_points=time_points,
        trotter_steps=trotter_steps,
        pairs=pairs,
        backend_context=backend_context,
    )
    _emit_branch_estimator_status(
        progress_callback=progress_callback,
        algorithm=algorithm,
        pairs=pairs,
        dimension=dimension,
        pauli_terms=len(pauli_hamiltonian),
        trotter_steps=trotter_steps,
        status="branch_circuits_ready",
        estimator_pub_count=len(pubs),
    )

    projected = np.empty((dimension, dimension), dtype=complex)
    overlap = np.empty((dimension, dimension), dtype=complex)
    # ``None`` means that the primitive did not provide uncertainty data.
    # It must not be treated as zero uncertainty by the projected solver.
    max_hamiltonian_standard_error: float | None = None
    max_overlap_standard_error: float | None = None
    max_standard_error: float | None = None
    chunk_size = _estimator_pub_chunk_size(backend_context)

    completed = 0
    primitive_run_calls = 0
    primitive_successful_runs = 0
    for chunk_start in range(0, len(pubs), chunk_size):
        chunk_end = min(chunk_start + chunk_size, len(pubs))
        primitive_run_calls += 1
        (
            max_hamiltonian_standard_error,
            max_overlap_standard_error,
            max_standard_error,
            completed,
        ) = _accumulate_matrix_element_chunk(
            estimator=estimator,
            pubs=pubs,
            pairs=pairs,
            projected=projected,
            overlap=overlap,
            algorithm=algorithm,
            dimension=dimension,
            progress_callback=progress_callback,
            chunk_start=chunk_start,
            chunk_end=chunk_end,
            completed=completed,
            max_hamiltonian_standard_error=max_hamiltonian_standard_error,
            max_overlap_standard_error=max_overlap_standard_error,
            max_standard_error=max_standard_error,
        )
        primitive_successful_runs += 1

    projected = _hermitian_symmetrized(projected)
    overlap = _hermitian_symmetrized(overlap)
    # Each branch state is normalized, so S_ii is a structural identity.
    # Enforce it after measurement and Hermitian symmetrization.
    overlap[np.diag_indices_from(overlap)] = 1.0

    summary = _build_branch_estimator_summary(
        pubs=pubs,
        observables=observables,
        pauli_hamiltonian=pauli_hamiltonian,
        trotter_steps=trotter_steps,
        time_points=time_points,
        dimension=dimension,
        max_hamiltonian_standard_error=max_hamiltonian_standard_error,
        max_overlap_standard_error=max_overlap_standard_error,
        max_standard_error=max_standard_error,
        backend_context=backend_context,
        estimator_pub_chunk_size=chunk_size,
        overlap_diagonal_normalized=True,
        primitive_run_calls=primitive_run_calls,
        primitive_successful_runs=primitive_successful_runs,
    )
    return MatrixElementEstimate(projected, overlap, summary)


def _validate_branch_estimator_inputs(
    *,
    estimator: Any,
    trotter_steps: int,
    dimension: int,
) -> None:
    """Validate basic branch-estimator execution constraints."""
    if not hasattr(estimator, "run"):
        raise ValueError("Hardware matrix-element workflow requires an EstimatorV2 backend")
    if trotter_steps < 1:
        raise ValueError("trotter_steps must be positive")
    if dimension < 1:
        raise ValueError("time_points must contain at least one entry")
    if dimension > _MAX_HARDWARE_PROJECTED_DIM:
        raise ValueError(
            f"Hardware matrix-element workflow is capped at {_MAX_HARDWARE_PROJECTED_DIM} "
            "basis states per run"
        )


def _build_branch_observables(
    *,
    pauli_hamiltonian: SparsePauliOp,
    num_qubits: int,
) -> list[SparsePauliOp]:
    """Build the branch-ancilla observables used for H/S estimation."""
    x_hamiltonian = _augment_system_observable(pauli_hamiltonian, "X")
    y_hamiltonian = _augment_system_observable(pauli_hamiltonian, "Y")
    x_overlap = SparsePauliOp.from_list([("X" + "I" * num_qubits, 1.0)])
    y_overlap = SparsePauliOp.from_list([("Y" + "I" * num_qubits, 1.0)])
    return [x_hamiltonian, y_hamiltonian, x_overlap, y_overlap]


def _emit_branch_estimator_status(
    *,
    progress_callback: ProgressCallback | None,
    algorithm: str,
    pairs: list[tuple[int, int]],
    dimension: int,
    pauli_terms: int,
    trotter_steps: int,
    status: str,
    estimator_pub_count: int | None = None,
) -> None:
    """Emit setup-stage progress for branch-estimator execution."""
    if progress_callback is None:
        return
    progress_callback(
        {
            "algorithm": algorithm,
            "stage": "progress",
            "step": "hardware_matrix_elements",
            "iteration": 0,
            "completed_iterations": 0,
            "total_iterations": len(pairs),
            "energy": None,
            "matrix_element_strategy": "branch_estimator",
            "estimator_pub_count": len(pairs)
            if estimator_pub_count is None
            else estimator_pub_count,
            "basis_dimension": dimension,
            "pauli_terms": pauli_terms,
            "trotter_steps": trotter_steps,
            "status": status,
        }
    )


def _build_branch_estimator_pubs(
    *,
    hamiltonian: object,
    pauli_hamiltonian: SparsePauliOp,
    num_qubits: int,
    observables: list[SparsePauliOp],
    time_points: list[float],
    trotter_steps: int,
    pairs: list[tuple[int, int]],
    backend_context: Any | None,
) -> list[tuple[Any, list[SparsePauliOp]]]:
    """Build Estimator PUBs for each upper-triangular projected basis pair."""
    pubs: list[tuple[Any, list[SparsePauliOp]]] = []
    for row, col in pairs:
        circuit = _build_branch_state_circuit(
            hamiltonian=hamiltonian,
            pauli_hamiltonian=pauli_hamiltonian,
            num_qubits=num_qubits,
            left_time=time_points[row],
            right_time=time_points[col],
            trotter_steps=trotter_steps,
        )
        # The Aer adapter transpiles and applies the final layout immediately
        # before primitive submission. Avoid a second, uncached transpilation
        # while keeping logical circuits reusable for PUB batching.
        pubs.append((circuit, observables))
    return pubs


def _accumulate_matrix_element_chunk(
    *,
    estimator: Any,
    pubs: list[tuple[Any, list[SparsePauliOp]]],
    pairs: list[tuple[int, int]],
    projected: np.ndarray,
    overlap: np.ndarray,
    algorithm: str,
    dimension: int,
    progress_callback: ProgressCallback | None,
    chunk_start: int,
    chunk_end: int,
    completed: int,
    max_hamiltonian_standard_error: float | None,
    max_overlap_standard_error: float | None,
    max_standard_error: float | None,
) -> tuple[float | None, float | None, float | None, int]:
    """Run one Estimator chunk and merge its values into the projected matrices."""
    estimator_pub_chunk = [chunk_start + 1, chunk_end]
    _emit_branch_chunk_start(
        progress_callback=progress_callback,
        algorithm=algorithm,
        completed=completed,
        total_iterations=len(pairs),
        dimension=dimension,
        estimator_pub_chunk=estimator_pub_chunk,
        estimator_pub_count=len(pubs),
    )
    chunk_result = estimator.run(pubs[chunk_start:chunk_end]).result()
    _validate_chunk_result_count(chunk_result=chunk_result, expected_count=chunk_end - chunk_start)
    for local_index, pub_result in enumerate(chunk_result):
        index = chunk_start + local_index + 1
        row, col = pairs[index - 1]
        h_value, s_value, stds = _extract_matrix_element_values(pub_result)
        _store_matrix_element(
            projected=projected,
            overlap=overlap,
            row=row,
            col=col,
            h_value=h_value,
            s_value=s_value,
        )
        if stds.size:
            if stds.size != 4:
                raise ValueError("Estimator PUB did not return all matrix-element standard errors")
            hamiltonian_error = _finite_max_abs(stds[:2])
            overlap_error = _finite_max_abs(stds[2:4])
            max_hamiltonian_standard_error = _update_error_max(
                max_hamiltonian_standard_error, hamiltonian_error
            )
            max_overlap_standard_error = _update_error_max(
                max_overlap_standard_error, overlap_error
            )
            max_standard_error = _update_error_max(
                max_standard_error,
                _update_error_max(hamiltonian_error, overlap_error),
            )
        completed = index
        _emit_matrix_element_progress(
            progress_callback=progress_callback,
            algorithm=algorithm,
            index=index,
            total_iterations=len(pairs),
            row=row,
            col=col,
            h_value=h_value,
            estimator_pub_chunk=estimator_pub_chunk,
            dimension=dimension,
            projected=projected,
            overlap=overlap,
            max_hamiltonian_standard_error=max_hamiltonian_standard_error,
            max_overlap_standard_error=max_overlap_standard_error,
            max_standard_error=max_standard_error,
        )
    return (
        max_hamiltonian_standard_error,
        max_overlap_standard_error,
        max_standard_error,
        completed,
    )


def _finite_max_abs(values: np.ndarray) -> float | None:
    """Return the largest finite absolute standard error, if present."""
    finite_values = np.abs(np.asarray(values, dtype=float))
    finite_values = finite_values[np.isfinite(finite_values)]
    return float(np.max(finite_values)) if finite_values.size else None


def _update_error_max(
    current: float | None,
    candidate: float | None,
) -> float | None:
    """Merge a finite standard-error maximum without treating missing as zero."""
    if candidate is None:
        return current
    return candidate if current is None else max(current, candidate)


def _emit_branch_chunk_start(
    *,
    progress_callback: ProgressCallback | None,
    algorithm: str,
    completed: int,
    total_iterations: int,
    dimension: int,
    estimator_pub_chunk: list[int],
    estimator_pub_count: int,
) -> None:
    """Emit progress before one Estimator chunk is submitted."""
    if progress_callback is None:
        return
    progress_callback(
        {
            "algorithm": algorithm,
            "stage": "progress",
            "step": "hardware_matrix_elements",
            "iteration": completed,
            "completed_iterations": completed,
            "total_iterations": total_iterations,
            "energy": None,
            "matrix_element_strategy": "branch_estimator",
            "basis_dimension": dimension,
            "estimator_pub_chunk": estimator_pub_chunk,
            "estimator_pub_count": estimator_pub_count,
        }
    )


def _validate_chunk_result_count(*, chunk_result: Any, expected_count: int) -> None:
    """Validate that an Estimator chunk returned one result per submitted PUB."""
    if len(chunk_result) != expected_count:
        raise ValueError("Estimator result count does not match submitted matrix-element PUBs")


def _extract_matrix_element_values(
    pub_result: Any,
) -> tuple[complex, complex, np.ndarray]:
    """Extract complex H/S values and standard errors from one PUB result."""
    evs, stds = _extract_estimator_arrays(pub_result)
    if evs.size < 4:
        raise ValueError("Estimator PUB did not return all matrix-element observables")
    h_value = complex(float(evs[0]), float(evs[1]))
    s_value = complex(float(evs[2]), float(evs[3]))
    return h_value, s_value, stds


def _store_matrix_element(
    *,
    projected: np.ndarray,
    overlap: np.ndarray,
    row: int,
    col: int,
    h_value: complex,
    s_value: complex,
) -> None:
    """Store one upper-triangular matrix element and its Hermitian mirror."""
    projected[row, col] = h_value
    overlap[row, col] = s_value
    if row != col:
        projected[col, row] = np.conjugate(h_value)
        overlap[col, row] = np.conjugate(s_value)


def _emit_matrix_element_progress(
    *,
    progress_callback: ProgressCallback | None,
    algorithm: str,
    index: int,
    total_iterations: int,
    row: int,
    col: int,
    h_value: complex,
    estimator_pub_chunk: list[int],
    dimension: int,
    projected: np.ndarray,
    overlap: np.ndarray,
    max_hamiltonian_standard_error: float | None,
    max_overlap_standard_error: float | None,
    max_standard_error: float | None,
) -> None:
    """Emit per-PUB matrix-element progress and diagonal-subspace updates."""
    if progress_callback is None:
        return
    progress_callback(
        {
            "algorithm": algorithm,
            "stage": "progress",
            "step": "hardware_matrix_elements",
            "iteration": index,
            "completed_iterations": index,
            "total_iterations": total_iterations,
            "energy": None,
            "matrix_element_value": float(np.real(h_value)) if row == col else None,
            "value_kind": "diagonal_hamiltonian_element" if row == col else None,
            "matrix_element_pair": [row, col],
            "matrix_element_strategy": "branch_estimator",
            "basis_dimension": dimension,
            "estimator_pub_chunk": estimator_pub_chunk,
            "max_hamiltonian_standard_error": max_hamiltonian_standard_error,
            "max_overlap_standard_error": max_overlap_standard_error,
            "max_standard_error": max_standard_error,
            "standard_error_units": _STANDARD_ERROR_UNITS.copy(),
            "max_standard_error_compatibility": _STANDARD_ERROR_COMPATIBILITY.copy(),
        }
    )
    if row == col:
        _emit_projected_subspace_progress(
            progress_callback=progress_callback,
            algorithm=algorithm,
            projected=projected,
            overlap=overlap,
            basis_rank=row + 1,
            completed_matrix_elements=index,
            total_matrix_elements=total_iterations,
            estimator_pub_chunk=estimator_pub_chunk,
            basis_dimension=dimension,
            max_hamiltonian_standard_error=max_hamiltonian_standard_error,
            max_overlap_standard_error=max_overlap_standard_error,
            max_standard_error=max_standard_error,
        )


def _build_branch_estimator_summary(
    *,
    pubs: list[tuple[Any, list[SparsePauliOp]]],
    observables: list[SparsePauliOp],
    pauli_hamiltonian: SparsePauliOp,
    trotter_steps: int,
    time_points: list[float],
    dimension: int,
    max_hamiltonian_standard_error: float | None,
    max_overlap_standard_error: float | None,
    max_standard_error: float | None,
    backend_context: Any | None,
    estimator_pub_chunk_size: int,
    overlap_diagonal_normalized: bool,
    primitive_run_calls: int,
    primitive_successful_runs: int,
) -> dict[str, Any]:
    """Build the persisted summary for branch-estimator matrix-element solves."""
    return {
        "matrix_element_strategy": "branch_estimator",
        "primitive": "EstimatorV2",
        "branch_circuit_count": len(pubs),
        "estimator_pub_count": len(pubs),
        "estimator_pub_chunk_size": estimator_pub_chunk_size,
        "observable_count_per_pub": len(observables),
        "projected_dimension": dimension,
        "pauli_terms": len(pauli_hamiltonian),
        "trotter_steps": trotter_steps,
        "time_points": [float(value) for value in time_points],
        "max_hamiltonian_standard_error": max_hamiltonian_standard_error,
        "max_overlap_standard_error": max_overlap_standard_error,
        "max_standard_error": max_standard_error,
        "standard_error_units": _STANDARD_ERROR_UNITS.copy(),
        "max_standard_error_compatibility": _STANDARD_ERROR_COMPATIBILITY.copy(),
        "hermitian_symmetrized": True,
        "overlap_diagonal_normalized": overlap_diagonal_normalized,
        "residual_diagnostics_available": False,
        "backend_target": getattr(backend_context, "backend_target", None),
        "work_ledger": {
            "ledger_version": 1,
            "counting_scope": "worker_observed",
            "primitive_run_calls": primitive_run_calls,
            "primitive_successful_runs": primitive_successful_runs,
            "primitive_pub_count": len(pubs),
            "primitive_observable_slots": len(pubs) * len(observables),
        },
    }


def _emit_projected_subspace_progress(
    *,
    progress_callback: ProgressCallback,
    algorithm: str,
    projected: np.ndarray,
    overlap: np.ndarray,
    basis_rank: int,
    completed_matrix_elements: int,
    total_matrix_elements: int,
    estimator_pub_chunk: list[int],
    basis_dimension: int,
    max_hamiltonian_standard_error: float | None,
    max_overlap_standard_error: float | None,
    max_standard_error: float | None,
) -> None:
    """Emit partial Ritz progress once a leading projected block is complete."""
    partial_hamiltonian = _hermitian_symmetrized(projected[:basis_rank, :basis_rank])
    partial_overlap = _hermitian_symmetrized(overlap[:basis_rank, :basis_rank])
    partial_overlap[np.diag_indices_from(partial_overlap)] = 1.0
    solve_result = solve_stabilized_generalized_eigenproblem(
        partial_hamiltonian,
        partial_overlap,
        max_standard_error=max_overlap_standard_error,
    )
    diagnostics = solve_result.diagnostics
    ritz_values = solve_result.eigenvalues
    # A stabilized solve is diagnostic only.  PSD projection or mode dropping
    # changes the measured problem, so its Ritz value cannot be shown as a
    # usable provisional energy.
    is_valid = projected_matrix_converged(diagnostics) and ritz_values.size > 0
    progress_callback(
        {
            "algorithm": algorithm,
            "stage": "progress",
            "step": "projected_subspace_progress",
            "iteration": completed_matrix_elements,
            "completed_iterations": completed_matrix_elements,
            "total_iterations": total_matrix_elements,
            "energy": float(ritz_values[0]) if is_valid else None,
            "energy_state": "provisional" if is_valid else "unavailable",
            "convergence_iteration": basis_rank,
            "basis_rank": basis_rank,
            "basis_dimension": basis_dimension,
            "matrix_element_strategy": "branch_estimator",
            "estimator_pub_chunk": estimator_pub_chunk,
            "overlap_condition": float(diagnostics.get("overlap_condition", 0.0)),
            "overlap_min_eigenvalue": float(diagnostics.get("overlap_min_eigenvalue", 0.0)),
            "stability_state": diagnostics.get("stability_state"),
            "retained_rank": diagnostics.get("retained_rank"),
            "dropped_rank": diagnostics.get("dropped_rank"),
            "threshold": diagnostics.get("threshold"),
            "psd_projected": diagnostics.get("psd_projected"),
            "max_hamiltonian_standard_error": max_hamiltonian_standard_error,
            "max_overlap_standard_error": max_overlap_standard_error,
            "max_standard_error": max_standard_error,
            "standard_error_units": _STANDARD_ERROR_UNITS.copy(),
            "max_standard_error_compatibility": _STANDARD_ERROR_COMPATIBILITY.copy(),
        }
    )


def _resolve_pauli_hamiltonian(hamiltonian: object) -> SparsePauliOp:
    if isinstance(hamiltonian, SparsePauliOp):
        return hamiltonian
    pauli = getattr(hamiltonian, "pauli_hamiltonian", None)
    if isinstance(pauli, SparsePauliOp):
        return pauli
    raise ValueError("Hardware matrix-element workflow requires a SparsePauliOp Hamiltonian")


def _resolve_num_qubits(hamiltonian: object, pauli_hamiltonian: SparsePauliOp) -> int:
    raw_num_qubits = getattr(hamiltonian, "num_qubits", None)
    if isinstance(raw_num_qubits, int):
        return raw_num_qubits
    num_qubits = pauli_hamiltonian.num_qubits
    if not isinstance(num_qubits, int) or num_qubits < 1:
        raise ValueError("Hardware matrix-element workflow requires a positive qubit count")
    return num_qubits


def _extract_estimator_arrays(pub_result: Any) -> tuple[np.ndarray, np.ndarray]:
    data = getattr(pub_result, "data", None)
    if data is None:
        raise ValueError("Estimator PUB result missing data payload")
    evs = getattr(data, "evs", None)
    if evs is None:
        raise ValueError("Estimator PUB result missing expectation values")
    stds = getattr(data, "stds", np.array([], dtype=float))
    return np.asarray(evs, dtype=float).reshape(-1), np.asarray(stds, dtype=float).reshape(-1)


def _hermitian_symmetrized(matrix: np.ndarray) -> np.ndarray:
    value = np.asarray(matrix, dtype=complex)
    return 0.5 * (value + value.conj().T)


def hardware_projected_dimension_limit() -> int:
    """Return the projected-basis cap for hardware matrix-element workflows."""
    return _MAX_HARDWARE_PROJECTED_DIM
