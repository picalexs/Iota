"""Shared backend-path policies for projected KQD and QFD execution."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

from worker.chemistry.hamiltonian_action import HamiltonianAction, can_build_hamiltonian_action
from worker.exceptions import RunExcludedError

_DENSE_QUBIT_LIMIT = 12
_MAX_NOISY_AER_PROJECTED_MATRIX_ORBITALS = 6
_MAX_IBM_PROJECTED_MATRIX_ORBITALS = _MAX_NOISY_AER_PROJECTED_MATRIX_ORBITALS


@dataclass(frozen=True)
class ProjectedExecutionResources:
    """Shared branch, sector, or dense resources for projected solvers."""

    use_branch_matrix_elements: bool
    sector_action: HamiltonianAction | None
    operator: np.ndarray | None
    dimension: int
    time_evolution_backend: str
    selection_reason: str = "unspecified"


def prepare_projected_execution(
    *,
    hamiltonian: object,
    backend: object | None,
    backend_context: Any | None,
    should_use_branch_matrix_elements_fn: Callable[..., bool],
    can_use_sector_action_fn: Callable[[object, Any | None], bool],
    build_hamiltonian_action_fn: Callable[[object], HamiltonianAction],
    resolve_operator_matrix_fn: Callable[[object], np.ndarray],
    num_qubits_fn: Callable[[object], int],
    backend_label_fn: Callable[..., str],
) -> ProjectedExecutionResources:
    """Resolve shared resources for a projected KQD or QFD execution path."""
    use_branch_matrix_elements = should_use_branch_matrix_elements_fn(
        hamiltonian=hamiltonian,
        backend=backend,
        backend_context=backend_context,
    )
    use_sector_action = not use_branch_matrix_elements and can_use_sector_action_fn(
        hamiltonian,
        backend_context,
    )
    sector_action = build_hamiltonian_action_fn(hamiltonian) if use_sector_action else None
    operator = (
        None
        if use_branch_matrix_elements or sector_action is not None
        else resolve_operator_matrix_fn(hamiltonian)
    )
    if sector_action is not None:
        dimension = sector_action.dimension
    elif operator is None:
        dimension = 2 ** num_qubits_fn(hamiltonian)
    else:
        dimension = operator.shape[0]
    backend_target = getattr(backend_context, "backend_target", None)
    if use_branch_matrix_elements:
        if backend_target == "ibm_runtime":
            selection_reason = "requested_ibm_runtime_requires_branch_estimator"
        elif getattr(backend_context, "noise_profile", None) is not None:
            selection_reason = "noisy_aer_requires_branch_estimator"
        else:
            selection_reason = "large_aer_problem_requires_branch_estimator"
    elif use_sector_action:
        selection_reason = "large_noiseless_problem_uses_sector_matrix_free_action"
    else:
        selection_reason = "problem_uses_dense_projected_matrices"

    return ProjectedExecutionResources(
        use_branch_matrix_elements=use_branch_matrix_elements,
        sector_action=sector_action,
        operator=operator,
        dimension=dimension,
        time_evolution_backend=backend_label_fn(
            use_branch_matrix_elements=use_branch_matrix_elements,
            use_sector_action=sector_action is not None,
            backend_context=backend_context,
        ),
        selection_reason=selection_reason,
    )


def num_qubits(hamiltonian: object) -> int:
    """Resolve the qubit width from a Hamiltonian bundle-like object."""
    if hasattr(hamiltonian, "num_qubits"):
        return int(getattr(hamiltonian, "num_qubits") or 0)
    pauli = getattr(hamiltonian, "pauli_hamiltonian", None)
    if pauli is not None and hasattr(pauli, "num_qubits"):
        return int(getattr(pauli, "num_qubits") or 0)
    return 0


def num_spatial_orbitals(hamiltonian: object) -> int | None:
    """Resolve a positive spatial-orbital count from a Hamiltonian bundle."""
    value = getattr(hamiltonian, "num_spatial_orbitals", None)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    resolved = int(value)
    return resolved if resolved > 0 else None


def validate_branch_estimator_feasibility(
    hamiltonian: object,
    backend_context: Any | None,
    *,
    algorithm: str,
) -> None:
    """Reject projected branch-estimator runs beyond supported active spaces."""
    backend_target = getattr(backend_context, "backend_target", None)
    if backend_target not in {"aer_simulator", "ibm_runtime"}:
        return
    orbital_count = num_spatial_orbitals(hamiltonian)
    if orbital_count is None:
        return

    algorithm_name = algorithm.upper()
    if (
        backend_target == "aer_simulator"
        and getattr(backend_context, "noise_profile", None) is not None
        and orbital_count > _MAX_NOISY_AER_PROJECTED_MATRIX_ORBITALS
    ):
        raise RunExcludedError(
            f"Noisy Aer {algorithm_name} projected-matrix runs are limited to active spaces "
            f"up to {_MAX_NOISY_AER_PROJECTED_MATRIX_ORBITALS} orbitals in the current rollout.",
            reason="projected_matrix_active_space_too_large",
        )
    if backend_target == "ibm_runtime" and orbital_count > _MAX_IBM_PROJECTED_MATRIX_ORBITALS:
        raise RunExcludedError(
            f"IBM Runtime {algorithm_name} projected-matrix runs are limited to active spaces "
            f"up to {_MAX_IBM_PROJECTED_MATRIX_ORBITALS} orbitals in the current rollout.",
            reason="projected_matrix_active_space_too_large",
        )


def can_use_sector_action(hamiltonian: object, backend_context: Any | None) -> bool:
    """Return whether a large noiseless run can use sector matrix-free action."""
    backend_target = getattr(backend_context, "backend_target", None)
    if getattr(backend_context, "noise_profile", None) is not None:
        return False
    return (
        backend_target in {None, "statevector", "aer_simulator"}
        and num_qubits(hamiltonian) > _DENSE_QUBIT_LIMIT
        and can_build_hamiltonian_action(hamiltonian)
        and not hasattr(hamiltonian, "dense_operator_matrix")
    )


def should_use_branch_matrix_elements(
    *,
    hamiltonian: object,
    backend: object | None,
    backend_context: Any | None,
) -> bool:
    """Return whether projected matrix elements should use the branch estimator."""
    backend_target = getattr(backend_context, "backend_target", None)
    if backend_target == "ibm_runtime":
        return True
    return bool(
        backend_target == "aer_simulator"
        and backend is not None
        and (
            getattr(backend_context, "noise_profile", None) is not None
            or (
                num_qubits(hamiltonian) > _DENSE_QUBIT_LIMIT
                and not can_use_sector_action(hamiltonian, backend_context)
            )
        )
    )


def backend_label(
    *,
    use_branch_matrix_elements: bool,
    use_sector_action: bool,
    backend_context: Any | None,
) -> str:
    """Return the stable diagnostic label for a projected execution path."""
    backend_target = getattr(backend_context, "backend_target", None)
    if use_branch_matrix_elements:
        return (
            "hardware_branch_estimator"
            if backend_target == "ibm_runtime"
            else "aer_branch_estimator"
        )
    if use_sector_action:
        return "sector_matrix_free"
    return "aer_simulator" if backend_target == "aer_simulator" else "dense_matrix"


__all__ = [
    "ProjectedExecutionResources",
    "backend_label",
    "can_use_sector_action",
    "num_qubits",
    "num_spatial_orbitals",
    "prepare_projected_execution",
    "should_use_branch_matrix_elements",
    "validate_branch_estimator_feasibility",
]
