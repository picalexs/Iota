import math
from types import SimpleNamespace

import pytest
from qiskit import QuantumCircuit
from qiskit.circuit import Parameter
from qiskit.circuit.library import XXPlusYYGate
from qiskit.quantum_info import SparsePauliOp

from worker.adapters import base as adapter_base
from worker.adapters.aer_adapter import AerAdapter
from worker.adapters.aer_noise import AerNoiseConfiguration
from worker.adapters.base import BackendAdapter, BackendExecutionContext
from worker.adapters.ibm_adapter import IBMAdapter, _RuntimeTranspiler
from worker.adapters.result_adapter import normalize_result
from worker.adapters.statevector_adapter import StatevectorAdapter
from worker.chemistry.problem_manifest import build_problem_manifest
from worker.chemistry.types import (
    KQDResult,
    PreparedMolecule,
    QFDResult,
    QSEResult,
    SKQDResult,
    SQDResult,
    VQEResult,
)
from worker.exceptions import BackendError, IBMTimeoutError

_PrimitiveOptions = dict[str, dict[str, object]]
SAMPLER_V2_PATCH_PATH = "qiskit_aer.primitives.SamplerV2"


def test_statevector_adapter_capabilities_and_primitives() -> None:
    adapter = StatevectorAdapter()

    assert isinstance(adapter, BackendAdapter)
    assert adapter.capabilities.backend_target == "statevector"
    assert adapter.capabilities.enabled is True
    assert adapter.capabilities.supports_noise_profile is False
    estimator = adapter.create_estimator()
    sampler = adapter.create_sampler()
    assert estimator.__class__.__name__ == "StatevectorEstimator"
    assert sampler.__class__.__name__ == "StatevectorSampler"


def test_aer_adapter_capabilities_and_primitives() -> None:
    adapter = AerAdapter()
    context = BackendExecutionContext(
        backend_target="aer_simulator",
        backend_options={"method": "automatic", "shots": 256},
        noise_profile={
            "source": "custom_preset",
            "preset": "depolarizing_cx",
            "strength": 0.01,
        },
        shots=256,
        simulator_method="automatic",
    )

    estimator = adapter.create_estimator(context)
    sampler = adapter.create_sampler(context)
    metadata = adapter.execution_metadata(context)

    assert adapter.capabilities.backend_target == "aer_simulator"
    assert adapter.capabilities.enabled is True
    assert adapter.capabilities.supports_noise_profile is True
    assert estimator.__class__.__name__ == "TrackingPrimitive"
    assert sampler.__class__.__name__ == "TrackingPrimitive"
    assert metadata["primitive_family"] == "qiskit_aer"
    assert metadata["shots"] == 256
    assert metadata["noise_summary"]["enabled"] is True
    assert metadata["noise_summary"]["preset"] == "depolarizing_cx"


@pytest.mark.parametrize(
    "noise_profile",
    [
        None,
        {"source": "custom_preset", "preset": "depolarizing_cx", "strength": 0.01},
    ],
)
def test_aer_estimator_transpiles_number_preserving_gate(noise_profile) -> None:
    circuit = QuantumCircuit(2)
    circuit.append(XXPlusYYGate(Parameter("theta"), 0.0), [0, 1])
    observable = SparsePauliOp.from_list([("ZI", 1.0)])
    context = BackendExecutionContext(
        backend_target="aer_simulator",
        noise_profile=noise_profile,
        shots=128,
        simulator_method="automatic",
    )

    result = AerAdapter().create_estimator(context).run(
        [(circuit, [observable], [[0.1]])]
    ).result()

    assert result[0].data.evs.size == 1


def test_aer_estimator_reuses_transpiled_parameterized_circuit(monkeypatch) -> None:
    calls = 0

    def fake_transpile(circuit, *, context, noise_model=None):
        nonlocal calls
        calls += 1
        return circuit

    monkeypatch.setattr("worker.adapters.aer_adapter.transpile_aer_circuit", fake_transpile)
    circuit = QuantumCircuit(1)
    circuit.rx(Parameter("theta"), 0)
    observable = SparsePauliOp.from_list([("Z", 1.0)])
    context = BackendExecutionContext(
        backend_target="aer_simulator",
        backend_options={"method": "automatic"},
        shots=32,
        simulator_method="automatic",
    )
    adapter = AerAdapter()
    transform = adapter._build_estimator_run_transform(context, None)

    transform(([(circuit, observable)],), {})
    transform(([(circuit, observable)],), {})

    assert calls == 1
    assert adapter._transpilation_cache_metadata() == {
        "enabled": True,
        "entries": 1,
        "hits": 1,
        "misses": 1,
        "max_entries": 256,
    }


def test_aer_adapter_strips_ibm_profile_fields_from_primitive_options(monkeypatch) -> None:
    estimator_options: list[dict[str, object]] = []
    sampler_calls: list[dict[str, object]] = []

    class FakeEstimatorV2:
        def __init__(self, *, options):
            estimator_options.append(options)

    class FakeSamplerV2:
        def __init__(self, *, default_shots, seed, options):
            sampler_calls.append(
                {
                    "default_shots": default_shots,
                    "seed": seed,
                    "options": options,
                }
            )

    monkeypatch.setattr("qiskit_aer.primitives.EstimatorV2", FakeEstimatorV2)
    monkeypatch.setattr(SAMPLER_V2_PATCH_PATH, FakeSamplerV2)

    adapter = AerAdapter()
    context = BackendExecutionContext(
        backend_target="aer_simulator",
        backend_options={
            "method": "automatic",
            "shots": 256,
            "aer_pub_chunk_size": 3,
            "seed_simulator": 7,
            "credential_profile_id": "profile-123",
            "token": "fake-token",
            "instance": "fake-instance",
            "channel": "ibm_quantum_platform",
            "url": "https://example.invalid",
        },
        shots=256,
        simulator_method="automatic",
    )

    adapter.create_estimator(context)
    adapter.create_sampler(context)

    assert estimator_options == [
        {
            "backend_options": {"method": "automatic"},
            "default_precision": 0.0,
            "run_options": {"shots": 256, "seed_simulator": 7},
        }
    ]
    assert sampler_calls == [
        {
            "default_shots": 256,
                "seed": 7,
                "options": {
                    "backend_options": {"method": "automatic"},
                    "run_options": {"shots": 256, "seed_simulator": 7},
                },
        }
    ]


def test_aer_estimator_records_and_applies_precision_without_sampler_option_leak(
    monkeypatch,
) -> None:
    estimator_options: list[dict[str, object]] = []
    sampler_options: list[dict[str, object]] = []

    class FakeEstimatorV2:
        def __init__(self, *, options):
            estimator_options.append(options)

    class FakeSamplerV2:
        def __init__(self, *, default_shots, seed, options):
            del default_shots, seed
            sampler_options.append(options)

    monkeypatch.setattr("qiskit_aer.primitives.EstimatorV2", FakeEstimatorV2)
    monkeypatch.setattr(SAMPLER_V2_PATCH_PATH, FakeSamplerV2)

    adapter = AerAdapter()
    context = BackendExecutionContext(
        backend_target="aer_simulator",
        backend_options={"method": "automatic"},
        shots=512,
        requested_shots=1024,
        estimator_precision=0.125,
        requested_estimator_precision=0.25,
        simulator_method="automatic",
    )

    adapter.create_estimator(context)
    adapter.create_sampler(context)
    metadata = adapter.execution_metadata(context)

    assert estimator_options == [
        {
            "backend_options": {"method": "automatic"},
            "default_precision": 0.125,
            "run_options": {"shots": 512},
        }
    ]
    assert sampler_options == [
        {
            "backend_options": {"method": "automatic"},
            "run_options": {"shots": 512},
        }
    ]
    assert metadata["requested_shots"] == 1024
    assert metadata["effective_shots"] == 512
    assert metadata["requested_estimator_precision"] == 0.25
    assert metadata["effective_estimator_precision"] == 0.125
    assert metadata["measurement_mode"] == "precision_sampled"
    assert metadata["uncertainty_policy"] == "aer_estimator_default_precision"


def test_aer_exact_estimator_metadata_does_not_claim_configured_shots() -> None:
    adapter = AerAdapter()
    context = BackendExecutionContext(
        backend_target="aer_simulator",
        shots=256,
        estimator_precision=0.0,
    )

    adapter.create_estimator(context)
    metadata = adapter.execution_metadata(context)

    assert metadata["measurement_mode"] == "exact"
    assert metadata["requested_shots"] == 256
    assert metadata["shots"] is None
    assert metadata["effective_shots"] is None


@pytest.mark.parametrize(
    ("precision", "expected_std"),
    [(0.0, 0.0), (0.125, 0.125)],
)
def test_aer_estimator_returns_declared_standard_error(precision: float, expected_std: float) -> None:
    circuit = QuantumCircuit(1)
    observable = SparsePauliOp.from_list([("Z", 1.0)])
    context = BackendExecutionContext(
        backend_target="aer_simulator",
        backend_options={"method": "automatic", "seed_simulator": 7},
        shots=256,
        estimator_precision=precision,
    )

    result = AerAdapter().create_estimator(context).run([(circuit, observable)]).result()[0]

    assert float(result.data.stds) == expected_std


def test_aer_adapter_reuses_cached_noise_details_across_metadata_and_primitive_builds(
    monkeypatch,
) -> None:
    build_noise_calls: list[tuple[dict[str, object] | None, dict[str, object]]] = []
    estimator_options: list[_PrimitiveOptions] = []
    sampler_options: list[_PrimitiveOptions] = []
    noise_model = object()

    class FakeEstimatorV2:
        def __init__(self, *, options: _PrimitiveOptions):
            estimator_options.append(options)

    class FakeSamplerV2:
        def __init__(self, *, default_shots, seed, options: _PrimitiveOptions):
            del default_shots, seed
            sampler_options.append(options)

    def fake_resolve_noise_profile(noise_profile, backend_options):
        build_noise_calls.append((noise_profile, backend_options))
        return AerNoiseConfiguration(
            noise_model=noise_model,
            summary={"enabled": True, "source": "custom_preset"},
        )

    monkeypatch.setattr("qiskit_aer.primitives.EstimatorV2", FakeEstimatorV2)
    monkeypatch.setattr(SAMPLER_V2_PATCH_PATH, FakeSamplerV2)
    monkeypatch.setattr(
        "worker.adapters.aer_adapter.resolve_aer_noise_profile",
        fake_resolve_noise_profile,
    )

    adapter = AerAdapter()
    context = BackendExecutionContext(
        backend_target="aer_simulator",
        backend_options={"method": "automatic", "shots": 512, "seed_simulator": 11},
        noise_profile={
            "source": "custom_preset",
            "preset": "depolarizing_cx",
            "strength": 0.02,
        },
        shots=512,
        simulator_method="automatic",
    )

    first_metadata = adapter.execution_metadata(context)
    second_metadata = adapter.execution_metadata(context)
    adapter.create_estimator(context)
    adapter.create_sampler(context)

    assert build_noise_calls == [
        (
            {
                "source": "custom_preset",
                "preset": "depolarizing_cx",
                "strength": 0.02,
            },
            {"method": "automatic", "shots": 512, "seed_simulator": 11},
        )
    ]
    assert first_metadata["noise_summary"] == {"enabled": True, "source": "custom_preset"}
    assert second_metadata["noise_summary"] == {"enabled": True, "source": "custom_preset"}
    assert estimator_options[0]["backend_options"]["noise_model"] is noise_model
    assert sampler_options[0]["backend_options"]["noise_model"] is noise_model
    assert estimator_options[0]["backend_options"]["method"] == "automatic"
    assert sampler_options[0]["backend_options"]["method"] == "automatic"


def test_ibm_adapter_raises_without_credentials(monkeypatch) -> None:
    monkeypatch.setenv("QISKIT_IBM_TOKEN", "ignored-token")
    monkeypatch.setenv("IBM_QUANTUM_TOKEN", "ignored-token")
    monkeypatch.setenv("QISKIT_IBM_INSTANCE", "ignored-instance")
    monkeypatch.setenv("IBM_QUANTUM_INSTANCE", "ignored-instance")

    with pytest.raises(BackendError):
        IBMAdapter().create_estimator()


def test_ibm_adapter_backend_resolution_hides_provider_error_details() -> None:
    def fail_backend(_name: str) -> object:
        raise RuntimeError("provider token must stay out of worker diagnostics")

    service = SimpleNamespace(backend=fail_backend)
    adapter = IBMAdapter(service_factory=lambda **_: service)
    context = BackendExecutionContext(
        backend_target="ibm_runtime",
        backend_options={
            "backend_name": "ibm_brisbane",
            "token": "fake-token",
            "instance": "fake-instance",
        },
    )

    with pytest.raises(BackendError) as raised:
        adapter._resolve_backend(context)

    assert str(raised.value) == "Unable to resolve IBM Runtime backend (RuntimeError)"
    assert "provider token" not in str(raised.value)
    assert raised.value.__cause__ is None


def test_ibm_adapter_rejects_named_simulator_backend() -> None:
    backend = SimpleNamespace(name="ibm_cloud_simulator", simulator=True)
    service = SimpleNamespace(backend=lambda _name: backend)
    adapter = IBMAdapter(service_factory=lambda **_: service)
    context = BackendExecutionContext(
        backend_target="ibm_runtime",
        backend_options={
            "backend_name": "ibm_cloud_simulator",
            "token": "fake-token",
            "instance": "fake-instance",
        },
    )

    with pytest.raises(BackendError, match="resolved to a simulator"):
        adapter._resolve_backend(context)


def test_ibm_adapter_rejects_configuration_simulator_backend() -> None:
    backend = SimpleNamespace(
        name="ibm_cloud_simulator",
        configuration=lambda: SimpleNamespace(simulator=True),
    )
    service = SimpleNamespace(backend=lambda _name: backend)
    adapter = IBMAdapter(service_factory=lambda **_: service)
    context = BackendExecutionContext(
        backend_target="ibm_runtime",
        backend_options={
            "backend_name": "ibm_cloud_simulator",
            "token": "fake-token",
            "instance": "fake-instance",
        },
    )

    with pytest.raises(BackendError, match="resolved to a simulator"):
        adapter._resolve_backend(context)


def test_ibm_adapter_rejects_backend_without_explicit_simulator_metadata() -> None:
    backend = SimpleNamespace(name="ibm_unknown_backend_shape")
    service = SimpleNamespace(backend=lambda _name: backend)
    adapter = IBMAdapter(service_factory=lambda **_: service)
    context = BackendExecutionContext(
        backend_target="ibm_runtime",
        backend_options={
            "backend_name": "ibm_unknown_backend_shape",
            "token": "fake-token",
            "instance": "fake-instance",
        },
    )

    with pytest.raises(BackendError, match="explicit non-simulator metadata"):
        adapter._resolve_backend(context)


def test_ibm_adapter_service_initialization_hides_provider_error_details() -> None:
    def fail_service(**_options: object) -> object:
        raise RuntimeError("provider token must stay out of worker diagnostics")

    adapter = IBMAdapter(service_factory=fail_service)
    context = BackendExecutionContext(
        backend_target="ibm_runtime",
        backend_options={"token": "fake-token", "instance": "fake-instance"},
    )

    with pytest.raises(BackendError) as raised:
        adapter._resolve_service(context)

    assert str(raised.value) == "Unable to initialize IBM Runtime service (RuntimeError)"
    assert "provider token" not in str(raised.value)
    assert raised.value.__cause__ is None


def test_ibm_adapter_transpilation_hides_provider_error_details(monkeypatch) -> None:
    circuit = SimpleNamespace(num_qubits=2, data=[])
    transpiler = _RuntimeTranspiler(
        backend=SimpleNamespace(),
        context=BackendExecutionContext(backend_target="ibm_runtime"),
    )
    pass_manager = SimpleNamespace(
        run=lambda _circuit: (_ for _ in ()).throw(
            RuntimeError("provider token must stay out of worker diagnostics")
        )
    )
    monkeypatch.setattr(transpiler, "_pass_manager_for_context", lambda: pass_manager)

    with pytest.raises(BackendError) as raised:
        transpiler.transpile_circuit(circuit)

    assert str(raised.value) == "IBM Runtime transpilation failed (RuntimeError)"
    assert "provider token" not in str(raised.value)
    assert raised.value.__cause__ is None


def test_ibm_adapter_uses_runtime_primitives_and_tracks_job_ids() -> None:
    backend = SimpleNamespace(name="ibm_brisbane", simulator=False)
    service = SimpleNamespace(backend=lambda name: backend)
    job = SimpleNamespace(job_id=lambda: "runtime-job-123")
    primitive = SimpleNamespace(run=lambda *args, **kwargs: job)
    estimator_calls = []
    observed_jobs = []

    def estimator_factory(**kwargs):
        estimator_calls.append(kwargs)
        return primitive

    def observe_job(job, metadata):
        observed_jobs.append((job, metadata))
        return None

    adapter = IBMAdapter(
        service_factory=lambda **_: service,
        estimator_factory=estimator_factory,
    )
    context = BackendExecutionContext(
        backend_target="ibm_runtime",
        backend_options={
            "backend_name": "ibm_brisbane",
            "token": "fake-token",
            "instance": "fake-instance",
        },
        shots=512,
        optimization_level=1,
        primitive_job_observer=observe_job,
    )

    estimator = adapter.create_estimator(context)
    estimator.run([(object(), object())])
    metadata = adapter.execution_metadata(context)

    assert estimator_calls[0]["mode"] is backend
    assert estimator_calls[0]["options"]["default_shots"] == 512
    assert "default_precision" not in estimator_calls[0]["options"]
    assert metadata["effective_estimator_precision"] == pytest.approx(1 / math.sqrt(512))
    assert metadata["measurement_mode"] == "precision_sampled"
    assert metadata["uncertainty_policy"] == "ibm_runtime_shot_precision"
    assert metadata["resolved_backend_name"] == "ibm_brisbane"
    assert metadata["job_ids"] == ["runtime-job-123"]
    assert metadata["ibm_job_id"] == "runtime-job-123"
    assert observed_jobs == [
        (
            job,
            {
                "job_id": "runtime-job-123",
                "pub_count": 1,
                "backend": "ibm_brisbane",
                "backend_target": "ibm_runtime",
                "selection_policy": "requested",
            },
        )
    ]


def test_ibm_adapter_runtime_contract_caps_and_failure_payloads() -> None:
    backend = SimpleNamespace(name="ibm_brisbane", simulator=False)
    service = SimpleNamespace(backend=lambda _name: backend)
    run_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    outcomes = [SimpleNamespace(job_id=lambda: "runtime-job-123"), RuntimeError("secret")]

    def primitive_run(*args: object, **kwargs: object) -> object:
        run_calls.append((args, kwargs))
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    adapter = IBMAdapter(
        service_factory=lambda **_: service,
        estimator_factory=lambda **_: SimpleNamespace(run=primitive_run),
    )
    context = BackendExecutionContext(
        backend_target="ibm_runtime",
        backend_options={
            "backend_name": "ibm_brisbane",
            "token": "fake-token",
            "instance": "fake-instance",
        },
        shots=512,
    )

    estimator = adapter.create_estimator(context)
    estimator.run([(object(), object())])
    with pytest.raises(RuntimeError, match="secret"):
        estimator.run([(object(), object())])
    with pytest.raises(BackendError, match="PUB cap"):
        estimator.run([(object(), object())] * 129)

    metadata = adapter.execution_metadata(context)
    assert metadata["job_ids"] == ["runtime-job-123"]
    assert metadata["ibm_job_id"] == "runtime-job-123"
    assert metadata["runtime_failure_payloads"] == [
        {"stage": "submission", "error_type": "RuntimeError", "pub_count": 1, "shots": 512},
        {"stage": "submission", "error_type": "BackendError", "pub_count": 129, "shots": 512},
    ]
    assert len(run_calls) == 2


def test_ibm_adapter_runtime_contract_rejects_shot_job_and_option_violations() -> None:
    backend = SimpleNamespace(name="ibm_brisbane", simulator=False)
    service = SimpleNamespace(backend=lambda _name: backend)
    guarded_adapter = IBMAdapter(
        service_factory=lambda **_: (_ for _ in ()).throw(AssertionError("service used")),
        estimator_factory=lambda **_: (_ for _ in ()).throw(AssertionError("primitive used")),
    )
    base_options = {
        "backend_name": "ibm_brisbane",
        "token": "fake-token",
        "instance": "fake-instance",
    }

    with pytest.raises(BackendError, match="shots exceed"):
        guarded_adapter.create_estimator(
            BackendExecutionContext(
                backend_target="ibm_runtime",
                backend_options=base_options,
                shots=100_001,
            )
        )
    with pytest.raises(BackendError, match="local noise_profile"):
        guarded_adapter.create_estimator(
            BackendExecutionContext(
                backend_target="ibm_runtime",
                backend_options=base_options,
                noise_profile={"source": "custom_preset"},
            )
        )
    # Estimator precision is primitive-specific. SamplerV2 ignores it and
    # receives the bounded shot count through its own runtime options.
    sampler_adapter = IBMAdapter(
        service_factory=lambda **_: service,
        sampler_factory=lambda **_: object(),
    )
    sampler_adapter.create_sampler(
        BackendExecutionContext(
            backend_target="ibm_runtime",
            backend_options=base_options,
            estimator_precision=0.1,
        )
    )

    adapter = IBMAdapter(
        service_factory=lambda **_: service,
        estimator_factory=lambda **_: SimpleNamespace(run=lambda *_args, **_kwargs: object()),
    )
    context = BackendExecutionContext(backend_target="ibm_runtime", backend_options=base_options)
    estimator = adapter.create_estimator(context)
    adapter._runtime_submitted_job_count = 128
    with pytest.raises(BackendError, match="job cap"):
        estimator.run([(object(), object())])


def test_ibm_adapter_uses_estimator_precision_only_for_estimator() -> None:
    backend = SimpleNamespace(name="ibm_brisbane", simulator=False)
    service = SimpleNamespace(backend=lambda _name: backend)
    estimator_calls: list[dict[str, object]] = []
    sampler_calls: list[dict[str, object]] = []

    class FakeEstimatorV2:
        def __init__(self, **kwargs: object) -> None:
            estimator_calls.append(kwargs)

    class FakeSamplerV2:
        def __init__(self, **kwargs: object) -> None:
            sampler_calls.append(kwargs)

    adapter = IBMAdapter(
        service_factory=lambda **_: service,
        estimator_factory=FakeEstimatorV2,
        sampler_factory=FakeSamplerV2,
    )
    context = BackendExecutionContext(
        backend_target="ibm_runtime",
        backend_options={
            "backend_name": "ibm_brisbane",
            "token": "fake-token",
            "instance": "fake-instance",
        },
        shots=512,
        estimator_precision=0.125,
    )

    adapter.create_estimator(context)
    adapter.create_sampler(context)

    assert estimator_calls == [
        {"mode": backend, "options": {"default_precision": 0.125}}
    ]
    assert sampler_calls == [{"mode": backend, "options": {"default_shots": 512}}]


def test_ibm_adapter_records_named_backend_mismatch_as_fallback() -> None:
    backend = SimpleNamespace(name="ibm_fez", simulator=False)
    service = SimpleNamespace(backend=lambda _name: backend)
    adapter = IBMAdapter(service_factory=lambda **_: service)
    context = BackendExecutionContext(
        backend_target="ibm_runtime",
        backend_options={
            "backend_name": "ibm_brisbane",
            "token": "fake-token",
            "instance": "fake-instance",
        },
    )

    adapter._resolve_backend(context)
    metadata = adapter.execution_metadata(context)

    assert metadata["requested_backend_name"] == "ibm_brisbane"
    assert metadata["resolved_backend_name"] == "ibm_fez"
    assert metadata["fallback_reason"] == (
        "requested_backend_name_differed_from_resolved_backend"
    )


def test_aer_adapter_metadata_prefers_observed_sampler_shots() -> None:
    job = SimpleNamespace(job_id=lambda: "aer-job-1")

    class FakeSamplerV2:
        def __init__(self, *, default_shots, seed, options):
            self.default_shots = default_shots
            self.seed = seed
            self.options = options

        def run(self, *args, **kwargs):
            del args, kwargs
            return job

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(SAMPLER_V2_PATCH_PATH, FakeSamplerV2)
    try:
        adapter = AerAdapter()
        context = BackendExecutionContext(
            backend_target="aer_simulator",
            backend_options={"method": "automatic", "shots": 256},
            shots=256,
            simulator_method="automatic",
        )

        sampler = adapter.create_sampler(context)
        sampler.run([(object(),)], shots=1536)
        metadata = adapter.execution_metadata(context)

        assert metadata["shots"] == 1536
        assert metadata["pub_count"] == 1
    finally:
        monkeypatch.undo()


def test_ibm_adapter_run_guard_blocks_remote_submission() -> None:
    backend = SimpleNamespace(name="ibm_brisbane", simulator=False)
    service = SimpleNamespace(backend=lambda name: backend)
    run_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    job = SimpleNamespace(job_id=lambda: "runtime-job-123")

    def primitive_run(*args, **kwargs):
        run_calls.append((args, kwargs))
        return job

    def raise_run_cancelled() -> None:
        raise RuntimeError("run cancelled")

    primitive = SimpleNamespace(run=primitive_run)

    adapter = IBMAdapter(
        service_factory=lambda **_: service,
        estimator_factory=lambda **kwargs: primitive,
    )
    context = BackendExecutionContext(
        backend_target="ibm_runtime",
        backend_options={
            "backend_name": "ibm_brisbane",
            "token": "fake-token",
            "instance": "fake-instance",
        },
        primitive_run_guard=raise_run_cancelled,
    )

    estimator = adapter.create_estimator(context)

    with pytest.raises(RuntimeError, match="run cancelled"):
        estimator.run([(object(), object())])

    assert run_calls == []


def test_ibm_adapter_times_out_stalled_runtime_submission(monkeypatch) -> None:
    backend = SimpleNamespace(name="ibm_brisbane", simulator=False)
    service = SimpleNamespace(backend=lambda name: backend)
    primitive = SimpleNamespace(run=lambda *args, **kwargs: object())

    captured_timeout: dict[str, float] = {}

    def fake_call_with_submission_timeout(callback, *, timeout_seconds, error_factory=None):
        del callback
        captured_timeout["seconds"] = float(timeout_seconds)
        raise (error_factory or TimeoutError)(float(timeout_seconds))

    monkeypatch.setattr(
        adapter_base,
        "_call_with_submission_timeout",
        fake_call_with_submission_timeout,
    )

    adapter = IBMAdapter(
        service_factory=lambda **_: service,
        estimator_factory=lambda **kwargs: primitive,
    )
    context = BackendExecutionContext(
        backend_target="ibm_runtime",
        backend_options={
            "backend_name": "ibm_brisbane",
            "token": "fake-token",
            "instance": "fake-instance",
        },
    )

    estimator = adapter.create_estimator(context)

    with pytest.raises(
        IBMTimeoutError,
        match="IBM Runtime EstimatorV2 submission to ibm_brisbane did not return within",
    ):
        estimator.run([(object(), object())])

    assert captured_timeout["seconds"] > 0.0


def test_ibm_adapter_execution_metadata_resolves_backend_name_before_primitive_creation() -> None:
    backend = SimpleNamespace(name="ibm_brisbane", simulator=False)
    service = SimpleNamespace(
        backend=lambda name: backend,
        least_busy=lambda **kwargs: backend,
    )

    adapter = IBMAdapter(service_factory=lambda **_: service)
    context = BackendExecutionContext(
        backend_target="ibm_runtime",
        backend_options={
            "selection_policy": "least_busy",
            "token": "fake-token",
            "instance": "fake-instance",
        },
        shots=512,
        optimization_level=1,
    )

    metadata = adapter.execution_metadata(context)

    assert metadata["resolved_backend_name"] == "ibm_brisbane"


def test_ibm_precision_estimator_metadata_does_not_claim_configured_shots() -> None:
    backend = SimpleNamespace(name="ibm_brisbane", simulator=False)
    service = SimpleNamespace(backend=lambda name: backend)
    adapter = IBMAdapter(
        service_factory=lambda **_: service,
        estimator_factory=lambda **_: SimpleNamespace(run=lambda *args, **kwargs: object()),
    )
    context = BackendExecutionContext(
        backend_target="ibm_runtime",
        backend_options={
            "backend_name": "ibm_brisbane",
            "token": "fake-token",
            "instance": "fake-instance",
        },
        shots=512,
        estimator_precision=0.25,
    )

    adapter.create_estimator(context)
    metadata = adapter.execution_metadata(context)

    assert metadata["measurement_mode"] == "precision_sampled"
    assert metadata["requested_shots"] == 512
    assert metadata["effective_estimator_precision"] == 0.25
    assert metadata["shots"] is None
    assert metadata["effective_shots"] is None


def test_ibm_adapter_uses_least_error_selection_policy_for_resolution() -> None:
    quiet_backend = SimpleNamespace(
        name="ibm_miami",
        simulator=False,
        properties=lambda: SimpleNamespace(gate_error=lambda: 0.001),
        status=lambda: SimpleNamespace(pending_jobs=12),
    )
    noisy_backend = SimpleNamespace(
        name="ibm_pittsburgh",
        simulator=False,
        properties=lambda: SimpleNamespace(gate_error=lambda: 0.02),
        status=lambda: SimpleNamespace(pending_jobs=1),
    )
    service = SimpleNamespace(
        backends=lambda **kwargs: [noisy_backend, quiet_backend],
        least_busy=lambda **kwargs: noisy_backend,
    )
    estimator_calls: list[dict[str, object]] = []

    adapter = IBMAdapter(
        service_factory=lambda **_: service,
        estimator_factory=lambda **kwargs: estimator_calls.append(kwargs) or SimpleNamespace(),
    )
    context = BackendExecutionContext(
        backend_target="ibm_runtime",
        backend_options={
            "token": "fake-token",
            "instance": "fake-instance",
        },
        selection_policy="least_error",
        shots=512,
        optimization_level=1,
    )

    adapter.create_estimator(context)
    metadata = adapter.execution_metadata(context)

    assert estimator_calls[0]["mode"] is quiet_backend
    assert metadata["resolved_backend_name"] == "ibm_miami"


def test_ibm_adapter_captures_transpilation_layout_summary(monkeypatch) -> None:
    backend = SimpleNamespace(name="ibm_brisbane", simulator=False)
    service = SimpleNamespace(backend=lambda name: backend)
    job = SimpleNamespace(job_id=lambda: "runtime-job-123")
    primitive = SimpleNamespace(run=lambda *args, **kwargs: job)

    monkeypatch.setattr(
        "worker.adapters.ibm_adapter._transpile_circuit_summary",
        lambda circuit, **kwargs: {
            "logical_to_physical": [
                {"logical": 0, "physical": 112},
                {"logical": 1, "physical": 113},
            ],
            "used_physical_qubits": [112, 113],
            "final_layout": [112, 113],
            "transpiled_depth": 42,
        },
    )

    adapter = IBMAdapter(
        service_factory=lambda **_: service,
        estimator_factory=lambda **kwargs: primitive,
    )
    context = BackendExecutionContext(
        backend_target="ibm_runtime",
        backend_options={
            "backend_name": "ibm_brisbane",
            "token": "fake-token",
            "instance": "fake-instance",
        },
        shots=512,
        optimization_level=1,
    )

    estimator = adapter.create_estimator(context)
    estimator.run([("circuit", object())])
    metadata = adapter.execution_metadata(context)

    assert metadata["transpilation_summary"]["logical_to_physical"] == [
        {"logical": 0, "physical": 112},
        {"logical": 1, "physical": 113},
    ]
    assert metadata["transpilation_summary"]["used_physical_qubits"] == [112, 113]
    assert metadata["transpilation_summary"]["transpiled_depth"] == 42


def test_ibm_adapter_metadata_prefers_observed_sampler_shots() -> None:
    backend = SimpleNamespace(name="ibm_brisbane", simulator=False)
    service = SimpleNamespace(backend=lambda name: backend)
    job = SimpleNamespace(job_id=lambda: "runtime-job-123")
    primitive = SimpleNamespace(run=lambda *args, **kwargs: job)

    adapter = IBMAdapter(
        service_factory=lambda **_: service,
        sampler_factory=lambda **kwargs: primitive,
    )
    context = BackendExecutionContext(
        backend_target="ibm_runtime",
        backend_options={
            "backend_name": "ibm_brisbane",
            "token": "fake-token",
            "instance": "fake-instance",
        },
        shots=512,
        optimization_level=1,
    )

    sampler = adapter.create_sampler(context)
    sampler.run([(object(),)], shots=24576)
    metadata = adapter.execution_metadata(context)

    assert metadata["shots"] == 24576
    assert metadata["pub_count"] == 1


def test_normalize_result_for_vqe_dataclass() -> None:
    result = VQEResult(
        algorithm="vqe",
        primary_energy=-1.13,
        primary_iterations=3,
        converged=True,
        optimal_parameters=[0.1, 0.2],
        convergence_trace=[-1.13, -1.12, -1.11],
        optimizer_diagnostics={
            "final_energy": -1.11,
            "best_observed_energy": -1.13,
            "reported_energy_source": "best_observed_optimizer_evaluation",
            "final_parameters": [0.3, 0.4],
            "best_observed_parameters": [0.1, 0.2],
        },
    )

    normalized = normalize_result(result)

    assert normalized["algorithm"] == "vqe"
    assert normalized["energy"] == -1.13
    assert normalized["iterations"] == 3
    assert normalized["optimal_parameters"] == [0.1, 0.2]
    assert normalized["algorithm_metrics"]["convergence_trace"] == [-1.13, -1.12, -1.11]
    assert (
        normalized["energy_policy"]["primary_energy_source"] == "best_observed_optimizer_evaluation"
    )
    assert normalized["final_energy"] == pytest.approx(-1.11)
    assert normalized["best_observed_energy"] == pytest.approx(-1.13)
    assert normalized["reported_energy_source"] == "best_observed_optimizer_evaluation"
    convergence = normalized["algorithm_metrics"]["convergence"]
    assert convergence["optimizer_converged"] is True
    assert convergence["scientific_converged"] is None
    assert convergence["convergence_failure_reason"] == "energy_delta_threshold_unavailable"


def test_normalize_result_detects_scipy_function_evaluation_cap() -> None:
    normalized = normalize_result(
        VQEResult(
            algorithm="vqe",
            primary_energy=-1.0,
            primary_iterations=32,
            converged=False,
            optimal_parameters=[],
            convergence_trace=[-0.9, -1.0],
            optimizer_diagnostics={
                "effective_max_iterations": 30,
                "objective_evaluations": 32,
                "message": "Return from COBYLA because the objective was evaluated MAXFUN times.",
                "termination_reason": "optimizer_failure",
                "final_delta_energy": 0.1,
                "convergence_threshold": 1e-5,
            },
        )
    )

    convergence = normalized["algorithm_metrics"]["convergence"]
    assert convergence["budget_exhausted"] is True
    assert convergence["scientific_converged"] is False
    assert convergence["convergence_failure_reason"] == "budget_exhausted"


def test_normalize_result_preserves_zero_primary_energy() -> None:
    result = VQEResult(
        algorithm="vqe",
        primary_energy=0.0,
        primary_iterations=1,
        converged=True,
        optimal_parameters=[],
        convergence_trace=[1.0],
        optimizer_diagnostics={"final_energy": 1.0, "best_observed_energy": 1.0},
    )

    normalized = normalize_result(result)

    assert normalized["energy"] == 0.0
    assert normalized["reported_energy"] == 0.0


def test_normalize_result_for_kqd_dataclass() -> None:
    result = KQDResult(
        algorithm="kqd",
        primary_energy=-0.92,
        primary_iterations=4,
        converged=True,
        ritz_values=[-1.0, -0.97, -0.94, -0.92],
        krylov_rank=4,
        orthogonality_metrics={"basis_rank": 4.0, "overlap_condition": 1.0},
    )

    normalized = normalize_result(result)

    assert normalized["algorithm"] == "kqd"
    assert normalized["iterations"] == 4
    assert normalized["optimal_parameters"] == []
    assert normalized["algorithm_metrics"]["krylov_rank"] == 4
    assert normalized["algorithm_metrics"]["ritz_values"] == [-1.0, -0.97, -0.94, -0.92]
    assert normalized["algorithm_metrics"]["raw_ritz_values"] == []


def test_normalize_result_for_qfd_dataclass() -> None:
    result = QFDResult(
        algorithm="qfd",
        primary_energy=-0.88,
        primary_iterations=5,
        converged=True,
        filter_eigenvalues=[-0.95, -0.91, -0.9, -0.89, -0.88],
        conditioning_summary={"time_points": 5.0, "condition_number": 1.5},
    )

    normalized = normalize_result(result)

    assert normalized["algorithm"] == "qfd"
    assert normalized["iterations"] == 5
    assert normalized["optimal_parameters"] == []
    assert normalized["algorithm_metrics"]["filter_eigenvalues"] == [
        -0.95,
        -0.91,
        -0.9,
        -0.89,
        -0.88,
    ]
    assert normalized["algorithm_metrics"]["raw_filter_eigenvalues"] == []


def test_normalize_result_rejects_stabilized_branch_projected_spectra() -> None:
    kqd = normalize_result(
        KQDResult(
            algorithm="kqd",
            primary_energy=-1.11,
            primary_iterations=3,
            converged=True,
            ritz_values=[-1.11, -1.0],
            krylov_rank=3,
            orthogonality_metrics={},
            matrix_element_summary={"matrix_element_strategy": "branch_estimator"},
            raw_ritz_values=[-100.0, -1.11, -1.0],
            stability_summary={"stability_state": "stabilized", "dropped_rank": 1},
        )
    )
    qfd = normalize_result(
        QFDResult(
            algorithm="qfd",
            primary_energy=-1.07,
            primary_iterations=4,
            converged=True,
            filter_eigenvalues=[-1.07, -0.95],
            conditioning_summary={},
            matrix_element_summary={"matrix_element_strategy": "branch_estimator"},
            raw_filter_eigenvalues=[-999.0, -1.07, -0.95],
            stability_summary={"stability_state": "stabilized", "dropped_rank": 1},
        )
    )

    assert kqd["reported_energy"] is None
    assert kqd["reported_energy_source"] == "unavailable_unstable_projected_solve"
    assert kqd["energy_policy"]["primary_energy_source"] == (
        "unavailable_unstable_projected_solve"
    )
    assert kqd["algorithm_metrics"]["raw_ritz_values"][0] == pytest.approx(-100.0)
    assert kqd["algorithm_metrics"]["stability_summary"]["stability_state"] == "stabilized"
    assert qfd["reported_energy"] is None
    assert qfd["reported_energy_source"] == "unavailable_unstable_projected_solve"
    assert qfd["energy_policy"]["primary_energy_source"] == (
        "unavailable_unstable_projected_solve"
    )
    assert qfd["algorithm_metrics"]["raw_filter_eigenvalues"][0] == pytest.approx(-999.0)


def test_normalize_result_reports_stabilized_branch_energy_as_diagnostic() -> None:
    diagnostic_summary = {
        "stability_state": "stabilized",
        "dropped_rank": 1,
        "retained_rank": 3,
        "relative_projected_ritz_residual": 1e-3,
    }
    kqd = normalize_result(
        KQDResult(
            algorithm="kqd",
            primary_energy=-1.11,
            primary_iterations=3,
            converged=False,
            ritz_values=[-1.11, -1.0],
            krylov_rank=3,
            orthogonality_metrics={},
            matrix_element_summary={"matrix_element_strategy": "branch_estimator"},
            raw_ritz_values=[-100.0, -1.11, -1.0],
            stability_summary=diagnostic_summary,
        )
    )
    qfd = normalize_result(
        QFDResult(
            algorithm="qfd",
            primary_energy=-1.07,
            primary_iterations=4,
            converged=False,
            filter_eigenvalues=[-1.07, -0.95],
            conditioning_summary={},
            matrix_element_summary={"matrix_element_strategy": "branch_estimator"},
            raw_filter_eigenvalues=[-999.0, -1.07, -0.95],
            stability_summary=diagnostic_summary,
        )
    )

    assert kqd["reported_energy"] == pytest.approx(-1.11)
    assert kqd["reported_energy_source"] == "stabilized_projected_diagnostic"
    assert qfd["reported_energy"] == pytest.approx(-1.07)
    assert qfd["reported_energy_source"] == "stabilized_projected_diagnostic"
    assert qfd["algorithm_metrics"]["stability_summary"]["stability_state"] == "stabilized"


@pytest.mark.parametrize("algorithm", ["kqd", "qfd"])
def test_normalize_result_accepts_stable_branch_projected_spectrum(algorithm: str) -> None:
    if algorithm == "kqd":
        result = KQDResult(
            algorithm=algorithm,
            primary_energy=-1.11,
            primary_iterations=2,
            converged=False,
            ritz_values=[-1.11],
            krylov_rank=2,
            orthogonality_metrics={},
            matrix_element_summary={"matrix_element_strategy": "branch_estimator"},
            stability_summary={
                "stability_state": "stable",
                "overlap_condition": 2.0,
                "overlap_min_eigenvalue": 0.5,
                "dropped_rank": 0,
            },
        )
        source = "lowest_krylov_ritz_value"
    else:
        result = QFDResult(
            algorithm=algorithm,
            primary_energy=-1.07,
            primary_iterations=2,
            converged=False,
            filter_eigenvalues=[-1.07],
            conditioning_summary={},
            matrix_element_summary={"matrix_element_strategy": "branch_estimator"},
            stability_summary={
                "stability_state": "stable",
                "overlap_condition": 2.0,
                "overlap_min_eigenvalue": 0.5,
                "dropped_rank": 0,
            },
        )
        source = "lowest_filter_eigenvalue"

    normalized = normalize_result(result)

    assert normalized["reported_energy"] == pytest.approx(result.primary_energy)
    assert normalized["reported_energy_source"] == source


def test_normalize_result_does_not_infer_projected_convergence_without_residual() -> None:
    normalized = normalize_result(
        KQDResult(
            algorithm="kqd",
            primary_energy=-1.11,
            primary_iterations=3,
            converged=True,
            ritz_values=[-1.11],
            krylov_rank=3,
            orthogonality_metrics={
                "stability_state": "stable",
                "overlap_condition": 1.0,
                "overlap_min_eigenvalue": 1.0,
            },
        )
    )

    convergence = normalized["algorithm_metrics"]["convergence"]
    assert convergence["projected_system_stable"] is True
    assert convergence["scientific_converged"] is None
    assert convergence["convergence_failure_reason"] == "projected_residual_unavailable"


def test_normalize_result_rejects_unstable_projected_convergence() -> None:
    normalized = normalize_result(
        KQDResult(
            algorithm="kqd",
            primary_energy=-1.11,
            primary_iterations=3,
            converged=True,
            ritz_values=[-1.11],
            krylov_rank=3,
            orthogonality_metrics={
                "stability_state": "invalid",
                "overlap_condition": 1e16,
                "overlap_min_eigenvalue": -1e-8,
                "relative_ritz_residual": 1e-10,
                "residual_convergence_threshold": 1e-6,
            },
        )
    )

    convergence = normalized["algorithm_metrics"]["convergence"]

    assert convergence["projected_system_stable"] is False
    assert convergence["scientific_converged"] is False
    assert convergence["convergence_criterion"] == (
        "projected_overlap_condition_and_generalized_residual"
    )
    assert convergence["convergence_failure_reason"] == "projected_system_unstable"


def test_normalize_result_rejects_scientific_convergence_with_invalid_reference() -> None:
    result = VQEResult(
        algorithm="vqe",
        primary_energy=-1.13,
        primary_iterations=3,
        converged=True,
        optimal_parameters=[],
        convergence_trace=[-1.13, -1.13],
        optimizer_diagnostics={
            "final_delta_energy": 0.0,
            "convergence_threshold": 1e-8,
            "termination_reason": "optimizer_success",
        },
    )

    normalized = normalize_result(
        result,
        hamiltonian_metadata={
            "casci_energy": -1.15,
            "pipeline": "pyscf+ffsim",
            "reference_basis": "sto-3g",
            "reference_active_space": [2, 2],
        },
    )

    convergence = normalized["algorithm_metrics"]["convergence"]

    assert convergence["energy_sane"] is False
    assert convergence["scientific_converged"] is False
    assert convergence["convergence_failure_reason"] == "energy_consistency_invalid"


def test_normalize_result_for_qse_dataclass() -> None:
    result = QSEResult(
        algorithm="qse",
        primary_energy=-0.84,
        primary_iterations=2,
        converged=True,
        eigenvalues=[-0.9, -0.84],
        overlap_condition=1.25,
        reference_state_energy=-0.82,
    )

    normalized = normalize_result(result)

    assert normalized["algorithm"] == "qse"
    assert normalized["iterations"] == 2
    assert normalized["algorithm_metrics"]["eigenvalues"] == [-0.9, -0.84]
    assert normalized["algorithm_metrics"]["reference_state_energy"] == -0.82


@pytest.mark.parametrize(
    ("selected_solution", "expected_provenance"),
    [
        ("sqd_core", "selected_sqd_core_backend_sampler"),
        ("krylov_extension", "selected_krylov_extension_classical_exact"),
    ],
)
def test_normalize_result_describes_skqd_solution_provenance(
    selected_solution: str,
    expected_provenance: str,
) -> None:
    result = SKQDResult(
        algorithm="skqd",
        primary_energy=-0.76,
        primary_iterations=5,
        converged=True,
        sqd_core={"primary_energy": -0.7},
        krylov_extension_diagnostics={"selected_solution": selected_solution},
    )

    normalized = normalize_result(result)

    assert normalized["reported_energy_source"] == expected_provenance
    assert normalized["raw_result"]["reported_energy_source"] == expected_provenance
    assert normalized["energy_policy"]["selected_solution_provenance"] == expected_provenance
    assert (
        normalized["algorithm_metrics"]["energy_policy"]["selected_solution_provenance"]
        == expected_provenance
    )


def test_normalize_result_for_skqd_dataclass() -> None:
    result = SKQDResult(
        algorithm="skqd",
        primary_energy=-0.81,
        primary_iterations=5,
        converged=True,
        sqd_core={"algorithm": "sqd", "primary_energy": -0.83, "primary_iterations": 3},
        krylov_extension_diagnostics={"krylov_extension_dim": 2.0, "ritz_values": [-0.82, -0.81]},
    )

    normalized = normalize_result(result)

    assert normalized["algorithm"] == "skqd"
    assert normalized["iterations"] == 5
    assert normalized["algorithm_metrics"]["sqd_core"]["algorithm"] == "sqd"
    assert normalized["algorithm_metrics"]["krylov_extension_diagnostics"]["ritz_values"] == [
        -0.82,
        -0.81,
    ]


def test_normalize_result_promotes_skqd_work_ledger() -> None:
    result = SKQDResult(
        algorithm="skqd",
        primary_energy=-0.81,
        primary_iterations=2,
        converged=False,
        sqd_core={"status": "not_run"},
        krylov_extension_diagnostics={
            "work_ledger": {
                "ledger_version": 1,
                "sampler_run_attempts": 2,
                "sampler_returned_raw_sample_rows": 16,
            }
        },
    )

    normalized = normalize_result(result)

    assert normalized["algorithm_metrics"]["work_ledger"] == {
        "ledger_version": 1,
        "sampler_run_attempts": 2,
        "sampler_returned_raw_sample_rows": 16,
    }


@pytest.mark.parametrize(
    ("selected_solution", "diagnostics", "expected_converged", "expected_criterion"),
    [
        (
            "sqd_core",
            {
                "extension_status": "failed",
                "sqd_converged": True,
                "relative_residual": None,
            },
            True,
            "selected_sqd_core_sqd_convergence",
        ),
        (
            "krylov_extension",
            {
                "sqd_converged": True,
                "relative_residual": 1e-8,
                "residual_tolerance": 1e-6,
            },
            True,
            "selected_krylov_extension_residual_and_sqd_convergence",
        ),
        (
            "krylov_extension",
            {"sqd_converged": True, "relative_residual": None},
            None,
            "selected_krylov_extension_residual_and_sqd_convergence",
        ),
    ],
)
def test_normalize_result_classifies_skqd_selected_solution_convergence(
    selected_solution: str,
    diagnostics: dict[str, object],
    expected_converged: bool | None,
    expected_criterion: str,
) -> None:
    result = SKQDResult(
        algorithm="skqd",
        primary_energy=-0.81,
        primary_iterations=5,
        converged=True,
        sqd_core={"converged": True},
        krylov_extension_diagnostics={
            "selected_solution": selected_solution,
            **diagnostics,
        },
    )

    convergence = normalize_result(result)["algorithm_metrics"]["convergence"]

    assert convergence["scientific_converged"] is expected_converged
    assert convergence["convergence_criterion"] == expected_criterion
    if selected_solution == "sqd_core":
        assert convergence["convergence_failure_reason"] is None
    else:
        assert convergence["convergence_value"] == diagnostics.get("relative_residual")


def test_normalize_result_classifies_skqd_sample_union_convergence() -> None:
    result = SKQDResult(
        algorithm="skqd",
        primary_energy=-1.137,
        primary_iterations=4,
        converged=True,
        sqd_core={"converged": None},
        krylov_extension_diagnostics={
            "selected_solution": "skqd_sample_union",
            "convergence_status": "subspace_saturated",
            "convergence_verdict": {
                "converged": True,
                "convergence_status": "subspace_saturated",
                "subspace_saturated": True,
                "complete_selected_ci_solve": True,
                "full_sector_recovered": False,
                "selected_ci_fraction": 0.75,
                "final_prefix_growth_delta": 0,
                "convergence_criterion": (
                    "krylov_subspace_saturation_and_complete_selected_ci_solve"
                ),
            },
        },
    )

    convergence = normalize_result(result)["algorithm_metrics"]["convergence"]

    assert convergence["scientific_converged"] is True
    assert convergence["convergence_criterion"] == (
        "krylov_subspace_saturation_and_complete_selected_ci_solve"
    )
    assert convergence["convergence_value"]["subspace_saturated"] is True
    assert convergence["convergence_failure_reason"] is None


def test_normalize_result_reports_skqd_sample_union_not_converged() -> None:
    result = SKQDResult(
        algorithm="skqd",
        primary_energy=-1.0,
        primary_iterations=4,
        converged=False,
        sqd_core={"converged": None},
        krylov_extension_diagnostics={
            "selected_solution": "skqd_sample_union",
            "convergence_status": "sampling_convergence_not_established",
            "convergence_verdict": {
                "converged": False,
                "convergence_status": "sampling_convergence_not_established",
                "subspace_saturated": False,
                "complete_selected_ci_solve": True,
                "full_sector_recovered": False,
                "selected_ci_fraction": 0.4,
                "final_prefix_growth_delta": 3,
            },
        },
    )

    convergence = normalize_result(result)["algorithm_metrics"]["convergence"]

    assert convergence["scientific_converged"] is False
    assert convergence["convergence_failure_reason"] == "sampling_convergence_not_established"


def test_normalize_result_classical_references_propagated() -> None:
    result = VQEResult(
        algorithm="vqe",
        primary_energy=-1.13,
        primary_iterations=3,
        converged=True,
        optimal_parameters=[0.1, 0.2],
        convergence_trace=[-1.13, -1.12, -1.11],
        optimizer_diagnostics={
            "final_energy": -1.11,
            "best_observed_energy": -1.13,
            "reported_energy_source": "best_observed_optimizer_evaluation",
        },
    )
    metadata = {"hf_energy": -1.05, "casci_energy": -1.15, "pipeline": "pyscf+ffsim"}

    normalized = normalize_result(result, hamiltonian_metadata=metadata)

    refs = normalized["raw_result"]["classical_references"]
    assert refs["hf"] == pytest.approx(-1.05)
    assert refs["fci"] == pytest.approx(-1.15)


def test_normalize_result_records_reference_provenance_separately() -> None:
    result = VQEResult(
        algorithm="vqe",
        primary_energy=-1.13,
        primary_iterations=3,
        converged=True,
        optimal_parameters=[0.1, 0.2],
        convergence_trace=[-1.13, -1.12, -1.11],
    )
    metadata = {
        "hf_energy": -1.05,
        "casci_energy": -1.15,
        "pipeline": "pyscf+ffsim",
        "reference_basis": "sto-3g",
        "reference_active_space": [2, 2],
        "reference_method": "CASCI",
        "reference_backend_target": "local_classical",
        "reference_solver_path": "pyscf+ffsim",
        "reference_precision": None,
        "reference_precision_policy": "deterministic_float64",
        "source_commit": "c" * 40,
        "hamiltonian_sha256": "a" * 64,
    }

    normalized = normalize_result(result, hamiltonian_metadata=metadata)

    assert normalized["energy"] == pytest.approx(-1.13)
    assert normalized["algorithm_metrics"]["reference_provenance"] == {
        "method": "CASCI",
        "backend_target": "local_classical",
        "solver_path": "pyscf+ffsim",
        "basis": "sto-3g",
        "active_space": [2, 2],
        "hamiltonian_sha256": "a" * 64,
        "energy": pytest.approx(-1.15),
        "reference_precision": None,
        "reference_precision_policy": "deterministic_float64",
        "source_commit": "c" * 40,
        "validity_status": "valid",
        "validity_reasons": [],
    }
    assert normalized["algorithm_metrics"]["energy_consistency"] == {
        "status": "valid",
        "reported_energy": pytest.approx(-1.13),
        "reference_energy": pytest.approx(-1.15),
        "signed_error": pytest.approx(0.02),
        "absolute_error": pytest.approx(0.02),
        "tolerance_ha": 1e-12,
        "failure_reasons": [],
    }


def test_normalize_result_persists_and_validates_problem_manifest() -> None:
    result = VQEResult(
        algorithm="vqe",
        primary_energy=-1.13,
        primary_iterations=1,
        converged=True,
        optimal_parameters=[],
        convergence_trace=[-1.13],
    )
    manifest = build_problem_manifest(
        molecule=PreparedMolecule(
            atom_spec=[("H", (0.0, 0.0, 0.0)), ("H", (0.0, 0.0, 0.7414))],
            basis="sto-3g",
            charge=0,
            multiplicity=1,
            active_space=(2, 2),
        ),
        resolved_active_space=(2, 2),
        num_spatial_orbitals=2,
        num_qubits=4,
        num_electrons_alpha=1,
        num_electrons_beta=1,
        constant=-0.2,
        nuclear_repulsion=0.7,
        hamiltonian_sha256="a" * 64,
        total_electrons=2,
        total_molecular_orbitals=2,
        active_space_auto_reduced=False,
    )

    normalized = normalize_result(result, hamiltonian_metadata={"problem_manifest": manifest})

    assert normalized["problem_manifest"] == manifest
    assert normalized["algorithm_metrics"]["problem_manifest"] == manifest
    assert normalized["raw_result"]["problem_manifest"] == manifest

    invalid_manifest = dict(manifest)
    invalid_manifest["manifest_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="problem manifest hash is invalid"):
        normalize_result(result, hamiltonian_metadata={"problem_manifest": invalid_manifest})


def test_normalize_qse_result_records_reference_state_and_cost() -> None:
    result = QSEResult(
        algorithm="qse",
        primary_energy=-1.15,
        primary_iterations=4,
        converged=True,
        eigenvalues=[-1.15],
        overlap_condition=1.2,
        reference_state_energy=-1.1,
        reference_method="vqe",
        reference_circuit_artifacts=[
            {
                "role": "reference",
                "depth": 12,
                "reference_cost": {
                    "cost_type": "vqe_reference_optimization",
                    "cost_status": "measured",
                    "objective_evaluations": 25,
                    "state_preparations": 25,
                },
            }
        ],
    )

    normalized = normalize_result(result)
    metrics = normalized["algorithm_metrics"]

    assert metrics["reference_state"] == {
        "method": "vqe",
        "energy": pytest.approx(-1.1),
    }
    assert metrics["reference_cost"] == {
        "cost_type": "vqe_reference_optimization",
        "cost_status": "measured",
        "objective_evaluations": 25,
        "state_preparations": 25,
        "reference_method": "vqe",
        "circuit_artifact_count": 1,
    }


@pytest.mark.parametrize(
    "result",
    [
        SQDResult(
            algorithm="sqd",
            primary_energy=-0.72,
            primary_iterations=2,
            converged=True,
            sci_energies=[-0.7, -0.72],
            configuration_recovery_trace=[],
            spin_diagnostics={},
            sci_result_package={
                "best_energy": -0.72,
                "final_energy": -0.7,
                "best_iteration": 2,
                "reported_energy_source": "best_observed_sqd_iteration",
            },
        ),
        KQDResult(
            algorithm="kqd",
            primary_energy=-0.73,
            primary_iterations=3,
            converged=True,
            ritz_values=[-0.73],
            krylov_rank=3,
            orthogonality_metrics={},
        ),
        QFDResult(
            algorithm="qfd",
            primary_energy=-0.74,
            primary_iterations=4,
            converged=True,
            filter_eigenvalues=[-0.74],
            conditioning_summary={},
        ),
        QSEResult(
            algorithm="qse",
            primary_energy=-0.75,
            primary_iterations=2,
            converged=True,
            eigenvalues=[-0.75],
            overlap_condition=1.0,
            reference_state_energy=-0.7,
        ),
        SKQDResult(
            algorithm="skqd",
            primary_energy=-0.76,
            primary_iterations=5,
            converged=True,
            sqd_core={},
            krylov_extension_diagnostics={},
        ),
    ],
)
def test_normalize_result_never_replaces_algorithm_energy_with_classical_reference(
    result,
) -> None:
    metadata = {"hf_energy": -100.0, "casci_energy": -999.0}

    normalized = normalize_result(result, hamiltonian_metadata=metadata)

    assert normalized["primary_energy"] == pytest.approx(result.primary_energy)
    assert normalized["energy"] == pytest.approx(result.primary_energy)
    assert normalized["algorithm_metrics"]["classical_references"]["fci"] == pytest.approx(-999.0)
    assert normalized["energy_policy"]["classical_references_are_context_only"] is True
    assert normalized["algorithm_metrics"]["energy_policy"] == normalized["energy_policy"]


def test_normalize_result_describes_sqd_best_observed_energy_policy() -> None:
    result = SQDResult(
        algorithm="sqd",
        primary_energy=-1.2,
        primary_iterations=3,
        converged=True,
        sci_energies=[-1.0, -1.2, -1.1],
        configuration_recovery_trace=[],
        spin_diagnostics={},
        sci_result_package={
            "final_energy": -1.1,
            "best_energy": -1.2,
            "best_iteration": 2,
            "reported_energy_source": "best_observed_sqd_iteration",
        },
    )

    normalized = normalize_result(result)

    assert normalized["energy"] == pytest.approx(-1.2)
    assert normalized["energy_policy"]["primary_energy_source"] == "best_observed_sqd_iteration"
    assert normalized["energy_policy"]["best_iteration"] == 2
    assert (
        "sci_result_package.final_energy" in normalized["energy_policy"]["candidate_energy_fields"]
    )


def test_normalize_result_classical_references_absent_when_no_metadata() -> None:
    result = VQEResult(
        algorithm="vqe",
        primary_energy=-1.11,
        primary_iterations=3,
        converged=True,
        optimal_parameters=[],
        convergence_trace=[],
    )

    normalized = normalize_result(result)

    assert normalized["raw_result"]["classical_references"] == {}
