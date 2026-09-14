"""Backend selection policies that operate on normalized summaries."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from app.config import Settings
from app.models.enums import BackendTarget
from app.schemas.backend import BackendResolveRequest, BackendResolveResponse, BackendSummary
from app.schemas.run_config import BackendSelectionPolicy
from app.schemas.settings import IbmRuntimeCredentials
from app.services.backend_catalog import list_backends

AER_BACKEND_NAMES = {"aer_simulator", "aer_simulator_statevector"}


def resolve_backend(
    request: BackendResolveRequest,
    *,
    settings: Settings | None = None,
    ibm_credentials: IbmRuntimeCredentials | None = None,
    ibm_service_factory: Callable[[Settings], Any] | None = None,
) -> BackendResolveResponse:
    """Resolve a backend target and selection policy to a concrete backend when possible."""
    summaries = list_backends(
        settings=settings,
        ibm_credentials=ibm_credentials,
        ibm_service_factory=ibm_service_factory,
    )
    warnings = list(summaries.warnings)
    candidates = [backend for backend in summaries.backends if backend.target == request.target]

    if request.target == BackendTarget.STATEVECTOR:
        backend = candidates[0] if candidates else None
        return BackendResolveResponse(
            target=request.target,
            selection_policy=request.backend_options.selection_policy,
            resolved=backend is not None and backend.available,
            backend_name=backend.name if backend else None,
            backend=backend,
            warnings=warnings,
        )

    if request.target == BackendTarget.AER_SIMULATOR:
        backend = select_aer_backend(request, candidates, warnings)
        return BackendResolveResponse(
            target=request.target,
            selection_policy=request.backend_options.selection_policy,
            resolved=backend is not None and backend.available,
            backend_name=backend.name if backend else None,
            backend=backend,
            warnings=warnings,
        )

    backend = select_ibm_backend(request, candidates, warnings)
    return BackendResolveResponse(
        target=request.target,
        selection_policy=request.backend_options.selection_policy,
        resolved=backend is not None and backend.available,
        backend_name=backend.name if backend else None,
        backend=backend,
        warnings=warnings,
    )


def select_aer_backend(
    request: BackendResolveRequest,
    candidates: Sequence[BackendSummary],
    warnings: list[str],
) -> BackendSummary | None:
    if request.backend_options.backend_name:
        name = request.backend_options.backend_name
        if name not in AER_BACKEND_NAMES:
            warnings.append(
                f"Aer backend '{name}' is not a named local backend; using aer_simulator contract."
            )
    return candidates[0] if candidates else None


def select_ibm_backend(
    request: BackendResolveRequest,
    candidates: Sequence[BackendSummary],
    warnings: list[str],
) -> BackendSummary | None:
    available = _available_ibm_backend_candidates(request, candidates)

    if request.backend_options.selection_policy == BackendSelectionPolicy.MANUAL:
        return _select_manual_ibm_backend(request, available, warnings)

    if request.backend_options.selection_policy == BackendSelectionPolicy.LEAST_BUSY:
        return _select_least_busy_ibm_backend(available, warnings)

    return _select_least_error_ibm_backend(available, warnings)


def _available_ibm_backend_candidates(
    request: BackendResolveRequest,
    candidates: Sequence[BackendSummary],
) -> list[BackendSummary]:
    available = [backend for backend in candidates if backend.available]
    if request.required_qubits is None:
        return available
    return [
        backend
        for backend in available
        if backend.num_qubits is None or backend.num_qubits >= request.required_qubits
    ]


def _select_manual_ibm_backend(
    request: BackendResolveRequest,
    available: Sequence[BackendSummary],
    warnings: list[str],
) -> BackendSummary | None:
    backend_name = request.backend_options.backend_name
    if not backend_name:
        warnings.append("Manual IBM Runtime selection requires backend_options.backend_name.")
        return None
    for backend in available:
        if backend.name == backend_name:
            return backend
    warnings.append(f"IBM Runtime backend '{backend_name}' was not found.")
    return None


def _select_least_busy_ibm_backend(
    available: Sequence[BackendSummary],
    warnings: list[str],
) -> BackendSummary | None:
    if not available:
        warnings.append("No available IBM Runtime backends matched the request.")
        return None
    return min(available, key=lambda item: (item.pending_jobs is None, item.pending_jobs or 0))


def _select_least_error_ibm_backend(
    available: Sequence[BackendSummary],
    warnings: list[str],
) -> BackendSummary | None:
    with_error_rates = [backend for backend in available if backend.error_rate is not None]
    if not with_error_rates:
        warnings.append(
            "least_error selection requires backend error-rate metadata, which was not available."
        )
        return None
    return min(with_error_rates, key=lambda item: item.error_rate or 0.0)
