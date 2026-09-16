"""Measured fixed-pool QSE matrix assembly for noisy and hardware targets.

Builds nonorthogonal projected matrices directly from Pauli expectation values
measured on one reference state ``|psi>`` through the backend Estimator:

    S_ij = <psi| A_i^dagger A_j |psi>
    H_ij = <psi| A_i^dagger H A_j |psi>

The excitation operators ``A_i`` are Jordan-Wigner ``SparsePauliOp`` objects
built from the same fermionic excitation specifications used by the exact QSE
path (``worker.chemistry.algorithms.qse.excitations``). ``A_0`` is the
identity, so the reference state is the first basis vector and ``S_00`` is a
structural identity.

This path uses a fixed fermionic excitation pool. It does not implement the
adaptive global Pauli-bank procedure in DA-CASE. Only the projected H/S matrices
are assembled here; the stabilized generalized eigensolver and its diagnostic
reportability gate are reused unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from qiskit.quantum_info import SparsePauliOp, Statevector

from worker.chemistry.algorithms.qse.excitations import (
    apply_fermionic_excitation,
    fermionic_excitation_specs,
)
from worker.chemistry.progress import ProgressCallback
from worker.chemistry.projected_execution import validate_branch_estimator_feasibility

# Keep the projected dimension small enough to be meaningful for noisy targets.
_MAX_MEASURED_QSE_DIM = 8
_ESTIMATOR_PUB_CHUNK_SIZE = 4
_AER_ESTIMATOR_PUB_CHUNK_SIZE = 2
_NOISY_AER_ESTIMATOR_PUB_CHUNK_SIZE = 4
_STANDARD_ERROR_UNITS = {
    "max_hamiltonian_standard_error": "hamiltonian_energy_units",
    "max_overlap_standard_error": "dimensionless",
    "max_standard_error": "mixed_hamiltonian_energy_and_dimensionless_overlap",
}
_STANDARD_ERROR_COMPATIBILITY = {
    "definition": "legacy_max_across_hamiltonian_and_overlap_entries",
    "units": "mixed_hamiltonian_energy_and_dimensionless_overlap",
    "deprecated": True,
}


@dataclass(frozen=True)
class MeasuredQSEMatrixElements:
    """Projected H/S matrices assembled from measured Pauli expectations."""

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


def _resolve_pauli_hamiltonian(hamiltonian: object) -> SparsePauliOp:
    if isinstance(hamiltonian, SparsePauliOp):
        return hamiltonian
    pauli = getattr(hamiltonian, "pauli_hamiltonian", None)
    if isinstance(pauli, SparsePauliOp):
        return pauli
    raise ValueError("Measured QSE requires a SparsePauliOp Hamiltonian")


def _resolve_num_qubits(hamiltonian: object, pauli_hamiltonian: SparsePauliOp) -> int:
    raw_num_qubits = getattr(hamiltonian, "num_qubits", None)
    if isinstance(raw_num_qubits, int) and raw_num_qubits > 0:
        return raw_num_qubits
    num_qubits = pauli_hamiltonian.num_qubits
    if not isinstance(num_qubits, int) or num_qubits < 1:
        raise ValueError("Measured QSE requires a positive qubit count")
    return num_qubits


def _jordan_wigner_ladder(num_qubits: int, orbital: int, *, create: bool) -> SparsePauliOp:
    """Return a single Jordan-Wigner ladder operator as a SparsePauliOp.

    ``a_p^dagger = 0.5 (X_p - i Y_p) Z_{p-1} ... Z_0`` and
    ``a_p = 0.5 (X_p + i Y_p) Z_{p-1} ... Z_0``. This matches the sign
    convention of ``apply_fermionic_ladder`` (parity of lower-index qubits).
    """
    if orbital < 0 or orbital >= num_qubits:
        raise ValueError(f"orbital {orbital} out of range for {num_qubits} qubits")

    def _label(pauli_on_orbital: str) -> str:
        chars = ["I"] * num_qubits
        for lower in range(orbital):
            chars[lower] = "Z"
        chars[orbital] = pauli_on_orbital
        # Qiskit labels are little-endian: the rightmost char is qubit 0.
        return "".join(reversed(chars))

    y_coefficient = -0.5j if create else 0.5j
    return SparsePauliOp.from_list(
        [(_label("X"), 0.5), (_label("Y"), y_coefficient)]
    )


def _excitation_operator(
    num_qubits: int,
    *,
    create_orbitals: tuple[int, ...],
    annihilate_orbitals: tuple[int, ...],
) -> SparsePauliOp:
    """Build ``A = (prod create) (prod annihilate)`` as a SparsePauliOp.

    Operators act right-to-left: annihilate first, then create in reverse
    order, matching ``apply_fermionic_excitation``.
    """
    operations = [(False, orbital) for orbital in annihilate_orbitals] + [
        (True, orbital) for orbital in reversed(create_orbitals)
    ]
    ladders = [
        _jordan_wigner_ladder(num_qubits, orbital, create=create)
        for create, orbital in operations
    ]
    # ``operations[0]`` is applied first (the rightmost matrix factor); the
    # composed operator is ``M_last @ ... @ M_first``.
    product = ladders[0]
    for ladder in ladders[1:]:
        product = ladder @ product
    return product.simplify(atol=1e-12)


def build_measured_excitation_operators(
    *,
    num_qubits: int,
    reference_state: np.ndarray,
    excitation_level: str,
    max_dimension: int,
) -> list[SparsePauliOp]:
    """Build a capped set of independent excitation actions on the reference.

    The dimension cap includes the identity/reference direction. Skip an
    excitation when it annihilates the reference or its resulting state is
    linearly dependent on an already selected direction. This lets useful
    later excitations, including doubles, fill the available basis slots.
    """
    if (
        isinstance(max_dimension, bool)
        or not isinstance(max_dimension, (int, np.integer))
        or max_dimension < 1
    ):
        raise ValueError("Measured QSE max_dimension must be a positive integer")
    max_dimension = int(max_dimension)

    reference = np.asarray(reference_state, dtype=complex)
    if reference.ndim != 1 or reference.size != 2**num_qubits:
        raise ValueError("Measured QSE reference_state size must match num_qubits")
    reference_norm = float(np.linalg.norm(reference))
    if not np.isfinite(reference_norm) or reference_norm <= 1e-12:
        raise ValueError("Measured QSE reference_state must have a finite non-zero norm")
    reference = reference / reference_norm

    identity = SparsePauliOp.from_list([("I" * num_qubits, 1.0)])
    operators: list[SparsePauliOp] = [identity]
    orthonormal_states = [reference]
    for _kind, create_orbitals, annihilate_orbitals in fermionic_excitation_specs(
        num_qubits,
        excitation_level=excitation_level,
    ):
        if len(operators) >= max_dimension:
            break
        operator = _excitation_operator(
            num_qubits,
            create_orbitals=create_orbitals,
            annihilate_orbitals=annihilate_orbitals,
        )
        # Skip operators that annihilate to zero on the full space.
        if len(operator) == 0:
            continue

        candidate = apply_fermionic_excitation(
            reference,
            create_orbitals=create_orbitals,
            annihilate_orbitals=annihilate_orbitals,
            num_qubits=num_qubits,
        )
        candidate_norm = float(np.linalg.norm(candidate))
        if not np.isfinite(candidate_norm) or candidate_norm <= 1e-12:
            continue

        residual = candidate / candidate_norm
        # Re-orthogonalize once to keep the rank test stable for non-determinant
        # reference states while limiting work to this small capped subspace.
        for _ in range(2):
            for basis_state in orthonormal_states:
                residual -= np.vdot(basis_state, residual) * basis_state
        residual_norm = float(np.linalg.norm(residual))
        if not np.isfinite(residual_norm) or residual_norm <= 1e-10:
            continue

        operators.append(operator)
        orthonormal_states.append(residual / residual_norm)
    return operators


def _prepare_reference_circuit(
    *,
    hamiltonian: object,
    num_qubits: int,
    backend_context: Any | None,
) -> Any:
    """Build the single reference-state preparation circuit for measurement."""
    from qiskit import QuantumCircuit

    from worker.chemistry.circuit_artifacts import prepare_hf_reference_bits

    circuit = QuantumCircuit(num_qubits)
    prepare_hf_reference_bits(circuit, hamiltonian, num_qubits=num_qubits)
    return circuit


def _layout_observable(observable: SparsePauliOp, layout: Any) -> SparsePauliOp:
    apply_layout = getattr(observable, "apply_layout", None)
    if not callable(apply_layout):
        return observable
    resolved = apply_layout(layout)
    return resolved if isinstance(resolved, SparsePauliOp) else observable


def _is_hermitian_operator(operator: SparsePauliOp) -> bool:
    """Return True when every Pauli coefficient is (numerically) real.

    A Pauli-basis operator is Hermitian iff all of its coefficients are real,
    because every Pauli word is itself Hermitian.
    """
    coeffs = np.asarray(operator.coeffs, dtype=complex)
    if coeffs.size == 0:
        return True
    return bool(np.all(np.abs(coeffs.imag) <= 1e-9))


def _hermitian_measurement_plan(
    operator: SparsePauliOp,
) -> list[tuple[SparsePauliOp, complex]]:
    """Return the Hermitian observables and complex coefficients for ``O``.

    A general (possibly non-Hermitian) Pauli operator ``O`` has a complex
    expectation value that cannot be obtained from a single EstimatorV2
    observable, because the primitive rejects non-Hermitian inputs and returns
    a real number. We therefore split ``O`` into two Hermitian observables:

        O_re = (O + O_dagger) / 2
        O_im = (O - O_dagger) / (2 i)

    Both are Hermitian (real Pauli coefficients after ``simplify``), and
    ``<O> = <O_re> + i <O_im>``.

    When ``O`` is already Hermitian, a single observable suffices and the
    reconstruction is purely real.

    Returns an ordered list of ``(observable, complex_coefficient)`` components.
    The complex expectation is reconstructed as
    ``sum(coefficient * real_ev)``. Observables that simplify to the empty
    operator (all coefficients cancel) are dropped, because EstimatorV2 rejects
    empty observables; their contribution is exactly zero anyway.
    """

    def _real_nonempty(candidate: SparsePauliOp) -> SparsePauliOp | None:
        real_operator = SparsePauliOp(
            candidate.paulis, np.real(np.asarray(candidate.coeffs, dtype=complex))
        ).simplify(atol=1e-12)
        coeffs = np.asarray(real_operator.coeffs, dtype=complex)
        # ``simplify`` collapses an all-zero operator to a single zero-weighted
        # term rather than an empty operator; EstimatorV2 rejects that as an
        # "Empty observable". Treat any all-zero operator as absent.
        if coeffs.size == 0 or bool(np.all(np.abs(coeffs) <= 1e-12)):
            return None
        return real_operator

    simplified = operator.simplify(atol=1e-12)
    if _is_hermitian_operator(simplified):
        real_operator = _real_nonempty(simplified)
        if real_operator is None:
            return []
        return [(real_operator, 1.0 + 0.0j)]

    adjoint = simplified.adjoint()
    o_re = ((simplified + adjoint) * 0.5).simplify(atol=1e-12)
    o_im = ((simplified - adjoint) * (-0.5j)).simplify(atol=1e-12)
    components: list[tuple[SparsePauliOp, complex]] = []
    re_operator = _real_nonempty(o_re)
    if re_operator is not None:
        components.append((re_operator, 1.0 + 0.0j))
    im_operator = _real_nonempty(o_im)
    if im_operator is not None:
        components.append((im_operator, 1.0j))
    return components


@dataclass(frozen=True)
class _PairMeasurementPlan:
    """Ordered Hermitian observables and reconstruction coefficients for a pair.

    ``h_component_count`` observables reconstruct ``H_ij``; the remaining
    observables reconstruct ``S_ij``. ``coefficients`` are the complex weights
    applied to each measured real expectation value.
    """

    observables: list[SparsePauliOp]
    coefficients: list[complex]
    h_component_count: int


def _build_pair_measurement_plans(
    *,
    operators: list[SparsePauliOp],
    pauli_hamiltonian: SparsePauliOp,
    pairs: list[tuple[int, int]],
    layout: Any | None,
) -> list[_PairMeasurementPlan]:
    """Build per-pair Hermitian observable plans for ``H_ij`` and ``S_ij``.

    Off-diagonal composite operators are non-Hermitian, so each is decomposed
    into Hermitian observables whose real expectations reconstruct the complex
    matrix element. Every observable submitted to the estimator is therefore
    Hermitian, and empty observables are never submitted.
    """
    plans: list[_PairMeasurementPlan] = []
    for row, col in pairs:
        a_row_dagger = operators[row].adjoint()
        a_col = operators[col]
        h_operator = (a_row_dagger @ pauli_hamiltonian @ a_col).simplify(atol=1e-12)
        s_operator = (a_row_dagger @ a_col).simplify(atol=1e-12)
        h_components = _hermitian_measurement_plan(h_operator)
        s_components = _hermitian_measurement_plan(s_operator)
        observables = [obs for obs, _ in h_components] + [obs for obs, _ in s_components]
        coefficients = [coeff for _, coeff in h_components] + [
            coeff for _, coeff in s_components
        ]
        if layout is not None:
            observables = [_layout_observable(obs, layout) for obs in observables]
        if not observables:
            # EstimatorV2 rejects empty PUBs. Both H_ij and S_ij fully
            # cancelled, so submit a single zero-weighted identity observable
            # whose contribution is exactly zero for both matrix elements.
            num_qubits = pauli_hamiltonian.num_qubits
            identity = SparsePauliOp.from_list([("I" * num_qubits, 1.0)])
            if layout is not None:
                identity = _layout_observable(identity, layout)
            observables = [identity]
            coefficients = [0.0 + 0.0j]
            plans.append(_PairMeasurementPlan(observables, coefficients, 1))
            continue
        plans.append(
            _PairMeasurementPlan(observables, coefficients, len(h_components))
        )
    return plans


def _reconstruct_from_components(
    values: np.ndarray, coefficients: list[complex], offset: int, count: int
) -> complex:
    """Reconstruct a complex expectation as ``sum(coefficient * real_ev)``."""
    total = 0.0 + 0.0j
    for local in range(count):
        total += coefficients[offset + local] * float(values[offset + local])
    return complex(total)


def _hermitian_symmetrized(matrix: np.ndarray) -> np.ndarray:
    value = np.asarray(matrix, dtype=complex)
    return 0.5 * (value + value.conj().T)


def _extract_estimator_arrays(pub_result: Any) -> tuple[np.ndarray, np.ndarray]:
    data = getattr(pub_result, "data", None)
    if data is None:
        raise ValueError("Estimator PUB result missing data payload")
    evs = getattr(data, "evs", None)
    if evs is None:
        raise ValueError("Estimator PUB result missing expectation values")
    stds = getattr(data, "stds", np.array([], dtype=float))
    return np.asarray(evs, dtype=float).reshape(-1), np.asarray(stds, dtype=float).reshape(-1)


def _emit_status(
    *,
    progress_callback: ProgressCallback | None,
    pairs: list[tuple[int, int]],
    dimension: int,
    pauli_terms: int,
    status: str,
    estimator_pub_count: int | None = None,
) -> None:
    if progress_callback is None:
        return
    progress_callback(
        {
            "algorithm": "qse",
            "stage": "progress",
            "step": "measured_matrix_elements",
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
            "status": status,
        }
    )


def _emit_pair_progress(
    *,
    progress_callback: ProgressCallback | None,
    index: int,
    total: int,
    row: int,
    col: int,
    h_value: complex,
    dimension: int,
    estimator_pub_chunk: list[int],
    max_hamiltonian_standard_error: float | None,
    max_overlap_standard_error: float | None,
    max_standard_error: float | None,
) -> None:
    if progress_callback is None:
        return
    progress_callback(
        {
            "algorithm": "qse",
            "stage": "progress",
            "step": "measured_matrix_elements",
            "iteration": index,
            "completed_iterations": index,
            "total_iterations": total,
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


def estimate_measured_qse_matrices(
    *,
    hamiltonian: object,
    estimator: Any,
    excitation_level: str,
    max_dimension: int,
    backend_context: Any | None = None,
    progress_callback: ProgressCallback | None = None,
) -> MeasuredQSEMatrixElements:
    """Assemble measured QSE projected H/S matrices from Estimator PUBs.

    One PUB per upper-triangular ``(i, j)`` pair carries two observables:
    ``A_i^dagger H A_j`` and ``A_i^dagger A_j``. Their expectation values on the
    single prepared reference state give ``H_ij`` and ``S_ij`` directly.
    """
    if not hasattr(estimator, "run"):
        raise ValueError("Measured QSE requires an EstimatorV2 backend")
    validate_branch_estimator_feasibility(hamiltonian, backend_context, algorithm="qse")
    pauli_hamiltonian = _resolve_pauli_hamiltonian(hamiltonian)
    num_qubits = _resolve_num_qubits(hamiltonian, pauli_hamiltonian)
    bounded_dimension = max(1, min(int(max_dimension), _MAX_MEASURED_QSE_DIM))

    _emit_status(
        progress_callback=progress_callback,
        pairs=[],
        dimension=bounded_dimension,
        pauli_terms=len(pauli_hamiltonian),
        status="preparing_reference_circuit",
    )
    circuit = _prepare_reference_circuit(
        hamiltonian=hamiltonian,
        num_qubits=num_qubits,
        backend_context=backend_context,
    )
    # Use the state prepared by the submitted circuit as the basis-selection
    # reference. This keeps the cap filter tied to the measured state if the
    # circuit preparation policy changes.
    reference_state = Statevector.from_instruction(circuit).data
    operators = build_measured_excitation_operators(
        num_qubits=num_qubits,
        reference_state=reference_state,
        excitation_level=excitation_level,
        max_dimension=bounded_dimension,
    )
    dimension = len(operators)
    pairs = [(row, col) for row in range(dimension) for col in range(row, dimension)]
    layout = getattr(circuit, "layout", None)
    plans = _build_pair_measurement_plans(
        operators=operators,
        pauli_hamiltonian=pauli_hamiltonian,
        pairs=pairs,
        layout=layout,
    )
    # One PUB per pair, each carrying the Hermitian observables required to
    # reconstruct H_ij and S_ij (1 or 2 observables per matrix element).
    pubs = [(circuit, plan.observables) for plan in plans]
    _emit_status(
        progress_callback=progress_callback,
        pairs=pairs,
        dimension=dimension,
        pauli_terms=len(pauli_hamiltonian),
        status="reference_circuit_ready",
        estimator_pub_count=len(pubs),
    )

    projected = np.zeros((dimension, dimension), dtype=complex)
    overlap = np.zeros((dimension, dimension), dtype=complex)
    # ``None`` means the primitive did not report uncertainty; it must not be
    # treated as zero by the stabilized solver.
    max_hamiltonian_standard_error: float | None = None
    max_overlap_standard_error: float | None = None
    max_standard_error: float | None = None
    chunk_size = _estimator_pub_chunk_size(backend_context)

    completed = 0
    for chunk_start in range(0, len(pubs), chunk_size):
        chunk_end = min(chunk_start + chunk_size, len(pubs))
        estimator_pub_chunk = [chunk_start + 1, chunk_end]
        chunk_result = estimator.run(pubs[chunk_start:chunk_end]).result()
        if len(chunk_result) != chunk_end - chunk_start:
            raise ValueError(
                "Estimator result count does not match submitted matrix-element PUBs"
            )
        for local_index, pub_result in enumerate(chunk_result):
            index = chunk_start + local_index
            row, col = pairs[index]
            plan = plans[index]
            evs, stds = _extract_estimator_arrays(pub_result)
            expected_count = len(plan.observables)
            if evs.size < expected_count:
                raise ValueError(
                    "Measured QSE PUB did not return the required Hermitian observables"
                )
            h_count = plan.h_component_count
            s_count = expected_count - h_count
            h_value = _reconstruct_from_components(evs, plan.coefficients, 0, h_count)
            s_value = _reconstruct_from_components(
                evs, plan.coefficients, h_count, s_count
            )
            projected[row, col] = h_value
            overlap[row, col] = s_value
            if row != col:
                projected[col, row] = np.conjugate(h_value)
                overlap[col, row] = np.conjugate(s_value)
            if stds.size:
                if stds.size != expected_count:
                    raise ValueError(
                        "Measured QSE PUB did not return all observable standard errors"
                    )
                h_error = _finite_max_standard_error(stds[:h_count])
                s_error = _finite_max_standard_error(stds[h_count:expected_count])
                max_hamiltonian_standard_error = _update_standard_error_max(
                    max_hamiltonian_standard_error, h_error
                )
                max_overlap_standard_error = _update_standard_error_max(
                    max_overlap_standard_error, s_error
                )
                max_standard_error = _update_standard_error_max(
                    max_standard_error,
                    _update_standard_error_max(h_error, s_error),
                )
            completed = index + 1
            _emit_pair_progress(
                progress_callback=progress_callback,
                index=completed,
                total=len(pairs),
                row=row,
                col=col,
                h_value=h_value,
                dimension=dimension,
                estimator_pub_chunk=estimator_pub_chunk,
                max_hamiltonian_standard_error=max_hamiltonian_standard_error,
                max_overlap_standard_error=max_overlap_standard_error,
                max_standard_error=max_standard_error,
            )

    projected = _hermitian_symmetrized(projected)
    overlap = _hermitian_symmetrized(overlap)
    # ``A_0`` is the identity, so ``S_00`` is a structural identity. The
    # excitation operators are not normalized, so only the reference diagonal is
    # forced; off-diagonal and excited-diagonal overlaps stay measured.
    overlap[0, 0] = 1.0

    summary = {
        "matrix_element_strategy": "branch_estimator",
        "measured_matrix_element_construction": "fixed_pool_qse_nonorthogonal_eigensolver",
        "primitive": "EstimatorV2",
        "estimator_pub_count": len(pubs),
        "estimator_pub_chunk_size": chunk_size,
        "observable_count": sum(len(plan.observables) for plan in plans),
        "hermitian_observable_decomposition": True,
        "projected_dimension": dimension,
        "projected_matrix_element_count": 2 * dimension**2,
        "basis_cap_policy": "nonzero_independent_reference_actions",
        "pauli_terms": len(pauli_hamiltonian),
        "max_hamiltonian_standard_error": max_hamiltonian_standard_error,
        "max_overlap_standard_error": max_overlap_standard_error,
        "max_standard_error": max_standard_error,
        "standard_error_units": _STANDARD_ERROR_UNITS.copy(),
        "max_standard_error_compatibility": _STANDARD_ERROR_COMPATIBILITY.copy(),
        "hermitian_symmetrized": True,
        "reference_overlap_normalized": True,
        "basis_construction_rule": "jordan_wigner_fermionic_excitation_operators",
        "excitation_level": excitation_level,
        "backend_target": getattr(backend_context, "backend_target", None),
    }
    return MeasuredQSEMatrixElements(projected, overlap, summary)


def _finite_max_standard_error(values: np.ndarray) -> float | None:
    """Return the maximum finite absolute standard error, if present."""
    candidates = np.abs(np.asarray(values, dtype=float))
    finite = candidates[np.isfinite(candidates)]
    return float(np.max(finite)) if finite.size else None


def _update_standard_error_max(
    current: float | None,
    candidate: float | None,
) -> float | None:
    """Merge a standard-error maximum without treating missing data as zero."""
    if candidate is None:
        return current
    return candidate if current is None else max(current, candidate)


def measured_qse_dimension_limit() -> int:
    """Return the projected-basis cap for measured QSE workflows."""
    return _MAX_MEASURED_QSE_DIM


__all__ = [
    "MeasuredQSEMatrixElements",
    "build_measured_excitation_operators",
    "estimate_measured_qse_matrices",
    "measured_qse_dimension_limit",
]
