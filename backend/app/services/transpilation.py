"""Deterministic backend transpile-preview orchestration."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.config import Settings
from app.schemas.backend import (
    BackendResolveRequest,
    TranspilePreviewRequest,
    TranspilePreviewResponse,
)
from app.schemas.run_config import BackendSelectionPolicy
from app.schemas.settings import IbmRuntimeCredentials
from app.services.backend_metadata import preview_metadata_for_backend
from app.services.backend_resolution import resolve_backend


def transpile_preview(
    request: TranspilePreviewRequest,
    *,
    settings: Settings | None = None,
    ibm_credentials: IbmRuntimeCredentials | None = None,
    ibm_service_factory: Callable[[Settings], Any] | None = None,
) -> TranspilePreviewResponse:
    """Return deterministic transpile feasibility metadata without building a circuit."""
    required_qubits = (
        None
        if request.backend_options.selection_policy == BackendSelectionPolicy.MANUAL
        else request.num_qubits
    )
    resolved = resolve_backend(
        BackendResolveRequest(
            target=request.target,
            backend_options=request.backend_options,
            required_qubits=required_qubits,
            algorithm=request.algorithm,
        ),
        settings=settings,
        ibm_credentials=ibm_credentials,
        ibm_service_factory=ibm_service_factory,
    )
    warnings = list(resolved.warnings)
    backend = resolved.backend

    metadata: dict[str, Any] = {
        "optimization_level": request.backend_options.optimization_level,
        "shots": request.backend_options.shots,
    }
    if request.backend_options.seed_transpiler is not None:
        metadata["seed_transpiler"] = request.backend_options.seed_transpiler
    if request.circuit_depth is not None:
        metadata["input_depth"] = request.circuit_depth

    feasible = bool(resolved.resolved)
    if backend is None:
        feasible = False
        warnings.append("No backend could be resolved for transpile preview.")
    else:
        metadata.update(preview_metadata_for_backend(backend))
        if backend.num_qubits is not None and request.num_qubits > backend.num_qubits:
            feasible = False
            warnings.append(
                f"Requested {request.num_qubits} qubits but backend reports {backend.num_qubits}."
            )
        if not backend.supports_transpile_preview:
            warnings.append("Transpile preview is metadata-only for this backend target.")

    return TranspilePreviewResponse(
        target=request.target,
        backend_name=resolved.backend_name,
        feasible=feasible,
        requested_qubits=request.num_qubits,
        metadata=metadata,
        warnings=warnings,
    )
