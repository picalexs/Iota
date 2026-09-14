"""IBM Runtime backend discovery and cache helpers."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from multiprocessing import get_context
from queue import Empty
from threading import Lock, Thread
from time import monotonic
from typing import Any, TypeAlias, cast

from app.config import Settings
from app.models.enums import BackendTarget
from app.schemas.backend import BackendSummary
from app.schemas.settings import IbmRuntimeCredentials
from app.services.backend_metadata import (
    extract_processor_type,
    normalize_coupling_map,
    summarize_ibm_backend,
    summarize_ibm_calibration_payload,
)

logger = logging.getLogger(__name__)
_IBM_DISCOVERY_TIMEOUT_WARNING = (
    "IBM Runtime discovery timed out; local backends remain available and IBM hardware "
    "metadata will be retried automatically."
)
_IBM_DISCOVERY_REFRESHING_WARNING = "Refreshing IBM Runtime hardware metadata in the background."
_IBM_DISCOVERY_STALE_CACHE_WARNING = (
    "Using the last successful IBM Runtime hardware snapshot while live discovery refreshes in "
    "the background."
)
_IBM_DISCOVERY_DISABLED_WARNING = (
    "IBM Runtime catalog discovery is disabled for this API process; local backends remain "
    "available and saved IBM credentials can still be used for IBM Runtime submissions."
)
_IBM_DISCOVERY_BACKGROUND_TIMEOUT_SECONDS = 20.0


@dataclass
class _BackendCatalogCache:
    expires_at: float
    summaries: list[BackendSummary]
    warnings: list[str]


_BackendCatalogKey: TypeAlias = tuple[str | None, str | None, str | None]

_backend_catalog_cache: dict[_BackendCatalogKey, _BackendCatalogCache] = {}
_backend_catalog_refreshing_keys: set[_BackendCatalogKey] = set()
_backend_catalog_lock = Lock()


def discover_ibm_backends_cached(
    settings: Settings,
    *,
    ibm_credentials: IbmRuntimeCredentials | None,
    ibm_service_factory: Callable[[Settings], Any] | None,
    allow_background_refresh: bool = False,
) -> tuple[list[BackendSummary], list[str]]:
    """Discover IBM backends with a short in-process cache for slow catalog calls."""
    if ibm_service_factory is not None:
        return _discover_ibm_backends(
            settings,
            ibm_credentials=ibm_credentials,
            ibm_service_factory=ibm_service_factory,
        )
    if ibm_credentials is None or not settings.backend_catalog_discovery_enabled:
        return _discover_ibm_backends(
            settings,
            ibm_credentials=ibm_credentials,
            ibm_service_factory=None,
        )

    cache_key = _backend_catalog_key(ibm_credentials)
    now = monotonic()
    with _backend_catalog_lock:
        cached = _backend_catalog_cache.get(cache_key)
    if cached is not None and cached.expires_at > now:
        if allow_background_refresh and _should_retry_unavailable_catalog(cached.summaries):
            _schedule_ibm_catalog_refresh(settings, ibm_credentials, cache_key)
            return _refreshing_placeholder_response()
        return _cached_catalog_response(cached)

    if allow_background_refresh:
        _schedule_ibm_catalog_refresh(settings, ibm_credentials, cache_key)
        if cached is not None:
            return _stale_cached_catalog_response(cached)
        return _refreshing_placeholder_response()

    summaries, warnings = _discover_ibm_backends(
        settings,
        ibm_credentials=ibm_credentials,
        ibm_service_factory=None,
    )
    if cached is not None and _should_reuse_stale_catalog(summaries):
        stale_warnings = list(cached.warnings)
        if _IBM_DISCOVERY_STALE_CACHE_WARNING not in stale_warnings:
            stale_warnings.append(_IBM_DISCOVERY_STALE_CACHE_WARNING)
        _store_backend_catalog_cache(
            cache_key=cache_key,
            settings=settings,
            summaries=cached.summaries,
            warnings=stale_warnings,
        )
        return (
            [summary.model_copy(deep=True) for summary in cached.summaries],
            stale_warnings,
        )
    _store_backend_catalog_cache(
        cache_key=cache_key,
        settings=settings,
        summaries=summaries,
        warnings=warnings,
    )
    return summaries, warnings


def _refreshing_placeholder_response() -> tuple[list[BackendSummary], list[str]]:
    return [
        _unavailable_ibm_summary(
            _IBM_DISCOVERY_REFRESHING_WARNING,
            credential_configured=True,
            credentials_usable=None,
        )
    ], [_IBM_DISCOVERY_REFRESHING_WARNING]


def _cached_catalog_response(
    cached: _BackendCatalogCache,
) -> tuple[list[BackendSummary], list[str]]:
    return ([summary.model_copy(deep=True) for summary in cached.summaries], list(cached.warnings))


def _stale_cached_catalog_response(
    cached: _BackendCatalogCache,
) -> tuple[list[BackendSummary], list[str]]:
    stale_warnings = list(cached.warnings)
    if _IBM_DISCOVERY_STALE_CACHE_WARNING not in stale_warnings:
        stale_warnings.append(_IBM_DISCOVERY_STALE_CACHE_WARNING)
    return ([summary.model_copy(deep=True) for summary in cached.summaries], stale_warnings)


def _backend_catalog_key(credentials: IbmRuntimeCredentials) -> _BackendCatalogKey:
    return (
        str(credentials.profile_id),
        credentials.instance,
        credentials.channel,
    )


def _store_backend_catalog_cache(
    *,
    cache_key: _BackendCatalogKey,
    settings: Settings,
    summaries: Sequence[BackendSummary],
    warnings: Sequence[str],
) -> None:
    with _backend_catalog_lock:
        _backend_catalog_cache[cache_key] = _BackendCatalogCache(
            expires_at=monotonic() + max(0, settings.backend_catalog_cache_seconds),
            summaries=[summary.model_copy(deep=True) for summary in summaries],
            warnings=list(warnings),
        )


def _schedule_ibm_catalog_refresh(
    settings: Settings,
    credentials: IbmRuntimeCredentials,
    cache_key: _BackendCatalogKey,
) -> None:
    with _backend_catalog_lock:
        if cache_key in _backend_catalog_refreshing_keys:
            return
        _backend_catalog_refreshing_keys.add(cache_key)

    refresh_settings = _background_refresh_settings(settings)
    refresh_credentials = credentials.model_copy(deep=True)
    Thread(
        target=_refresh_ibm_catalog_cache,
        args=(refresh_settings, refresh_credentials, cache_key),
        name="ibm-backend-refresh",
        daemon=True,
    ).start()


def _refresh_ibm_catalog_cache(
    settings: Settings,
    credentials: IbmRuntimeCredentials,
    cache_key: _BackendCatalogKey,
) -> None:
    try:
        summaries, warnings = _discover_ibm_backends(
            settings,
            ibm_credentials=credentials,
            ibm_service_factory=None,
        )
        with _backend_catalog_lock:
            cached = _backend_catalog_cache.get(cache_key)
        if cached is not None and _should_reuse_stale_catalog(summaries):
            stale_warnings = list(cached.warnings)
            if _IBM_DISCOVERY_STALE_CACHE_WARNING not in stale_warnings:
                stale_warnings.append(_IBM_DISCOVERY_STALE_CACHE_WARNING)
            _store_backend_catalog_cache(
                cache_key=cache_key,
                settings=settings,
                summaries=cached.summaries,
                warnings=stale_warnings,
            )
            return
        _store_backend_catalog_cache(
            cache_key=cache_key,
            settings=settings,
            summaries=summaries,
            warnings=warnings,
        )
    finally:
        with _backend_catalog_lock:
            _backend_catalog_refreshing_keys.discard(cache_key)


def _background_refresh_settings(settings: Settings) -> Settings:
    refresh_settings = settings.model_copy(deep=True)
    refresh_settings.backend_catalog_discovery_timeout_seconds = max(
        refresh_settings.backend_catalog_discovery_timeout_seconds,
        _IBM_DISCOVERY_BACKGROUND_TIMEOUT_SECONDS,
    )
    return refresh_settings


def _discover_ibm_backends(
    settings: Settings,
    *,
    ibm_credentials: IbmRuntimeCredentials | None,
    ibm_service_factory: Callable[[Settings], Any] | None,
) -> tuple[list[BackendSummary], list[str]]:
    warnings: list[str] = []
    if ibm_credentials is None:
        warning = "IBM Quantum credentials are not connected, so hardware backends are hidden."
        return [
            BackendSummary(
                target=BackendTarget.IBM_RUNTIME,
                name="ibm_runtime",
                display_name="IBM Runtime",
                available=False,
                credential_configured=False,
                credentials_usable=False,
                simulator=False,
                supports_noise_profile=False,
                supports_transpile_preview=True,
                status_message=(
                    "Save an encrypted IBM profile in Settings to enable hardware backends."
                ),
                warnings=[warning],
            )
        ], [warning]

    if ibm_service_factory is None and not settings.backend_catalog_discovery_enabled:
        return [
            _unavailable_ibm_summary(
                _IBM_DISCOVERY_DISABLED_WARNING,
                credential_configured=True,
                credentials_usable=None,
            )
        ], [_IBM_DISCOVERY_DISABLED_WARNING]

    try:
        if ibm_service_factory is None:
            summaries = _discover_real_ibm_backend_summaries_with_timeout(
                settings,
                ibm_credentials,
            )
        else:
            raw_backends = ibm_service_factory(settings).backends(simulator=False, operational=True)
            summaries = [summarize_ibm_backend(backend) for backend in raw_backends]
    except FuturesTimeoutError:
        logger.info("IBM Runtime discovery timed out")
        return [
            _unavailable_ibm_summary(
                _IBM_DISCOVERY_TIMEOUT_WARNING,
                credential_configured=True,
                credentials_usable=None,
            )
        ], [_IBM_DISCOVERY_TIMEOUT_WARNING]
    except ModuleNotFoundError:
        warning = "qiskit-ibm-runtime is not installed; IBM Runtime discovery is unavailable."
        return [
            _unavailable_ibm_summary(
                warning,
                credential_configured=True,
                credentials_usable=False,
            )
        ], [warning]
    except Exception as exc:  # pragma: no cover - exercised with mocked failures in tests
        logger.info("IBM Runtime discovery failed: %s", type(exc).__name__)
        warning = "IBM Runtime discovery failed; check credentials, account access, or network."
        return [
            _unavailable_ibm_summary(
                warning,
                credential_configured=True,
                credentials_usable=None,
            )
        ], [warning]
    if not summaries:
        warnings.append("IBM Runtime returned no operational hardware backends.")
    return summaries, warnings


def _discover_real_ibm_backend_summaries_with_timeout(
    settings: Settings,
    credentials: IbmRuntimeCredentials,
) -> list[BackendSummary]:
    timeout = max(0.001, settings.backend_catalog_discovery_timeout_seconds)
    context = get_context("fork")
    results = context.Queue(maxsize=1)
    process = context.Process(
        target=_discover_real_ibm_backend_summaries_worker,
        args=(results, credentials.model_dump(mode="python")),
        name="ibm-backend-discovery",
        daemon=True,
    )
    process.start()
    try:
        kind, value = results.get(timeout=timeout)
    except Empty as exc:
        if process.is_alive():
            process.kill()
        process.join(timeout=1)
        raise FuturesTimeoutError from exc
    finally:
        results.close()
        results.join_thread()

    process.join(timeout=1)
    if kind == "module_error":
        raise ModuleNotFoundError
    if kind == "error":
        raise RuntimeError(value.get("message") or value.get("type") or "IBM discovery failed")
    return [BackendSummary.model_validate(item) for item in value]


def _discover_real_ibm_backend_summaries_worker(
    results: Any,
    credentials_payload: dict[str, Any],
) -> None:
    try:
        credentials = IbmRuntimeCredentials.model_validate(credentials_payload)
        service = _build_ibm_service_from_credentials(credentials)
        summaries = [
            _summarize_ibm_backend_payload(
                backend,
                calibration=_fetch_ibm_calibration_payload(service, backend),
            ).model_dump(mode="python")
            for backend in _list_ibm_backend_payloads(service)
        ]
        results.put(("ok", summaries))
    except ModuleNotFoundError:
        results.put(("module_error", None))
    except Exception as exc:  # pragma: no cover - surfaced through parent process
        results.put(
            (
                "error",
                {
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
            )
        )


def _build_ibm_service_from_credentials(credentials: IbmRuntimeCredentials) -> Any:
    """Build a direct IBM Runtime client for the catalog endpoint.

    QiskitRuntimeService.backends() validates every account instance before it
    lists backends. The catalog already has an explicit CRN, so use the direct
    RuntimeClient endpoint and avoid the extra Global Search and backend-object
    metadata calls.
    """
    from qiskit_ibm_runtime.accounts.account import IBM_QUANTUM_PLATFORM_API_URL
    from qiskit_ibm_runtime.api.client_parameters import ClientParameters
    from qiskit_ibm_runtime.api.clients.runtime import RuntimeClient

    return RuntimeClient(
        ClientParameters(
            url=IBM_QUANTUM_PLATFORM_API_URL,
            channel=cast(Any, credentials.channel),
            token=credentials.token,
            instance=credentials.instance,
        )
    )


def _list_ibm_backend_payloads(service: Any) -> list[Any]:
    """Return raw backend payloads without constructing one SDK object per backend."""
    if hasattr(service, "list_backends"):
        payloads = service.list_backends()
    else:
        # Keep the injectable service seam compatible with existing tests and
        # callers that provide a QiskitRuntimeService-shaped fake.
        payloads = service.backends(simulator=False, operational=True)
    return [
        payload
        for payload in payloads
        if not isinstance(payload, Mapping) or payload.get("simulator") is not True
    ]


def _fetch_ibm_calibration_payload(service: Any, payload: Any) -> Mapping[str, Any] | None:
    """Read calibration for one direct-catalog backend without failing catalog discovery."""
    if not isinstance(payload, Mapping) or not hasattr(service, "backend_properties"):
        return None
    name = payload.get("name")
    if not isinstance(name, str) or not name:
        return None
    try:
        calibration = service.backend_properties(name)
    except Exception as exc:
        logger.info("IBM calibration metadata unavailable for %s: %s", name, type(exc).__name__)
        return None
    return calibration if isinstance(calibration, Mapping) else None


def _summarize_ibm_backend_payload(
    payload: Any,
    *,
    calibration: Mapping[str, Any] | None = None,
) -> BackendSummary:
    """Normalize one raw Runtime ``/backends`` payload for the catalog."""
    if not isinstance(payload, Mapping):
        return summarize_ibm_backend(payload)

    status = payload.get("status") if isinstance(payload.get("status"), Mapping) else {}
    configuration = (
        payload.get("configuration")
        if isinstance(payload.get("configuration"), Mapping)
        else {}
    )

    def first_value(*keys: str) -> Any:
        for source in (payload, configuration, status):
            for key in keys:
                value = source.get(key)
                if value is not None:
                    return value
        return None

    operational = status.get("operational")
    if not isinstance(operational, bool):
        operational = None
    coupling_map = normalize_coupling_map(first_value("coupling_map"))
    num_qubits = _non_negative_int(first_value("num_qubits", "n_qubits", "qubits"))
    pending_jobs = _non_negative_int(first_value("pending_jobs", "queue_length"))
    max_shots = _positive_int(first_value("max_shots"))
    basis_gates = first_value("basis_gates")
    if basis_gates is not None:
        basis_gates = [str(gate) for gate in basis_gates]
    error_rate = _non_negative_float(first_value("error_rate"))
    processor_type = extract_processor_type(
        payload.get("processor_type"), configuration.get("processor_type")
    )
    status_message = status.get("status_msg")
    if not isinstance(status_message, str):
        status_message = None

    calibration_error_rate, qubit_errors, gate_errors = summarize_ibm_calibration_payload(calibration)

    return BackendSummary(
        target=BackendTarget.IBM_RUNTIME,
        name=str(payload.get("name") or "unknown_ibm_backend"),
        display_name=str(payload.get("display_name") or payload.get("name") or "unknown_ibm_backend"),
        available=operational is not False,
        credential_configured=True,
        credentials_usable=True,
        simulator=bool(payload.get("simulator", False)),
        supports_noise_profile=False,
        supports_transpile_preview=True,
        num_qubits=num_qubits,
        pending_jobs=pending_jobs,
        operational=operational,
        basis_gates=basis_gates,
        coupling_map=coupling_map,
        coupling_map_edges=len(coupling_map) if coupling_map is not None else None,
        max_shots=max_shots,
        error_rate=error_rate if error_rate is not None else calibration_error_rate,
        processor_type=processor_type,
        qubit_errors=qubit_errors,
        gate_errors=gate_errors,
        status_message=status_message,
    )


def _non_negative_int(value: Any) -> int | None:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 else None


def _positive_int(value: Any) -> int | None:
    result = _non_negative_int(value)
    return result if result is not None and result > 0 else None


def _non_negative_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 else None


def _unavailable_ibm_summary(
    warning: str,
    *,
    credential_configured: bool,
    credentials_usable: bool | None,
) -> BackendSummary:
    return BackendSummary(
        target=BackendTarget.IBM_RUNTIME,
        name="ibm_runtime",
        display_name="IBM Runtime",
        available=False,
        credential_configured=credential_configured,
        credentials_usable=credentials_usable,
        simulator=False,
        supports_noise_profile=False,
        supports_transpile_preview=True,
        status_message=warning,
        warnings=[warning],
    )


def _should_reuse_stale_catalog(summaries: Sequence[BackendSummary]) -> bool:
    return (
        _should_retry_unavailable_catalog(summaries)
        and summaries[0].status_message != _IBM_DISCOVERY_DISABLED_WARNING
    )


def _should_retry_unavailable_catalog(summaries: Sequence[BackendSummary]) -> bool:
    return (
        len(summaries) == 1
        and summaries[0].target == BackendTarget.IBM_RUNTIME
        and summaries[0].name == "ibm_runtime"
        and summaries[0].available is False
        and summaries[0].credential_configured is True
        and summaries[0].credentials_usable is not False
    )
