"""Pure basis-construction helpers for the QSE algorithm package."""

from __future__ import annotations

import logging
from collections import abc
from itertools import chain
from typing import Any

import numpy as np

from worker.chemistry.algorithms.qse.excitations import (
    apply_fermionic_excitation,
    fermionic_excitation_specs,
)
from worker.chemistry.algorithms.qse.reference import vector_size_to_qubits
from worker.chemistry.algorithms.qse.sector import sector_excitation_specs
from worker.chemistry.eigensolver import solve_generalized_eigenproblem
from worker.chemistry.hamiltonian_action import HamiltonianAction
from worker.chemistry.overlap import build_overlap_matrix
from worker.chemistry.progress import ProgressCallback
from worker.chemistry.projected_subspace import solve_action_subspace
from worker.chemistry.sector_basis import apply_fermionic_excitation_sector

logger = logging.getLogger(__name__)


ExcitationSpec = tuple[str, tuple[int, ...], tuple[int, ...]]


def build_basis_selection_summary(
    selected_specs: list[ExcitationSpec],
    *,
    candidate_selection_policy: str,
    excitation_level: str,
    dimension_cap: int,
    actual_dimension: int,
    policy_details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Describe the exact excitation pool retained by a QSE basis builder."""
    counts = {"reference": 0, "single": 0, "double": 0}
    serialized_specs: list[dict[str, Any]] = []
    for basis_index, (kind, create_orbitals, annihilate_orbitals) in enumerate(
        selected_specs
    ):
        if kind in counts:
            counts[kind] += 1
        serialized_specs.append(
            {
                "basis_index": basis_index,
                "kind": kind,
                "create_orbitals": list(create_orbitals),
                "annihilate_orbitals": list(annihilate_orbitals),
            }
        )
    return {
        "candidate_selection_policy": candidate_selection_policy,
        "policy_details": dict(policy_details or {}),
        "requested_excitation_level": excitation_level,
        "requested_dimension_cap": int(dimension_cap),
        "actual_basis_dimension": int(actual_dimension),
        "selected_specs_complete": len(selected_specs) == int(actual_dimension),
        "dimension_cap_reached": int(actual_dimension) >= int(dimension_cap),
        "selected_excitation_counts": counts,
        "selected_excitation_specs": serialized_specs,
    }


def real_scalar(value: Any, *, label: str, atol: float = 1e-8) -> float:
    """Return the real part of a scalar that should be real by construction."""
    array_value = np.asarray(value)
    if array_value.size != 1:
        raise ValueError(f"{label} must be scalar")

    scalar = complex(array_value.reshape(()).item())
    if not np.isfinite(scalar.real) or not np.isfinite(scalar.imag):
        raise ValueError(f"{label} must be finite")

    tolerance = max(atol, atol * max(1.0, abs(scalar.real)))
    if abs(scalar.imag) > tolerance:
        logger.warning(
            "%s has non-negligible imaginary component %.3e; using real component %.12f",
            label,
            scalar.imag,
            scalar.real,
        )
    return float(scalar.real)


def accept_basis_candidate(
    candidate: np.ndarray,
    *,
    basis: list[np.ndarray],
    orthonormal_basis: list[np.ndarray],
    overlap_threshold: float,
) -> float | None:
    """Append a normalized candidate when it is linearly independent enough."""
    vector = np.asarray(candidate, dtype=complex)
    norm = float(np.linalg.norm(vector))
    if norm == 0.0:
        return None

    normalized = vector / norm
    residual = normalized.copy()
    for basis_vector in orthonormal_basis:
        residual -= np.vdot(basis_vector, residual) * basis_vector

    residual_norm = float(np.linalg.norm(residual))
    if orthonormal_basis and residual_norm <= overlap_threshold:
        return None

    if not np.isfinite(residual_norm):
        return None
    basis.append(normalized)
    if residual_norm == 0.0:
        orthonormal_basis.append(normalized)
        return 0.0

    orthonormal_basis.append(residual / residual_norm)
    return residual_norm


def build_sector_excitation_basis(
    reference_state: np.ndarray,
    action: HamiltonianAction,
    *,
    excitation_level: str,
    target_rank: int,
    overlap_threshold: float,
    residual_tolerance: float,
    progress_callback: ProgressCallback | None,
    selection_callback: abc.Callable[[ExcitationSpec], None] | None = None,
    sector_excitation_specs_fn: abc.Callable[..., list[ExcitationSpec]] = sector_excitation_specs,
    apply_fermionic_excitation_sector_fn: abc.Callable[..., np.ndarray] = (
        apply_fermionic_excitation_sector
    ),
    accept_basis_candidate_fn: abc.Callable[..., float | None] = accept_basis_candidate,
    solve_action_subspace_fn: abc.Callable[..., tuple[Any, ...]] = solve_action_subspace,
) -> list[np.ndarray]:
    """Build a compact QSE basis from fixed-sector excitation states."""
    basis: list[np.ndarray] = []
    orthonormal_basis: list[np.ndarray] = []

    candidate_specs = chain(
        [("reference", (), ())],
        sector_excitation_specs_fn(
            reference_state,
            action,
            excitation_level=excitation_level,
        ),
    )
    for idx, (kind, create_orbitals, annihilate_orbitals) in enumerate(candidate_specs, start=1):
        if kind == "reference":
            candidate = reference_state
        else:
            candidate = apply_fermionic_excitation_sector_fn(
                reference_state,
                create_orbitals=create_orbitals,
                annihilate_orbitals=annihilate_orbitals,
                norb=action.norb,
                nelec=action.nelec,
            )
        independence_norm = accept_basis_candidate_fn(
            candidate,
            basis=basis,
            orthonormal_basis=orthonormal_basis,
            overlap_threshold=overlap_threshold,
        )
        if independence_norm is None:
            continue
        if selection_callback is not None:
            selection_callback((kind, create_orbitals, annihilate_orbitals))

        candidate_norm = float(np.linalg.norm(candidate))
        partial_energy_m = None
        try:
            partial_eigs_m, *_ = solve_action_subspace_fn(
                action,
                np.column_stack(basis),
                residual_tolerance=residual_tolerance,
                regularization=0.0,
            )
            if partial_eigs_m.size:
                partial_energy_m = float(partial_eigs_m[0])
        except ValueError:
            partial_energy_m = None
        if progress_callback is not None:
            progress_callback(
                {
                    "algorithm": "qse",
                    "stage": "progress",
                    "step": "build_basis",
                    "iteration": idx,
                    "completed_iterations": len(basis),
                    "total_iterations": target_rank,
                    "energy": partial_energy_m,
                    "candidate_norm": candidate_norm,
                    "linear_independence_norm": independence_norm,
                    "excitation_level": excitation_level,
                    "excitation_kind": kind,
                    "create_orbitals": list(create_orbitals),
                    "annihilate_orbitals": list(annihilate_orbitals),
                    "execution_mode": "sector_matrix_free",
                }
            )
        if len(basis) >= target_rank:
            break

    if not basis:
        basis.append(np.asarray(reference_state, dtype=complex))

    return basis


def build_excitation_basis(
    reference_state: np.ndarray,
    operator_matrix: np.ndarray,
    *,
    excitation_level: str,
    target_rank: int,
    overlap_threshold: float,
    regularization: float,
    progress_callback: ProgressCallback | None,
    **basis_dependencies: Any,
) -> list[np.ndarray]:
    """Build a compact QSE basis from fermionic excitation-generated states."""
    vector_size_to_qubits_fn = basis_dependencies.get(
        "vector_size_to_qubits_fn", vector_size_to_qubits
    )
    fermionic_excitation_specs_fn = basis_dependencies.get(
        "fermionic_excitation_specs_fn", fermionic_excitation_specs
    )
    apply_fermionic_excitation_fn = basis_dependencies.get(
        "apply_fermionic_excitation_fn", apply_fermionic_excitation
    )
    accept_basis_candidate_fn = basis_dependencies.get(
        "accept_basis_candidate_fn", accept_basis_candidate
    )
    overlap_builder_fn = basis_dependencies.get("overlap_builder_fn", build_overlap_matrix)
    eigensolver_fn = basis_dependencies.get("eigensolver_fn", solve_generalized_eigenproblem)
    real_scalar_fn = basis_dependencies.get("real_scalar_fn", real_scalar)
    selection_callback = basis_dependencies.get("selection_callback")
    basis: list[np.ndarray] = []
    orthonormal_basis: list[np.ndarray] = []
    num_qubits = vector_size_to_qubits_fn(reference_state.size)

    candidate_specs = chain(
        [("reference", (), ())],
        fermionic_excitation_specs_fn(num_qubits, excitation_level=excitation_level),
    )
    for idx, (kind, create_orbitals, annihilate_orbitals) in enumerate(candidate_specs, start=1):
        if kind == "reference":
            candidate = reference_state
        else:
            candidate = apply_fermionic_excitation_fn(
                reference_state,
                create_orbitals=create_orbitals,
                annihilate_orbitals=annihilate_orbitals,
                num_qubits=num_qubits,
            )
        independence_norm = accept_basis_candidate_fn(
            candidate,
            basis=basis,
            orthonormal_basis=orthonormal_basis,
            overlap_threshold=overlap_threshold,
        )
        if independence_norm is None:
            continue
        if selection_callback is not None:
            selection_callback((kind, create_orbitals, annihilate_orbitals))

        candidate_norm = float(np.linalg.norm(candidate))
        partial_basis_m = np.column_stack(basis)
        partial_h_m = partial_basis_m.conj().T @ operator_matrix @ partial_basis_m
        partial_s_m = overlap_builder_fn(basis)
        partial_eigs_m, _ = eigensolver_fn(
            partial_h_m,
            partial_s_m,
            regularization=regularization,
        )
        partial_energy_m = (
            real_scalar_fn(partial_eigs_m[0], label="QSE partial energy")
            if partial_eigs_m.size
            else None
        )
        if progress_callback is not None:
            progress_callback(
                {
                    "algorithm": "qse",
                    "stage": "progress",
                    "step": "build_basis",
                    "iteration": idx,
                    "completed_iterations": len(basis),
                    "total_iterations": target_rank,
                    "energy": partial_energy_m,
                    "candidate_norm": candidate_norm,
                    "linear_independence_norm": independence_norm,
                    "excitation_level": excitation_level,
                    "excitation_kind": kind,
                    "create_orbitals": list(create_orbitals),
                    "annihilate_orbitals": list(annihilate_orbitals),
                }
            )
        if len(basis) >= target_rank:
            break

    if not basis:
        basis.append(np.asarray(reference_state, dtype=complex))

    return basis


__all__ = [
    "accept_basis_candidate",
    "build_basis_selection_summary",
    "build_excitation_basis",
    "build_sector_excitation_basis",
    "real_scalar",
]
