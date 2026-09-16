"""IBM Runtime adapter integration surface."""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from statistics import median
from typing import Any

from worker.adapters.base import (
    AdapterCapabilities,
    BackendAdapter,
    BackendExecutionContext,
    PrimitiveJobObserver,
    TrackingPrimitive,
)
from worker.chemistry.circuit_artifacts import serialize_legacy_circuit_preview
from worker.exceptions import BackendError, IBMTimeoutError

_DEFAULT_CONTEXT = BackendExecutionContext(backend_target="ibm_runtime")
_IBM_RUNTIME_SUBMISSION_TIMEOUT_SECONDS = 120.0
_IBM_RUNTIME_MAX_JOBS = 128
_IBM_RUNTIME_MAX_PUBS_PER_JOB = 128
_IBM_RUNTIME_MAX_SHOTS = 100_000


class IBMAdapter(BackendAdapter):
    """Adapter for IBM Runtime backend execution."""

    _caps = AdapterCapabilities(
        backend_target="ibm_runtime",
        enabled=True,
        supports_noise_profile=False,
    )

    def __init__(
        self,
        *,
        service_factory: Callable[..., Any] | None = None,
        estimator_factory: Callable[..., Any] | None = None,
        sampler_factory: Callable[..., Any] | None = None,
    ) -> None:
        self._service_factory = service_factory
        self._estimator_factory = estimator_factory
        self._sampler_factory = sampler_factory
        self._service: Any | None = None
        self._last_backend_name: str | None = None
        self._job_ids: list[str] = []
        self._last_transpilation_summary: dict[str, Any] = {}
        self._last_transpiled_preview: dict[str, Any] = {}
        self._last_runtime_observation: dict[str, Any] = {}
        self._runtime_submitted_job_count = 0
        self._runtime_failure_payloads: list[dict[str, Any]] = []

    @property
    def capabilities(self) -> AdapterCapabilities:
        return self._caps

    def create_estimator(self, context: BackendExecutionContext | None = None) -> Any:
        resolved = context or _DEFAULT_CONTEXT
        _validate_runtime_context(resolved, primitive_name="EstimatorV2")
        self._job_ids = []
        self._last_transpilation_summary = {}
        self._last_transpiled_preview = {}
        self._last_runtime_observation = {}
        self._runtime_submitted_job_count = 0
        self._runtime_failure_payloads = []
        backend = self._resolve_backend(resolved)
        backend_name = _backend_name(
            backend,
            fallback=_backend_resolution_fallback(resolved),
        )
        factory = self._estimator_factory or _runtime_estimator_factory()
        primitive = factory(mode=backend, options=_runtime_estimator_options(resolved))
        return TrackingPrimitive(
            primitive,
            self._job_ids,
            run_observer=self._build_run_observer(backend, resolved),
            run_transform=self._build_runtime_run_transform(
                self._build_estimator_run_transform(backend, resolved),
                resolved,
            ),
            run_guard=resolved.primitive_run_guard,
            job_observer=self._build_job_observer(backend, resolved),
            submission_timeout_seconds=_runtime_submission_timeout_seconds(),
            run_timeout_error_factory=_build_runtime_submission_timeout_error(
                primitive_name="EstimatorV2",
                backend_name=backend_name,
            ),
            run_label=f"IBM Runtime EstimatorV2 submission to {backend_name}",
            run_failure_observer=lambda error, args, kwargs: self._record_runtime_submission_failure(
                error,
                args,
                kwargs,
                context=resolved,
            ),
        )

    def create_sampler(self, context: BackendExecutionContext | None = None) -> Any:
        resolved = context or _DEFAULT_CONTEXT
        _validate_runtime_context(resolved, primitive_name="SamplerV2")
        self._job_ids = []
        self._last_transpilation_summary = {}
        self._last_transpiled_preview = {}
        self._last_runtime_observation = {}
        self._runtime_submitted_job_count = 0
        self._runtime_failure_payloads = []
        backend = self._resolve_backend(resolved)
        backend_name = _backend_name(
            backend,
            fallback=_backend_resolution_fallback(resolved),
        )
        factory = self._sampler_factory or _runtime_sampler_factory()
        primitive = factory(mode=backend, options=_runtime_sampler_options(resolved))
        return TrackingPrimitive(
            primitive,
            self._job_ids,
            run_observer=self._build_run_observer(backend, resolved),
            run_transform=self._build_runtime_run_transform(
                self._build_sampler_run_transform(backend, resolved),
                resolved,
            ),
            run_guard=resolved.primitive_run_guard,
            job_observer=self._build_job_observer(backend, resolved),
            submission_timeout_seconds=_runtime_submission_timeout_seconds(),
            run_timeout_error_factory=_build_runtime_submission_timeout_error(
                primitive_name="SamplerV2",
                backend_name=backend_name,
            ),
            run_label=f"IBM Runtime SamplerV2 submission to {backend_name}",
            run_failure_observer=lambda error, args, kwargs: self._record_runtime_submission_failure(
                error,
                args,
                kwargs,
                context=resolved,
            ),
        )

    def run_vqe(self, *, hamiltonian: object, config: dict) -> object:
        """Run VQE using IBM Runtime backend."""
        from worker.chemistry.algorithms.vqe.workflow import run_vqe

        return run_vqe(
            hamiltonian=hamiltonian,
            backend=self.create_estimator(_DEFAULT_CONTEXT),
            config=config,
        )

    def execution_metadata(self, context: BackendExecutionContext | None = None) -> dict[str, Any]:
        resolved = context or _DEFAULT_CONTEXT
        transpilation_summary: dict[str, Any] = {
            "optimization_level": resolved.optimization_level,
            "preview": "Runtime primitive transpilation handled by IBM backend target",
        }
        transpilation_summary.update(self._last_transpilation_summary)
        if self._last_backend_name is None:
            self._last_backend_name = _backend_name(
                self._resolve_backend(resolved),
                fallback=_backend_resolution_fallback(resolved),
            )
        requested_backend_name = _requested_backend_name(resolved)
        observed_shots = self._last_runtime_observation.get("shots")
        metadata: dict[str, Any] = {
            "backend_target": self.capabilities.backend_target,
            "requested_target": resolved.backend_target,
            "requested_backend_name": requested_backend_name,
            "actual_execution_target": "ibm_runtime",
            "execution_mode": "ibm_runtime_primitive",
            "actual_path_class": "ibm_runtime_primitive",
            "resolved_backend_name": self._last_backend_name
            or _backend_resolution_fallback(resolved),
            "fallback_reason": _backend_fallback_reason(
                requested_backend_name,
                self._last_backend_name,
            ),
            "selection_policy": _selection_policy(resolved),
            "backend_primitives_used": True,
            "primitive_family": "qiskit_ibm_runtime",
            "shots": int(observed_shots) if isinstance(observed_shots, (int, float)) else None,
            "requested_shots": (
                resolved.requested_shots
                if resolved.requested_shots is not None
                else resolved.shots
            ),
            "effective_shots": (
                int(observed_shots) if isinstance(observed_shots, (int, float)) else None
            ),
            "requested_estimator_precision": (
                resolved.requested_estimator_precision
                if resolved.requested_estimator_precision is not None
                else resolved.estimator_precision
            ),
            "effective_estimator_precision": _runtime_effective_estimator_precision(resolved),
            "measurement_mode": "precision_sampled",
            "uncertainty_policy": _runtime_uncertainty_policy(resolved),
            "optimization_level": resolved.optimization_level,
            "noise_summary": {"enabled": False, "source": "hardware"},
            "simulator_method": None,
            "transpilation_summary": transpilation_summary,
        }
        if "pub_count" in self._last_runtime_observation:
            metadata["pub_count"] = int(self._last_runtime_observation["pub_count"])
        if self._last_transpiled_preview:
            metadata["transpiled_circuit_preview"] = dict(self._last_transpiled_preview)
        if self._job_ids:
            metadata["job_ids"] = list(self._job_ids)
            metadata["ibm_job_id"] = self._job_ids[-1]
        if self._runtime_failure_payloads:
            metadata["runtime_failure_payloads"] = list(self._runtime_failure_payloads)
        return metadata

    def _build_run_observer(
        self,
        backend: Any,
        context: BackendExecutionContext,
    ) -> Callable[[tuple[Any, ...], dict[str, Any], Any], None]:
        def observe(args: tuple[Any, ...], kwargs: dict[str, Any], _job: Any) -> None:
            self._runtime_submitted_job_count += 1
            if self._last_transpilation_summary:
                return
            circuit = _extract_pub_circuit(args, kwargs)
            if circuit is None:
                return
            self._last_transpilation_summary = _transpile_circuit_summary(
                circuit,
                backend=backend,
                optimization_level=context.optimization_level,
                seed_transpiler=context.backend_options.get("seed_transpiler"),
            )

        return observe

    def _build_runtime_run_transform(
        self,
        transform: Callable[
            [tuple[Any, ...], dict[str, Any]],
            tuple[tuple[Any, ...], dict[str, Any]],
        ],
        context: BackendExecutionContext,
    ) -> Callable[[tuple[Any, ...], dict[str, Any]], tuple[tuple[Any, ...], dict[str, Any]]]:
        def validate_and_transform(
            args: tuple[Any, ...],
            kwargs: dict[str, Any],
        ) -> tuple[tuple[Any, ...], dict[str, Any]]:
            _validate_runtime_submission(
                context,
                args,
                kwargs,
                submitted_jobs=self._runtime_submitted_job_count,
            )
            return transform(args, kwargs)

        return validate_and_transform

    def _record_runtime_submission_failure(
        self,
        error: BaseException,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        *,
        context: BackendExecutionContext,
    ) -> None:
        payload: dict[str, Any] = {
            "stage": "submission",
            "error_type": type(error).__name__,
        }
        pub_count = _runtime_pub_count(args, kwargs)
        if pub_count is not None:
            payload["pub_count"] = pub_count
        shots = _runtime_requested_shots(context, kwargs)
        if shots is not None:
            payload["shots"] = shots
        self._runtime_failure_payloads.append(payload)

    def _build_job_observer(
        self,
        backend: Any,
        context: BackendExecutionContext,
    ) -> PrimitiveJobObserver:
        primitive_job_observer = context.primitive_job_observer

        backend_name = _backend_name(
            backend,
            fallback=_backend_resolution_fallback(context),
        )

        def observe(job: Any, metadata: dict[str, Any]) -> Any | None:
            shots = metadata.get("shots")
            if isinstance(shots, (int, float)):
                self._last_runtime_observation["shots"] = int(shots)
            pub_count = metadata.get("pub_count")
            if isinstance(pub_count, (int, float)):
                self._last_runtime_observation["pub_count"] = int(pub_count)

            if primitive_job_observer is None:
                return None
            return primitive_job_observer(
                job,
                {
                    **metadata,
                    "backend": backend_name,
                    "backend_target": context.backend_target,
                    "selection_policy": _selection_policy(context),
                },
            )

        return observe

    def _build_estimator_run_transform(
        self,
        backend: Any,
        context: BackendExecutionContext,
    ) -> Callable[[tuple[Any, ...], dict[str, Any]], tuple[tuple[Any, ...], dict[str, Any]]]:
        transpiler = _RuntimeTranspiler(backend=backend, context=context)

        def transform(
            args: tuple[Any, ...],
            kwargs: dict[str, Any],
        ) -> tuple[tuple[Any, ...], dict[str, Any]]:
            pubs, replace = _extract_pubs(args, kwargs)
            if pubs is None:
                return args, kwargs

            transformed = [_transpile_estimator_pub(pub, transpiler=transpiler) for pub in pubs]
            if transpiler.last_summary:
                self._last_transpilation_summary = transpiler.last_summary
            if transpiler.last_preview:
                self._last_transpiled_preview = transpiler.last_preview
            return replace(transformed)

        return transform

    def _build_sampler_run_transform(
        self,
        backend: Any,
        context: BackendExecutionContext,
    ) -> Callable[[tuple[Any, ...], dict[str, Any]], tuple[tuple[Any, ...], dict[str, Any]]]:
        transpiler = _RuntimeTranspiler(backend=backend, context=context)

        def transform(
            args: tuple[Any, ...],
            kwargs: dict[str, Any],
        ) -> tuple[tuple[Any, ...], dict[str, Any]]:
            pubs, replace = _extract_pubs(args, kwargs)
            if pubs is None:
                return args, kwargs

            transformed = [_transpile_sampler_pub(pub, transpiler=transpiler) for pub in pubs]
            if transpiler.last_summary:
                self._last_transpilation_summary = transpiler.last_summary
            if transpiler.last_preview:
                self._last_transpiled_preview = transpiler.last_preview
            return replace(transformed)

        return transform

    def _resolve_backend(self, context: BackendExecutionContext) -> Any:
        service = self._resolve_service(context)
        backend_name = _requested_backend_name(context)
        selection_policy = _selection_policy(context)
        try:
            if backend_name:
                backend = service.backend(str(backend_name))
            elif selection_policy == "least_error":
                backend = _least_error_backend(service)
            elif selection_policy in {"least_busy", "requested"}:
                backend = service.least_busy(operational=True, simulator=False)
            elif selection_policy == "manual":
                raise BackendError(
                    "Manual IBM Runtime selection requires backend_options.backend_name."
                )
            else:
                backend = service.least_busy(operational=True, simulator=False)
        except Exception as exc:  # pragma: no cover - exercised by mocked tests
            raise BackendError(
                f"Unable to resolve IBM Runtime backend ({type(exc).__name__})"
            ) from None

        simulator_flag = _backend_is_simulator(backend)
        if simulator_flag is True:
            raise BackendError("IBM Runtime backend selection resolved to a simulator")
        if simulator_flag is not False:
            raise BackendError(
                "IBM Runtime backend selection did not provide explicit non-simulator metadata"
            )

        self._last_backend_name = _backend_name(
            backend,
            fallback=_backend_resolution_fallback(context),
        )
        return backend

    def _resolve_service(self, context: BackendExecutionContext) -> Any:
        if self._service is not None:
            return self._service

        factory = self._service_factory or _runtime_service_factory()
        options = _service_options(context.backend_options)
        if not options.get("token") or not options.get("instance"):
            raise BackendError(
                "IBM Runtime credentials are not configured. Save an active IBM profile in Settings before running on IBM Runtime."
            )
        try:
            self._service = factory(**options)
        except Exception as exc:
            raise BackendError(
                f"Unable to initialize IBM Runtime service ({type(exc).__name__})"
            ) from None
        return self._service


def _runtime_service_factory() -> Callable[..., Any]:
    from qiskit_ibm_runtime import QiskitRuntimeService

    return QiskitRuntimeService


def _runtime_estimator_factory() -> Callable[..., Any]:
    from qiskit_ibm_runtime import EstimatorV2

    return EstimatorV2


def _runtime_sampler_factory() -> Callable[..., Any]:
    from qiskit_ibm_runtime import SamplerV2

    return SamplerV2


def _runtime_submission_timeout_seconds() -> float:
    return _IBM_RUNTIME_SUBMISSION_TIMEOUT_SECONDS


def _build_runtime_submission_timeout_error(
    *,
    primitive_name: str,
    backend_name: str,
) -> Callable[[float], Exception]:
    def build(timeout_seconds: float) -> Exception:
        seconds_label = (
            str(int(timeout_seconds))
            if float(timeout_seconds).is_integer()
            else f"{timeout_seconds:.1f}"
        )
        return IBMTimeoutError(
            "IBM Runtime "
            f"{primitive_name} submission to {backend_name} did not return within "
            f"{seconds_label}s. The worker timed out before IBM Runtime returned a job handle."
        )

    return build


def _runtime_estimator_options(context: BackendExecutionContext) -> dict[str, Any]:
    if context.estimator_precision > 0.0:
        return {"default_precision": context.estimator_precision}
    return {"default_shots": context.shots}


def _runtime_sampler_options(context: BackendExecutionContext) -> dict[str, Any]:
    return {"default_shots": context.shots}


def _validate_runtime_context(
    context: BackendExecutionContext,
    *,
    primitive_name: str,
) -> None:
    """Reject options that cannot describe one bounded Runtime primitive run."""
    if context.noise_profile is not None:
        raise BackendError("IBM Runtime does not accept a local noise_profile")
    if context.simulator_method != "automatic":
        raise BackendError("IBM Runtime does not accept an Aer simulator_method")
    if "seed_simulator" in context.backend_options:
        raise BackendError("IBM Runtime does not accept seed_simulator")
    requested_shots = context.requested_shots if context.requested_shots is not None else context.shots
    if requested_shots > _IBM_RUNTIME_MAX_SHOTS:
        raise BackendError(
            f"IBM Runtime shots exceed the per-job cap of {_IBM_RUNTIME_MAX_SHOTS}"
        )


def _runtime_pub_count(args: tuple[Any, ...], kwargs: dict[str, Any]) -> int | None:
    pubs = kwargs.get("pubs") if "pubs" in kwargs else (args[0] if args else None)
    return len(pubs) if isinstance(pubs, (list, tuple)) else None


def _runtime_requested_shots(
    context: BackendExecutionContext,
    kwargs: dict[str, Any],
) -> int | None:
    value = kwargs.get("shots", context.shots)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    shots = int(value)
    return shots if shots > 0 else None


def _validate_runtime_submission(
    context: BackendExecutionContext,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    *,
    submitted_jobs: int,
) -> None:
    """Enforce caps before a Runtime submission creates another job handle."""
    if submitted_jobs >= _IBM_RUNTIME_MAX_JOBS:
        raise BackendError(f"IBM Runtime job cap of {_IBM_RUNTIME_MAX_JOBS} was reached")
    pub_count = _runtime_pub_count(args, kwargs)
    if pub_count is None or pub_count < 1:
        raise BackendError("IBM Runtime submission requires at least one PUB")
    if pub_count > _IBM_RUNTIME_MAX_PUBS_PER_JOB:
        raise BackendError(
            f"IBM Runtime PUB cap of {_IBM_RUNTIME_MAX_PUBS_PER_JOB} per job was exceeded"
        )
    shots = _runtime_requested_shots(context, kwargs)
    if shots is None:
        raise BackendError("IBM Runtime submission requires a positive numeric shot count")
    if shots > _IBM_RUNTIME_MAX_SHOTS:
        raise BackendError(
            f"IBM Runtime shots exceed the per-job cap of {_IBM_RUNTIME_MAX_SHOTS}"
        )


def _runtime_effective_estimator_precision(context: BackendExecutionContext) -> float:
    if context.estimator_precision > 0.0:
        return context.estimator_precision
    return 1.0 / math.sqrt(context.shots)


def _runtime_uncertainty_policy(context: BackendExecutionContext) -> str:
    if context.estimator_precision > 0.0:
        return "ibm_runtime_configured_precision"
    return "ibm_runtime_shot_precision"


def _service_options(backend_options: dict[str, Any]) -> dict[str, Any]:
    options: dict[str, Any] = {}
    token = backend_options.get("token")
    channel = backend_options.get("channel")
    instance = backend_options.get("instance")
    if token:
        options["token"] = token
        channel = channel or "ibm_quantum_platform"
    if channel:
        options["channel"] = channel
    if instance:
        options["instance"] = instance
    if backend_options.get("url"):
        options["url"] = backend_options["url"]
    return options


def _selection_policy(context: BackendExecutionContext) -> str:
    raw = context.selection_policy
    if not isinstance(raw, str) or not raw.strip() or raw.strip().lower() == "requested":
        raw = context.backend_options.get("selection_policy") or raw
    if raw is None:
        raw = "requested"
    policy = str(raw).strip().lower()
    return policy or "requested"


def _requested_backend_name(context: BackendExecutionContext) -> str | None:
    for key in ("backend_name", "name", "backend"):
        value = context.backend_options.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _backend_resolution_fallback(context: BackendExecutionContext) -> str:
    return _requested_backend_name(context) or _selection_policy(context) or "least_busy"


def _backend_fallback_reason(
    requested_backend_name: str | None,
    resolved_backend_name: str | None,
) -> str | None:
    """Explain a named IBM backend mismatch without exposing provider details."""
    if requested_backend_name is None or resolved_backend_name is None:
        return None
    if requested_backend_name == resolved_backend_name:
        return None
    return "requested_backend_name_differed_from_resolved_backend"


def _call_backend_value(value: Any) -> Any:
    if callable(value):
        try:
            return value()
        except Exception:
            return None
    return value


def _float_or_none(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    parsed = float(value)
    return parsed if math.isfinite(parsed) else None


def _property_error_rate(properties: Any) -> float | None:
    for attr in ("gate_error", "readout_error"):
        numeric = _float_or_none(_call_backend_value(getattr(properties, attr, None)))
        if numeric is not None:
            return numeric
    return None


def _named_parameter_values(items: Any, *, name: str) -> list[float]:
    values: list[float] = []
    for item in items or []:
        for parameter in item or []:
            if getattr(parameter, "name", None) != name:
                continue
            numeric = _float_or_none(getattr(parameter, "value", None))
            if numeric is not None:
                values.append(numeric)
    return values


def _gate_error_values(properties: Any) -> list[float]:
    return _named_parameter_values(
        (
            (getattr(gate, "parameters", []) or [])
            for gate in getattr(properties, "gates", []) or []
        ),
        name="gate_error",
    )


def _readout_error_values(properties: Any) -> list[float]:
    return _named_parameter_values(getattr(properties, "qubits", []) or [], name="readout_error")


def _backend_error_rate(backend: Any) -> float | None:
    properties = _call_backend_value(getattr(backend, "properties", None))
    if properties is None:
        return None

    direct_error_rate = _property_error_rate(properties)
    if direct_error_rate is not None:
        return direct_error_rate

    values = _gate_error_values(properties)
    if not values:
        values = _readout_error_values(properties)
    return float(median(values)) if values else None


def _backend_pending_jobs(backend: Any) -> float:
    status = _call_backend_value(getattr(backend, "status", None))
    pending_jobs = getattr(status, "pending_jobs", None) if status is not None else None
    numeric = _float_or_none(pending_jobs)
    return numeric if numeric is not None else float("inf")


def _least_error_backend(service: Any) -> Any:
    backends = getattr(service, "backends", None)
    if not callable(backends):
        raise BackendError("IBM Runtime service does not expose backend discovery.")
    discovered = backends(simulator=False, operational=True)
    if discovered is None:
        candidates = []
    elif isinstance(discovered, list):
        candidates = discovered
    elif isinstance(discovered, Iterable):
        candidates = list(discovered)
    else:
        raise BackendError("IBM Runtime backend discovery returned a non-iterable response.")
    candidates = [backend for backend in candidates if backend is not None]
    if not candidates:
        raise BackendError("No operational IBM Runtime backends were available.")

    with_error = [
        (backend, error_rate)
        for backend in candidates
        if (error_rate := _backend_error_rate(backend)) is not None
    ]
    if not with_error:
        return service.least_busy(operational=True, simulator=False)

    return min(
        with_error,
        key=lambda item: (
            item[1],
            _backend_pending_jobs(item[0]),
            _backend_name(item[0], fallback=""),
        ),
    )[0]


def _backend_name(backend: Any, *, fallback: str) -> str:
    for attr in ("name", "backend_name"):
        value = getattr(backend, attr, None)
        if callable(value):
            value = value()
        if value:
            return str(value)
    return fallback


def _backend_is_simulator(backend: Any) -> bool | None:
    """Return the explicit simulator flag for an IBM backend, if available."""
    simulator = getattr(backend, "simulator", None)
    if callable(simulator):
        try:
            simulator = simulator()
        except Exception:
            simulator = None
    if isinstance(simulator, bool):
        return simulator

    configuration = getattr(backend, "configuration", None)
    if callable(configuration):
        try:
            configuration = configuration()
        except Exception:
            configuration = None
    configured_simulator = getattr(configuration, "simulator", None)
    return configured_simulator if isinstance(configured_simulator, bool) else None


def _extract_pub_circuit(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any | None:
    if "pubs" in kwargs:
        pubs = kwargs.get("pubs")
    elif args:
        pubs = args[0]
    else:
        pubs = None
    if not isinstance(pubs, (list, tuple)) or len(pubs) == 0:
        return None

    first_pub = pubs[0]
    if isinstance(first_pub, tuple) and len(first_pub) > 0:
        return first_pub[0]

    return getattr(first_pub, "circuit", None)


def _extract_pubs(
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> tuple[Any | None, Callable[[list[Any]], tuple[tuple[Any, ...], dict[str, Any]]]]:
    if "pubs" in kwargs:

        def replace_kwargs(pubs: list[Any]) -> tuple[tuple[Any, ...], dict[str, Any]]:
            next_kwargs = dict(kwargs)
            next_kwargs["pubs"] = pubs
            return args, next_kwargs

        return kwargs.get("pubs"), replace_kwargs

    if not args:

        def replace_missing(pubs: list[Any]) -> tuple[tuple[Any, ...], dict[str, Any]]:
            del pubs
            return args, kwargs

        return None, replace_missing

    def replace_args(pubs: list[Any]) -> tuple[tuple[Any, ...], dict[str, Any]]:
        return (pubs, *args[1:]), kwargs

    return args[0], replace_args


class _RuntimeTranspiler:
    """Transpile primitive PUB circuits to the selected IBM backend ISA."""

    def __init__(self, *, backend: Any, context: BackendExecutionContext) -> None:
        self._backend = backend
        self._context = context
        self._pass_manager: Any | None = None
        self._circuit_cache: dict[int, Any] = {}
        self._observable_cache: dict[tuple[int, int], Any] = {}
        self.last_summary: dict[str, Any] = {}
        self.last_preview: dict[str, Any] = {}

    def transpile_circuit(self, circuit: Any) -> Any:
        if not _is_circuit_like(circuit):
            return circuit

        circuit_id = id(circuit)
        cached = self._circuit_cache.get(circuit_id)
        if cached is not None:
            return cached

        try:
            transpiled = self._pass_manager_for_context().run(circuit)
        except Exception as exc:
            raise BackendError(f"IBM Runtime transpilation failed ({type(exc).__name__})") from None

        self._circuit_cache[circuit_id] = transpiled
        self.last_summary = _transpiled_circuit_summary(
            circuit,
            transpiled,
            optimization_level=self._context.optimization_level,
        )
        self.last_preview = serialize_legacy_circuit_preview(transpiled, style="iqp")
        return transpiled

    def apply_layout_to_observables(self, observables: Any, circuit: Any, isa_circuit: Any) -> Any:
        if not _is_circuit_like(circuit):
            return observables
        layout = getattr(isa_circuit, "layout", None)
        if layout is None:
            return observables

        cache_key = (id(observables), id(isa_circuit))
        cached = self._observable_cache.get(cache_key)
        if cached is not None:
            return cached

        transformed = _apply_layout_to_observables(observables, layout)
        self._observable_cache[cache_key] = transformed
        return transformed

    def _pass_manager_for_context(self) -> Any:
        if self._pass_manager is not None:
            return self._pass_manager

        try:
            from qiskit.transpiler.preset_passmanagers import (
                generate_preset_pass_manager,
            )
        except Exception as exc:
            raise BackendError(
                "Qiskit transpiler preset pass managers are unavailable; "
                "cannot prepare IBM Runtime ISA circuits."
            ) from exc

        kwargs: dict[str, Any] = {
            "backend": self._backend,
            "optimization_level": self._context.optimization_level,
        }
        seed_transpiler = self._context.backend_options.get("seed_transpiler")
        if isinstance(seed_transpiler, int):
            kwargs["seed_transpiler"] = seed_transpiler

        self._pass_manager = generate_preset_pass_manager(**kwargs)
        return self._pass_manager


def _transpile_estimator_pub(pub: Any, *, transpiler: _RuntimeTranspiler) -> Any:
    if not isinstance(pub, tuple) or len(pub) < 2:
        return pub

    circuit = pub[0]
    observables = pub[1]
    isa_circuit = transpiler.transpile_circuit(circuit)
    isa_observables = transpiler.apply_layout_to_observables(
        observables,
        circuit,
        isa_circuit,
    )
    return (isa_circuit, isa_observables, *pub[2:])


def _transpile_sampler_pub(pub: Any, *, transpiler: _RuntimeTranspiler) -> Any:
    if isinstance(pub, tuple) and len(pub) >= 1:
        return (transpiler.transpile_circuit(pub[0]), *pub[1:])
    return transpiler.transpile_circuit(pub)


def _is_circuit_like(value: Any) -> bool:
    return hasattr(value, "num_qubits") and hasattr(value, "data")


def _apply_layout_to_observables(observables: Any, layout: Any) -> Any:
    apply_layout = getattr(observables, "apply_layout", None)
    if callable(apply_layout):
        return apply_layout(layout)

    if isinstance(observables, list):
        return [_apply_layout_to_observables(item, layout) for item in observables]
    if isinstance(observables, tuple):
        return tuple(_apply_layout_to_observables(item, layout) for item in observables)

    return observables


def _transpiled_circuit_summary(
    circuit: Any,
    transpiled: Any,
    *,
    optimization_level: int,
) -> dict[str, Any]:
    layout = getattr(transpiled, "layout", None)
    initial_layout = _layout_index_list(layout, "initial_index_layout")
    final_layout = _layout_index_list(layout, "final_index_layout")
    effective_layout = final_layout or initial_layout
    if not effective_layout:
        return {
            "optimization_level": optimization_level,
            "input_qubits": getattr(circuit, "num_qubits", None),
            "num_qubits": getattr(transpiled, "num_qubits", None),
            "transpiled_depth": _safe_int(getattr(transpiled, "depth", None)),
        }

    return {
        "optimization_level": optimization_level,
        "initial_layout": initial_layout,
        "final_layout": final_layout,
        "logical_to_physical": [
            {"logical": logical, "physical": physical}
            for logical, physical in enumerate(effective_layout)
        ],
        "used_physical_qubits": sorted(set(effective_layout)),
        "input_qubits": getattr(circuit, "num_qubits", None),
        "num_qubits": getattr(transpiled, "num_qubits", None),
        "transpiled_depth": _safe_int(getattr(transpiled, "depth", None)),
    }


def _transpile_circuit_summary(
    circuit: Any,
    *,
    backend: Any,
    optimization_level: int,
    seed_transpiler: Any,
) -> dict[str, Any]:
    try:
        from qiskit import transpile
    except Exception:
        return {}

    try:
        kwargs: dict[str, Any] = {
            "backend": backend,
            "optimization_level": optimization_level,
        }
        if isinstance(seed_transpiler, int):
            kwargs["seed_transpiler"] = seed_transpiler
        transpiled = transpile(circuit, **kwargs)
    except Exception:
        return {}
    return _transpiled_circuit_summary(
        circuit,
        transpiled,
        optimization_level=optimization_level,
    )


def _layout_index_list(layout: Any, method_name: str) -> list[int] | None:
    method = getattr(layout, method_name, None)
    if not callable(method):
        return None
    try:
        raw = method(filter_ancillas=True)
    except TypeError:
        raw = method()
    except Exception:
        return None
    if not isinstance(raw, list) or not all(isinstance(value, int) for value in raw):
        return None
    return [int(value) for value in raw]


def _safe_int(value: Any) -> int | None:
    if callable(value):
        try:
            value = value()
        except Exception:
            return None
    return int(value) if isinstance(value, int) else None
