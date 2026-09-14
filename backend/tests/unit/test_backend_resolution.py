"""Unit tests for normalized backend selection policies."""

from __future__ import annotations

from app.config import Settings
from app.models.enums import BackendTarget
from app.schemas.backend import BackendResolveRequest, BackendSummary
from app.schemas.run_config import BackendOptions, BackendSelectionPolicy
from app.services.backend_resolution import resolve_backend, select_aer_backend, select_ibm_backend


def _ibm_summary(
    name: str,
    *,
    num_qubits: int,
    pending_jobs: int | None = None,
    error_rate: float | None = None,
    available: bool = True,
) -> BackendSummary:
    return BackendSummary(
        target=BackendTarget.IBM_RUNTIME,
        name=name,
        display_name=name,
        available=available,
        credential_configured=True,
        credentials_usable=True,
        simulator=False,
        supports_noise_profile=False,
        supports_transpile_preview=True,
        num_qubits=num_qubits,
        pending_jobs=pending_jobs,
        error_rate=error_rate,
    )


def test_select_ibm_backend_filters_qubit_capacity_before_least_busy() -> None:
    request = BackendResolveRequest(
        target=BackendTarget.IBM_RUNTIME,
        backend_options=BackendOptions(selection_policy=BackendSelectionPolicy.LEAST_BUSY),
        required_qubits=10,
    )
    candidates = [
        _ibm_summary("too_small", num_qubits=5, pending_jobs=0),
        _ibm_summary("right_size_busy", num_qubits=27, pending_jobs=8),
        _ibm_summary("right_size_quiet", num_qubits=127, pending_jobs=2),
    ]
    warnings: list[str] = []

    selected = select_ibm_backend(request, candidates, warnings)

    assert selected is candidates[2]
    assert warnings == []


def test_select_aer_backend_warns_for_unknown_local_name() -> None:
    request = BackendResolveRequest(
        target=BackendTarget.AER_SIMULATOR,
        backend_options=BackendOptions(backend_name="custom_aer_name"),
    )
    candidate = _ibm_summary("aer_simulator", num_qubits=32)
    candidate.target = BackendTarget.AER_SIMULATOR
    warnings: list[str] = []

    selected = select_aer_backend(request, [candidate], warnings)

    assert selected is candidate
    assert warnings == [
        "Aer backend 'custom_aer_name' is not a named local backend; using aer_simulator contract."
    ]


def test_resolve_backend_orchestrates_catalog_and_selection() -> None:
    request = BackendResolveRequest(
        target=BackendTarget.STATEVECTOR,
        backend_options=BackendOptions(),
    )

    response = resolve_backend(
        request,
        settings=Settings(
            _env_file=None,
            database_url="sqlite:///:memory:",
            redis_url="redis://localhost:6379/0",
        ),
    )

    assert response.resolved is True
    assert response.backend_name == "statevector"
