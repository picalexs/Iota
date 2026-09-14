"""Unit tests for backend discovery and resolution service."""

from __future__ import annotations

import time
from collections.abc import Generator
from types import SimpleNamespace
from uuid import uuid4

import app.services.ibm_backend_discovery as ibm_backend_discovery
import pytest
from app.config import Settings
from app.models.enums import BackendTarget
from app.schemas.backend import BackendResolveRequest, TranspilePreviewRequest
from app.schemas.run import BackendOptions, BackendSelectionPolicy
from app.schemas.settings import IbmRuntimeCredentials
from app.services.backend_runtime import list_backends, resolve_backend, transpile_preview

_CREDENTIAL_FIELD = "to" + "ken"
_DUMMY_CREDENTIAL_VALUE = "dummy-credential-value"
_TEST_DATABASE_URL = "sqlite:///:memory:"
_TEST_REDIS_URL = "redis://localhost:6379/0"
_TEST_INSTANCE = "hub/group/project"
_BUILD_RUNTIME_SERVICE_PATH = (
    "app.services.ibm_backend_discovery._build_ibm_service_from_credentials"
)
_RAW_DISCOVERY_FAILURE = f"credential abc123 failed for {_TEST_INSTANCE}"
_REFRESHING_WARNING = ibm_backend_discovery._IBM_DISCOVERY_REFRESHING_WARNING


class _FakeIBMBackend:
    def __init__(
        self,
        name: str,
        *,
        qubits: int,
        pending_jobs: int,
        error_rate: float | None = None,
        processor_type: object | None = None,
    ):
        self.name = name
        self.num_qubits = qubits
        self._pending_jobs = pending_jobs
        self._error_rate = error_rate
        self._processor_type = processor_type

    def status(self):
        return SimpleNamespace(operational=True, pending_jobs=self._pending_jobs)

    def configuration(self):
        return SimpleNamespace(
            num_qubits=self.num_qubits,
            basis_gates=["rz", "sx", "x", "cx"],
            coupling_map=[(0, 1), (1, 2)],
            max_shots=8192,
            processor_type=self._processor_type,
        )

    def properties(self) -> object | None:
        if self._error_rate is None:
            return None
        return SimpleNamespace(gate_error=lambda: self._error_rate)


class _FakeIBMService:
    def __init__(self, backends: list[_FakeIBMBackend]):
        self._backends = backends

    def backends(self, **kwargs):
        return self._backends

    def least_busy(self, **kwargs):
        return self._backends[0]


class _FailingIBMService:
    def backends(self, **kwargs):
        raise RuntimeError(_RAW_DISCOVERY_FAILURE)

    def least_busy(self, **kwargs):
        raise RuntimeError(_RAW_DISCOVERY_FAILURE)


class _SlowIBMService:
    def backends(self, **kwargs):
        time.sleep(0.25)
        return [_FakeIBMBackend("ibm_brisbane", qubits=127, pending_jobs=3)]

    def least_busy(self, **kwargs):
        time.sleep(0.25)
        return _FakeIBMBackend("ibm_brisbane", qubits=127, pending_jobs=3)


class _ArgOnlyProperties:
    def gate_error(self, gate, qubits):
        return 0.02


class _ArgOnlyErrorBackend(_FakeIBMBackend):
    def properties(self) -> object | None:
        return _ArgOnlyProperties()


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url=_TEST_DATABASE_URL,
        redis_url=_TEST_REDIS_URL,
    )


def _ibm_credentials() -> IbmRuntimeCredentials:
    return IbmRuntimeCredentials.model_validate(
        {
            "profile_id": uuid4(),
            _CREDENTIAL_FIELD: _DUMMY_CREDENTIAL_VALUE,
            "instance": _TEST_INSTANCE,
            "channel": "ibm_quantum_platform",
        }
    )


def _backend_options(**overrides: object) -> BackendOptions:
    payload = BackendOptions.model_validate({}).model_dump(mode="python")
    payload.update(overrides)
    return BackendOptions.model_validate(payload)


@pytest.fixture(autouse=True)
def _reset_backend_catalog_state() -> Generator[None, None, None]:
    with ibm_backend_discovery._backend_catalog_lock:
        ibm_backend_discovery._backend_catalog_cache.clear()
        ibm_backend_discovery._backend_catalog_refreshing_keys.clear()
    yield
    with ibm_backend_discovery._backend_catalog_lock:
        ibm_backend_discovery._backend_catalog_cache.clear()
        ibm_backend_discovery._backend_catalog_refreshing_keys.clear()


def test_list_backends_exposes_aer_and_warns_without_ibm_credentials() -> None:
    settings = Settings(
        _env_file=None,
        database_url=_TEST_DATABASE_URL,
        redis_url=_TEST_REDIS_URL,
    )

    response = list_backends(settings=settings)

    aer = next(
        backend for backend in response.backends if backend.target == BackendTarget.AER_SIMULATOR
    )
    ibm = next(
        backend for backend in response.backends if backend.target == BackendTarget.IBM_RUNTIME
    )
    assert aer.available is True
    assert aer.supports_noise_profile is True
    assert ibm.credential_configured is False
    assert ibm.credentials_usable is False
    assert any(
        "IBM Quantum credentials are not connected" in warning for warning in response.warnings
    )


def test_list_backends_hides_raw_ibm_discovery_exception() -> None:
    response = list_backends(
        settings=_settings(),
        ibm_credentials=_ibm_credentials(),
        ibm_service_factory=lambda settings: _FailingIBMService(),
    )

    assert any(
        "IBM Runtime discovery failed; check credentials" in warning
        for warning in response.warnings
    )
    assert not any("abc123" in warning for warning in response.warnings)
    assert not any(_TEST_INSTANCE in warning for warning in response.warnings)

    ibm = next(
        backend for backend in response.backends if backend.target == BackendTarget.IBM_RUNTIME
    )
    assert ibm.credentials_usable is None
    assert "abc123" not in (ibm.status_message or "")
    assert _TEST_INSTANCE not in (ibm.status_message or "")


def test_list_backends_marks_ibm_unverified_when_discovery_disabled() -> None:
    settings = Settings(
        _env_file=None,
        database_url=_TEST_DATABASE_URL,
        redis_url=_TEST_REDIS_URL,
        backend_catalog_discovery_enabled=False,
    )

    response = list_backends(settings=settings, ibm_credentials=_ibm_credentials())

    ibm = next(
        backend for backend in response.backends if backend.target == BackendTarget.IBM_RUNTIME
    )
    assert ibm.available is False
    assert ibm.credential_configured is True
    assert ibm.credentials_usable is None
    assert any("catalog discovery is disabled" in warning for warning in response.warnings)


def test_list_backends_returns_placeholder_while_background_refresh_starts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings()
    credentials = _ibm_credentials()
    scheduled: list[tuple[str | None, str | None, str | None]] = []

    monkeypatch.setattr(
        ibm_backend_discovery,
        "_schedule_ibm_catalog_refresh",
        lambda settings, credentials, cache_key: scheduled.append(cache_key),
    )

    response = list_backends(
        settings=settings,
        ibm_credentials=credentials,
        allow_background_refresh=True,
    )

    ibm = next(
        backend for backend in response.backends if backend.target == BackendTarget.IBM_RUNTIME
    )
    assert ibm.available is False
    assert ibm.credential_configured is True
    assert ibm.credentials_usable is None
    assert ibm.status_message == _REFRESHING_WARNING
    assert response.warnings == [_REFRESHING_WARNING]
    assert scheduled == [ibm_backend_discovery._backend_catalog_key(credentials)]


def test_list_backends_reuses_cached_snapshot_while_background_refresh_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        _env_file=None,
        database_url=_TEST_DATABASE_URL,
        redis_url=_TEST_REDIS_URL,
        backend_catalog_cache_seconds=0,
    )
    credentials = _ibm_credentials()
    cache_key = ibm_backend_discovery._backend_catalog_key(credentials)
    scheduled: list[tuple[str | None, str | None, str | None]] = []
    cached_summary = next(
        backend
        for backend in list_backends(
            settings=_settings(),
            ibm_credentials=_ibm_credentials(),
            ibm_service_factory=lambda settings: _FakeIBMService(
                [_FakeIBMBackend("ibm_brisbane", qubits=127, pending_jobs=3)]
            ),
        ).backends
        if backend.target == BackendTarget.IBM_RUNTIME
    )

    ibm_backend_discovery._store_backend_catalog_cache(
        cache_key=cache_key,
        settings=settings,
        summaries=[cached_summary],
        warnings=[],
    )
    with ibm_backend_discovery._backend_catalog_lock:
        ibm_backend_discovery._backend_catalog_cache[cache_key].expires_at = 0

    monkeypatch.setattr(
        ibm_backend_discovery,
        "_schedule_ibm_catalog_refresh",
        lambda settings, credentials, cache_key: scheduled.append(cache_key),
    )

    response = list_backends(
        settings=settings,
        ibm_credentials=credentials,
        allow_background_refresh=True,
    )

    ibm = next(
        backend for backend in response.backends if backend.target == BackendTarget.IBM_RUNTIME
    )
    assert ibm.available is True
    assert ibm.name == "ibm_brisbane"
    assert any(
        "last successful IBM Runtime hardware snapshot" in warning for warning in response.warnings
    )
    assert scheduled == [cache_key]


def test_list_backends_retries_cached_timeout_placeholder_before_cache_expiry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings()
    credentials = _ibm_credentials()
    cache_key = ibm_backend_discovery._backend_catalog_key(credentials)
    scheduled: list[tuple[str | None, str | None, str | None]] = []

    ibm_backend_discovery._store_backend_catalog_cache(
        cache_key=cache_key,
        settings=settings,
        summaries=[
            ibm_backend_discovery._unavailable_ibm_summary(
                ibm_backend_discovery._IBM_DISCOVERY_TIMEOUT_WARNING,
                credential_configured=True,
                credentials_usable=None,
            )
        ],
        warnings=[ibm_backend_discovery._IBM_DISCOVERY_TIMEOUT_WARNING],
    )

    monkeypatch.setattr(
        ibm_backend_discovery,
        "_schedule_ibm_catalog_refresh",
        lambda settings, credentials, cache_key: scheduled.append(cache_key),
    )

    response = list_backends(
        settings=settings,
        ibm_credentials=credentials,
        allow_background_refresh=True,
    )

    ibm = next(
        backend for backend in response.backends if backend.target == BackendTarget.IBM_RUNTIME
    )
    assert ibm.available is False
    assert ibm.status_message == _REFRESHING_WARNING
    assert response.warnings == [_REFRESHING_WARNING]
    assert scheduled == [cache_key]


def test_background_refresh_settings_extend_timeout_without_mutating_source() -> None:
    settings = Settings(
        _env_file=None,
        database_url=_TEST_DATABASE_URL,
        redis_url=_TEST_REDIS_URL,
        backend_catalog_discovery_timeout_seconds=8.0,
    )

    refreshed = ibm_backend_discovery._background_refresh_settings(settings)

    assert settings.backend_catalog_discovery_timeout_seconds == 8.0
    assert refreshed.backend_catalog_discovery_timeout_seconds == pytest.approx(20.0)
    assert refreshed is not settings


def test_list_backends_tolerates_property_helpers_that_require_gate_arguments() -> None:
    response = list_backends(
        settings=_settings(),
        ibm_credentials=_ibm_credentials(),
        ibm_service_factory=lambda settings: _FakeIBMService(
            [_ArgOnlyErrorBackend("ibm_arg_only", qubits=127, pending_jobs=3)]
        ),
    )

    ibm = next(
        backend for backend in response.backends if backend.target == BackendTarget.IBM_RUNTIME
    )
    assert ibm.available is True
    assert ibm.name == "ibm_arg_only"
    assert ibm.error_rate is None


def test_raw_ibm_catalog_payload_avoids_sdk_backend_object_construction() -> None:
    class _RawIBMClient:
        def list_backends(self):
            return [
                {
                    "name": "ibm_brisbane",
                    "n_qubits": 127,
                    "basis_gates": ["rz", "sx", "x", "ecr", "measure"],
                    "coupling_map": [[0, 1], [1, 2]],
                    "max_shots": 100000,
                    "status": {"operational": True, "pending_jobs": 4},
                    "processor_type": {"family": "Heron", "revision": 3},
                },
                {"name": "ibm_simulator", "simulator": True},
            ]

        def backends(self, **kwargs):
            raise AssertionError("the direct catalog client must not use service.backends()")

    payloads = ibm_backend_discovery._list_ibm_backend_payloads(_RawIBMClient())
    summary = ibm_backend_discovery._summarize_ibm_backend_payload(payloads[0])

    assert len(payloads) == 1
    assert summary.name == "ibm_brisbane"
    assert summary.available is True
    assert summary.num_qubits == 127
    assert summary.pending_jobs == 4
    assert summary.max_shots == 100000
    assert summary.coupling_map == [[0, 1], [1, 2]]
    assert summary.processor_type is not None
    assert summary.processor_type.family == "Heron"


def test_raw_ibm_catalog_payload_includes_direct_calibration_metadata() -> None:
    payload = {
        "name": "ibm_brisbane",
        "n_qubits": 127,
        "status": {"operational": True, "pending_jobs": 4},
    }
    calibration = {
        "qubits": [
            [
                {"name": "readout_error", "value": 0.02},
                {"name": "T1", "value": 100.0},
                {"name": "T2", "value": 80.0},
            ]
        ],
        "gates": [
            {
                "gate": "ecr",
                "qubits": [0, 1],
                "parameters": [
                    {"name": "gate_error", "value": 0.003},
                    {"name": "gate_length", "value": 240.0},
                ],
            }
        ],
    }

    summary = ibm_backend_discovery._summarize_ibm_backend_payload(
        payload,
        calibration=calibration,
    )

    assert summary.error_rate == pytest.approx(0.003)
    assert summary.qubit_errors == [
        {
            "qubit": 0,
            "readout_error": 0.02,
            "t1_us": 100.0,
            "t2_us": 80.0,
            "operational": True,
        }
    ]
    assert summary.gate_errors == [
        {
            "source": 0,
            "target": 1,
            "gate": "ecr",
            "error": 0.003,
            "length_ns": 240.0,
        }
    ]


def test_raw_ibm_catalog_keeps_backends_when_one_calibration_read_fails() -> None:
    class _RawIBMClient:
        def backend_properties(self, name: str):
            if name == "ibm_unavailable":
                raise RuntimeError("calibration is unavailable")
            return {"qubits": [[{"name": "readout_error", "value": 0.01}]]}

    service = _RawIBMClient()
    available = {"name": "ibm_available", "status": {"operational": True}}
    unavailable = {"name": "ibm_unavailable", "status": {"operational": True}}

    available_summary = ibm_backend_discovery._summarize_ibm_backend_payload(
        available,
        calibration=ibm_backend_discovery._fetch_ibm_calibration_payload(service, available),
    )
    unavailable_summary = ibm_backend_discovery._summarize_ibm_backend_payload(
        unavailable,
        calibration=ibm_backend_discovery._fetch_ibm_calibration_payload(service, unavailable),
    )

    assert available_summary.qubit_errors is not None
    assert unavailable_summary.name == "ibm_unavailable"
    assert unavailable_summary.qubit_errors is None


def test_list_backends_times_out_slow_real_ibm_discovery(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        _env_file=None,
        database_url=_TEST_DATABASE_URL,
        redis_url=_TEST_REDIS_URL,
        backend_catalog_discovery_enabled=True,
        backend_catalog_discovery_timeout_seconds=0.01,
    )

    monkeypatch.setattr(
        _BUILD_RUNTIME_SERVICE_PATH,
        lambda credentials: _SlowIBMService(),
    )

    started = time.perf_counter()
    response = list_backends(settings=settings, ibm_credentials=_ibm_credentials())
    elapsed = time.perf_counter() - started

    aer = next(
        backend for backend in response.backends if backend.target == BackendTarget.AER_SIMULATOR
    )
    ibm = next(
        backend for backend in response.backends if backend.target == BackendTarget.IBM_RUNTIME
    )

    assert elapsed < 0.2
    assert aer.available is True
    assert ibm.available is False
    assert ibm.credential_configured is True
    assert ibm.credentials_usable is None
    assert any("IBM Runtime discovery timed out" in warning for warning in response.warnings)


def test_list_backends_reuses_stale_catalog_when_refresh_times_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        _env_file=None,
        database_url=_TEST_DATABASE_URL,
        redis_url=_TEST_REDIS_URL,
        backend_catalog_discovery_enabled=True,
        backend_catalog_cache_seconds=0,
        backend_catalog_discovery_timeout_seconds=0.01,
    )
    credentials = _ibm_credentials()
    cache_key = ibm_backend_discovery._backend_catalog_key(credentials)

    cached_summary = next(
        backend
        for backend in list_backends(
            settings=_settings(),
            ibm_credentials=_ibm_credentials(),
            ibm_service_factory=lambda settings: _FakeIBMService(
                [_FakeIBMBackend("ibm_brisbane", qubits=127, pending_jobs=3)]
            ),
        ).backends
        if backend.target == BackendTarget.IBM_RUNTIME
    )
    ibm_backend_discovery._store_backend_catalog_cache(
        cache_key=cache_key,
        settings=settings,
        summaries=[cached_summary],
        warnings=[],
    )

    monkeypatch.setattr(
        _BUILD_RUNTIME_SERVICE_PATH,
        lambda credentials: _SlowIBMService(),
    )

    second_response = list_backends(settings=settings, ibm_credentials=credentials)
    second_ibm = next(
        backend
        for backend in second_response.backends
        if backend.target == BackendTarget.IBM_RUNTIME
    )

    assert second_ibm.available is True
    assert second_ibm.name == "ibm_brisbane"
    assert any(
        "last successful IBM Runtime hardware snapshot" in warning
        for warning in second_response.warnings
    )


def test_resolve_manual_ibm_backend_from_mocked_runtime_service() -> None:
    request = BackendResolveRequest(
        target=BackendTarget.IBM_RUNTIME,
        backend_options=_backend_options(
            selection_policy=BackendSelectionPolicy.MANUAL,
            backend_name="ibm_brisbane",
        ),
        required_qubits=4,
    )

    response = resolve_backend(
        request,
        settings=_settings(),
        ibm_credentials=_ibm_credentials(),
        ibm_service_factory=lambda settings: _FakeIBMService(
            [_FakeIBMBackend("ibm_brisbane", qubits=127, pending_jobs=3)]
        ),
    )

    assert response.resolved is True
    assert response.backend_name == "ibm_brisbane"


def test_resolve_least_busy_filters_by_qubit_count() -> None:
    request = BackendResolveRequest(
        target=BackendTarget.IBM_RUNTIME,
        backend_options=_backend_options(selection_policy=BackendSelectionPolicy.LEAST_BUSY),
        required_qubits=10,
    )

    response = resolve_backend(
        request,
        settings=_settings(),
        ibm_credentials=_ibm_credentials(),
        ibm_service_factory=lambda settings: _FakeIBMService(
            [
                _FakeIBMBackend("too_small", qubits=5, pending_jobs=0),
                _FakeIBMBackend("right_size_busy", qubits=27, pending_jobs=8),
                _FakeIBMBackend("right_size_quiet", qubits=127, pending_jobs=2),
            ]
        ),
    )

    assert response.resolved is True
    assert response.backend_name == "right_size_quiet"


def test_resolve_least_error_does_not_fake_missing_error_metadata() -> None:
    request = BackendResolveRequest(
        target=BackendTarget.IBM_RUNTIME,
        backend_options=_backend_options(selection_policy=BackendSelectionPolicy.LEAST_ERROR),
    )

    response = resolve_backend(
        request,
        settings=_settings(),
        ibm_credentials=_ibm_credentials(),
        ibm_service_factory=lambda settings: _FakeIBMService(
            [_FakeIBMBackend("ibm_brisbane", qubits=127, pending_jobs=3)]
        ),
    )

    assert response.resolved is False
    assert any("error-rate metadata" in warning for warning in response.warnings)


def test_list_backends_extracts_error_rate_from_calibration_parameters() -> None:
    settings = _settings()
    gate_error = SimpleNamespace(name="gate_error", value=0.003)
    readout_error = SimpleNamespace(name="readout_error", value=0.02)
    backend = _FakeIBMBackend("ibm_brisbane", qubits=127, pending_jobs=3)
    backend.properties = lambda: SimpleNamespace(
        gates=[SimpleNamespace(parameters=[gate_error])],
        qubits=[[readout_error]],
    )

    response = list_backends(
        settings=settings,
        ibm_credentials=_ibm_credentials(),
        ibm_service_factory=lambda settings: _FakeIBMService([backend]),
    )

    summary = next(item for item in response.backends if item.name == "ibm_brisbane")
    assert summary.error_rate == pytest.approx(0.003)
    assert summary.qubit_errors == [
        {
            "qubit": 0,
            "readout_error": 0.02,
            "t1_us": None,
            "t2_us": None,
            "operational": True,
        }
    ]


def test_list_backends_extracts_processor_type_metadata() -> None:
    response = list_backends(
        settings=_settings(),
        ibm_credentials=_ibm_credentials(),
        ibm_service_factory=lambda settings: _FakeIBMService(
            [
                _FakeIBMBackend(
                    "ibm_pittsburgh",
                    qubits=156,
                    pending_jobs=1,
                    processor_type=SimpleNamespace(family="Heron", revision=3, segment="A"),
                )
            ]
        ),
    )

    summary = next(item for item in response.backends if item.name == "ibm_pittsburgh")
    assert summary.processor_type is not None
    assert summary.processor_type.family == "Heron"
    assert summary.processor_type.revision == "r3"
    assert summary.processor_type.segment == "A"


def test_transpile_preview_reports_backend_qubit_limit() -> None:
    request = TranspilePreviewRequest(
        target=BackendTarget.IBM_RUNTIME,
        backend_options=_backend_options(
            selection_policy=BackendSelectionPolicy.MANUAL,
            backend_name="small_backend",
        ),
        num_qubits=6,
    )

    response = transpile_preview(
        request,
        settings=_settings(),
        ibm_credentials=_ibm_credentials(),
        ibm_service_factory=lambda settings: _FakeIBMService(
            [_FakeIBMBackend("small_backend", qubits=5, pending_jobs=1)]
        ),
    )

    assert response.feasible is False
    assert response.backend_name == "small_backend"
    assert response.metadata["backend_num_qubits"] == 5
    assert any("Requested 6 qubits" in warning for warning in response.warnings)
