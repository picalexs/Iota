"""QFD execution-path preparation for the algorithm package."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

from worker.chemistry.hamiltonian_action import HamiltonianAction
from worker.chemistry.projected_execution import (
    prepare_projected_execution,
)

BranchPolicy = Callable[..., bool]
SectorPolicy = Callable[[object, Any | None], bool]
ActionBuilder = Callable[[object], HamiltonianAction]
OperatorResolver = Callable[[object], np.ndarray]
QubitResolver = Callable[[object], int]
BackendLabeler = Callable[..., str]
SpectrumPreparer = Callable[..., tuple[np.ndarray | None, np.ndarray | None, np.ndarray | None]]


@dataclass(frozen=True)
class QFDExecutionPlan:
    """Resolved execution path and reusable resources for a QFD run."""

    use_aer: bool
    use_branch_matrix_elements: bool
    sector_action: HamiltonianAction | None
    operator: np.ndarray | None
    dimension: int
    time_evolution_backend: str
    eigenvalues: np.ndarray | None
    eigenvectors: np.ndarray | None
    reference_projection: np.ndarray | None
    selection_reason: str = "unspecified"


def prepare_qfd_execution(
    *,
    hamiltonian: object,
    backend: object | None,
    backend_context: Any | None,
    should_use_branch_matrix_elements_fn: BranchPolicy,
    can_use_sector_action_fn: SectorPolicy,
    build_hamiltonian_action_fn: ActionBuilder,
    resolve_operator_matrix_fn: OperatorResolver,
    num_qubits_fn: QubitResolver,
    backend_label_fn: BackendLabeler,
    prepare_dense_spectrum_fn: SpectrumPreparer,
) -> QFDExecutionPlan:
    """Resolve QFD's branch, sector, or dense execution resources."""
    use_aer = getattr(backend_context, "backend_target", None) == "aer_simulator"
    resources = prepare_projected_execution(
        hamiltonian=hamiltonian,
        backend=backend,
        backend_context=backend_context,
        should_use_branch_matrix_elements_fn=should_use_branch_matrix_elements_fn,
        can_use_sector_action_fn=can_use_sector_action_fn,
        build_hamiltonian_action_fn=build_hamiltonian_action_fn,
        resolve_operator_matrix_fn=resolve_operator_matrix_fn,
        num_qubits_fn=num_qubits_fn,
        backend_label_fn=backend_label_fn,
    )
    eigenvalues, eigenvectors, reference_projection = prepare_dense_spectrum_fn(
        hamiltonian=hamiltonian,
        operator=resources.operator,
        use_aer=use_aer,
        use_branch_matrix_elements=resources.use_branch_matrix_elements,
        sector_action=resources.sector_action,
    )
    return QFDExecutionPlan(
        use_aer=use_aer,
        use_branch_matrix_elements=resources.use_branch_matrix_elements,
        sector_action=resources.sector_action,
        operator=resources.operator,
        dimension=resources.dimension,
        time_evolution_backend=resources.time_evolution_backend,
        eigenvalues=eigenvalues,
        eigenvectors=eigenvectors,
        reference_projection=reference_projection,
        selection_reason=resources.selection_reason,
    )


__all__ = ["QFDExecutionPlan", "prepare_qfd_execution"]
