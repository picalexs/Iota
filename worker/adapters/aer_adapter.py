"""Qiskit Aer adapter implementation."""

from __future__ import annotations

import logging
import weakref
from collections.abc import Callable, Mapping
from typing import Any

from worker.adapters.base import (
    AdapterCapabilities,
    BackendAdapter,
    BackendExecutionContext,
    PrimitiveJobObserver,
    TrackingPrimitive,
)
from worker.adapters.aer_noise import AerNoiseConfiguration, resolve_aer_noise_profile
from worker.chemistry.matrix_element_circuits import (
    aer_simulator_options,
    apply_layout_to_observable,
    transpile_aer_circuit,
)
_DEFAULT_CONTEXT = BackendExecutionContext(backend_target="aer_simulator")
logger = logging.getLogger(__name__)


class AerAdapter(BackendAdapter):
    """Adapter for local Aer backend execution."""

    _caps = AdapterCapabilities(
        backend_target="aer_simulator",
        enabled=True,
        supports_noise_profile=True,
    )

    def __init__(self) -> None:
        self._job_ids: list[str] = []
        self._last_metadata: dict[str, Any] = {}
        self._cached_context_key: tuple[Any, ...] | None = None
        self._cached_backend_options: dict[str, Any] | None = None
        self._cached_noise_configuration: AerNoiseConfiguration | None = None
        self._cached_method: str | None = None
        self._transpile_cache: dict[
            tuple[int, tuple[Any, ...]], tuple[weakref.ReferenceType[Any], Any]
        ] = {}
        self._transpile_cache_hits = 0
        self._transpile_cache_misses = 0

    @property
    def capabilities(self) -> AdapterCapabilities:
        return self._caps

    def create_estimator(self, context: BackendExecutionContext | None = None) -> Any:
        from qiskit_aer.primitives import EstimatorV2

        resolved = context or _DEFAULT_CONTEXT
        self._job_ids = []
        self._last_metadata = {}
        primitive_options, metadata = self._build_primitive_options(
            resolved,
            include_estimator_precision=True,
        )
        primitive = EstimatorV2(options=primitive_options)
        noise_options = _noise_options_from_backend_options(primitive_options["backend_options"])
        self._last_metadata = metadata
        return TrackingPrimitive(
            primitive,
            self._job_ids,
            run_transform=self._build_estimator_run_transform(
                resolved,
                noise_options.get("noise_model"),
                noise_options,
            ),
            run_guard=resolved.primitive_run_guard,
            job_observer=self._build_job_observer(resolved),
        )

    def create_sampler(self, context: BackendExecutionContext | None = None) -> Any:
        from qiskit_aer.primitives import SamplerV2

        resolved = context or _DEFAULT_CONTEXT
        self._job_ids = []
        self._last_metadata = {}
        primitive_options, metadata = self._build_primitive_options(resolved)
        primitive = SamplerV2(
            default_shots=resolved.shots,
            seed=resolved.backend_options.get("seed_simulator"),
            options=primitive_options,
        )
        noise_options = _noise_options_from_backend_options(primitive_options["backend_options"])
        self._last_metadata = metadata
        return TrackingPrimitive(
            primitive,
            self._job_ids,
            run_transform=self._build_sampler_run_transform(
                resolved,
                noise_options.get("noise_model"),
                noise_options,
            ),
            run_guard=resolved.primitive_run_guard,
            job_observer=self._build_job_observer(resolved),
        )

    def _build_estimator_run_transform(
        self,
        context: BackendExecutionContext,
        noise_model: Any | None,
        noise_options: Mapping[str, Any] | None = None,
    ) -> Callable[[tuple[Any, ...], dict[str, Any]], tuple[tuple[Any, ...], dict[str, Any]]]:
        def transform(
            args: tuple[Any, ...],
            kwargs: dict[str, Any],
        ) -> tuple[tuple[Any, ...], dict[str, Any]]:
            pubs, replace = _extract_pubs(args, kwargs)
            if pubs is None:
                return args, kwargs

            transformed = []
            for pub in pubs:
                if not isinstance(pub, tuple) or len(pub) < 2:
                    transformed.append(pub)
                    continue
                circuit, observables = pub[0], pub[1]
                if not _is_circuit_like(circuit):
                    transformed.append(pub)
                    continue
                transpiled = self._transpile_cached(
                    circuit,
                    context,
                    noise_model,
                    noise_options=noise_options,
                )
                layout = getattr(transpiled, "layout", None)
                if layout is not None:
                    observables = _apply_layout_to_observables(observables, layout)
                transformed.append((transpiled, observables, *pub[2:]))
            return replace(transformed)

        return transform

    def _build_sampler_run_transform(
        self,
        context: BackendExecutionContext,
        noise_model: Any | None,
        noise_options: Mapping[str, Any] | None = None,
    ) -> Callable[[tuple[Any, ...], dict[str, Any]], tuple[tuple[Any, ...], dict[str, Any]]]:
        def transform(
            args: tuple[Any, ...],
            kwargs: dict[str, Any],
        ) -> tuple[tuple[Any, ...], dict[str, Any]]:
            pubs, replace = _extract_pubs(args, kwargs)
            if pubs is None:
                return args, kwargs
            transformed = [
                self._transpile_sampler_pub_cached(
                    pub,
                    context,
                    noise_model,
                    noise_options=noise_options,
                )
                for pub in pubs
            ]
            return replace(transformed)

        return transform

    def run_vqe(self, *, hamiltonian: object, config: dict) -> object:
        """Run VQE using Aer backend."""
        from worker.chemistry.algorithms.vqe.workflow import run_vqe

        return run_vqe(
            hamiltonian=hamiltonian,
            backend=self.create_estimator(_DEFAULT_CONTEXT),
            config=config,
        )

    def execution_metadata(self, context: BackendExecutionContext | None = None) -> dict[str, Any]:
        resolved = context or _DEFAULT_CONTEXT
        metadata = (
            dict(self._last_metadata)
            if self._cached_context_key == _context_cache_key(resolved)
            else {}
        )
        if not metadata:
            _, noise_configuration, method = self._resolve_execution_details(resolved)
            metadata = {
                "backend_target": self.capabilities.backend_target,
                "requested_target": resolved.backend_target,
                "actual_execution_target": "aer_simulator",
                "execution_mode": "aer_primitive",
                "actual_path_class": "aer_primitive",
                "resolved_backend_name": "aer_simulator",
                "selection_policy": resolved.selection_policy,
                "backend_primitives_used": True,
                "primitive_family": "qiskit_aer",
                "shots": resolved.shots,
                "requested_shots": _requested_shots(resolved),
                "effective_shots": resolved.shots,
                "requested_estimator_precision": _requested_estimator_precision(resolved),
                "effective_estimator_precision": resolved.estimator_precision,
                "measurement_mode": _measurement_mode(resolved.estimator_precision),
                "uncertainty_policy": "aer_estimator_default_precision",
                "simulator_method": method,
                "optimization_level": resolved.optimization_level,
                "noise_summary": noise_configuration.summary,
                "transpilation_summary": {
                    "optimization_level": resolved.optimization_level,
                    "preview": "Aer adapter transpiles primitive circuits to Aer instructions",
                    "cache": self._transpilation_cache_metadata(),
                    "simulator_options": aer_simulator_options(resolved),
                },
            }
            self._last_metadata = dict(metadata)
        if self._job_ids:
            metadata["job_ids"] = list(self._job_ids)
        transpilation_summary = metadata.get("transpilation_summary")
        if isinstance(transpilation_summary, dict):
            transpilation_summary["cache"] = self._transpilation_cache_metadata()
        return metadata

    def _build_job_observer(
        self,
        context: BackendExecutionContext,
    ) -> PrimitiveJobObserver:
        primitive_job_observer = context.primitive_job_observer

        def observe(job: Any, metadata: dict[str, Any]) -> Any | None:
            shots = metadata.get("shots")
            if isinstance(shots, (int, float)):
                self._last_metadata["shots"] = int(shots)
                self._last_metadata["effective_shots"] = int(shots)
            pub_count = metadata.get("pub_count")
            if isinstance(pub_count, (int, float)):
                self._last_metadata["pub_count"] = int(pub_count)

            if primitive_job_observer is None:
                return None
            return primitive_job_observer(
                job,
                {
                    **metadata,
                    "backend": "aer_simulator",
                    "backend_target": context.backend_target,
                    "selection_policy": context.selection_policy,
                },
            )

        return observe

    def _build_primitive_options(
        self,
        context: BackendExecutionContext,
        *,
        include_estimator_precision: bool = False,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        backend_options, noise_configuration, method = self._resolve_execution_details(
            context
        )
        backend_options.update(noise_configuration.simulator_options())

        primitive_options = {
            "backend_options": backend_options,
            "run_options": _run_options(context),
        }
        if include_estimator_precision:
            primitive_options["default_precision"] = context.estimator_precision
        metadata = {
            "backend_target": self.capabilities.backend_target,
            "requested_target": context.backend_target,
            "actual_execution_target": "aer_simulator",
            "execution_mode": "aer_primitive",
            "actual_path_class": "aer_primitive",
            "resolved_backend_name": "aer_simulator",
            "selection_policy": context.selection_policy,
            "backend_primitives_used": True,
            "primitive_family": "qiskit_aer",
            "shots": context.shots,
            "requested_shots": _requested_shots(context),
            "effective_shots": context.shots,
            "requested_estimator_precision": _requested_estimator_precision(context),
            "effective_estimator_precision": context.estimator_precision,
            "measurement_mode": _measurement_mode(context.estimator_precision),
            "uncertainty_policy": "aer_estimator_default_precision",
            "simulator_method": method,
            "optimization_level": context.optimization_level,
            "noise_summary": noise_configuration.summary,
            "transpilation_summary": {
                "optimization_level": context.optimization_level,
                "preview": "Aer adapter transpiles primitive circuits to Aer instructions",
                "cache": self._transpilation_cache_metadata(),
                "simulator_options": aer_simulator_options(context),
            },
        }
        return primitive_options, metadata

    def _transpile_cached(
        self,
        circuit: Any,
        context: BackendExecutionContext,
        noise_model: Any | None,
        *,
        noise_options: Mapping[str, Any] | None = None,
    ) -> Any:
        """Transpile each live circuit/context pair once per adapter.

        VQE submits one PUB per objective evaluation, but the parameterized
        ansatz circuit is reused. The weak reference prevents this bounded
        cache from retaining circuits after a primitive run ends.
        """
        context_key = _context_cache_key(context)
        cache_key = (id(circuit), context_key)
        cached = self._transpile_cache.get(cache_key)
        if cached is not None and cached[0]() is circuit:
            self._transpile_cache_hits += 1
            return cached[1]

        self._transpile_cache_misses += 1
        transpile_kwargs: dict[str, Any] = {
            "context": context,
            "noise_model": noise_model,
        }
        if noise_options:
            transpile_kwargs["noise_options"] = noise_options
        transpiled = transpile_aer_circuit(circuit, **transpile_kwargs)
        try:

            def remove_entry(
                circuit_ref: weakref.ReferenceType[Any],
                *,
                key: tuple[int, tuple[Any, ...]] = cache_key,
            ) -> None:
                entry = self._transpile_cache.get(key)
                if entry is not None and entry[0] is circuit_ref:
                    self._transpile_cache.pop(key, None)

            circuit_ref = weakref.ref(
                circuit,
                remove_entry,
            )
        except TypeError:
            # Circuit-like test doubles or third-party objects can be
            # non-weak-referenceable. Do not make caching a correctness gate.
            return transpiled
        self._transpile_cache[cache_key] = (circuit_ref, transpiled)
        if len(self._transpile_cache) > 256:
            self._transpile_cache.pop(next(iter(self._transpile_cache)))
        return transpiled

    def _transpile_sampler_pub_cached(
        self,
        pub: Any,
        context: BackendExecutionContext,
        noise_model: Any | None,
        *,
        noise_options: Mapping[str, Any] | None = None,
    ) -> Any:
        """Transpile a sampler PUB through the same bounded cache."""
        if isinstance(pub, tuple):
            if not pub or not _is_circuit_like(pub[0]):
                return pub
            return (
                self._transpile_cached(
                    pub[0],
                    context,
                    noise_model,
                    noise_options=noise_options,
                ),
                *pub[1:],
            )
        if not _is_circuit_like(pub):
            return pub
        return self._transpile_cached(
            pub,
            context,
            noise_model,
            noise_options=noise_options,
        )

    def _transpilation_cache_metadata(self) -> dict[str, Any]:
        return {
            "enabled": True,
            "entries": len(self._transpile_cache),
            "hits": self._transpile_cache_hits,
            "misses": self._transpile_cache_misses,
            "max_entries": 256,
        }

    def _resolve_execution_details(
        self,
        context: BackendExecutionContext,
    ) -> tuple[dict[str, Any], AerNoiseConfiguration, str]:
        cache_key = _context_cache_key(context)
        if self._cached_context_key == cache_key:
            return (
                dict(self._cached_backend_options or {}),
                self._cached_noise_configuration
                or AerNoiseConfiguration(noise_model=None, summary={"enabled": False}),
                str(self._cached_method or "automatic"),
            )

        backend_options = dict(context.backend_options)
        backend_options.pop("shots", None)
        backend_options.pop("estimator_precision", None)
        backend_options.pop("optimization_level", None)
        backend_options.pop("aer_pub_chunk_size", None)
        backend_options.pop("backend_name", None)
        backend_options.pop("seed_simulator", None)
        backend_options.pop("seed_transpiler", None)
        backend_options.pop("selection_policy", None)
        backend_options.pop("credential_profile_id", None)
        backend_options.pop("token", None)
        backend_options.pop("instance", None)
        backend_options.pop("channel", None)
        backend_options.pop("url", None)
        method = str(backend_options.pop("method", context.simulator_method) or "automatic")
        backend_options["method"] = method
        noise_configuration = resolve_aer_noise_profile(
            context.noise_profile,
            context.backend_options,
        )
        self._cached_context_key = cache_key
        self._cached_backend_options = dict(backend_options)
        self._cached_noise_configuration = noise_configuration
        self._cached_method = method
        return backend_options, noise_configuration, method


def _extract_pubs(
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> tuple[Any | None, Callable[[list[Any]], tuple[tuple[Any, ...], dict[str, Any]]]]:
    """Extract primitive PUBs and preserve the caller's argument style."""
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


def _apply_layout_to_observables(observables: Any, layout: Any) -> Any:
    """Apply a transpiler layout to estimator observables in their original shape."""
    if isinstance(observables, list):
        return [_apply_layout_to_observables(item, layout) for item in observables]
    if isinstance(observables, tuple):
        return tuple(_apply_layout_to_observables(item, layout) for item in observables)
    return apply_layout_to_observable(observables, layout)


def _is_circuit_like(value: Any) -> bool:
    """Return whether a primitive PUB value can be passed to Qiskit transpile."""
    return hasattr(value, "num_qubits") and hasattr(value, "data")


def _transpile_sampler_pub(pub: Any, context: BackendExecutionContext, noise_model: Any) -> Any:
    """Transpile a sampler PUB when it contains a circuit."""
    if isinstance(pub, tuple):
        if not pub or not _is_circuit_like(pub[0]):
            return pub
        return (
            transpile_aer_circuit(pub[0], context=context, noise_model=noise_model),
            *pub[1:],
        )
    if not _is_circuit_like(pub):
        return pub
    return transpile_aer_circuit(pub, context=context, noise_model=noise_model)


def _context_cache_key(context: BackendExecutionContext) -> tuple[Any, ...]:
    return (
        context.backend_target,
        context.selection_policy,
        int(context.shots),
        context.requested_shots,
        float(context.estimator_precision),
        context.requested_estimator_precision,
        int(context.optimization_level),
        str(context.simulator_method),
        _freeze_cache_value(context.backend_options),
        _freeze_cache_value(context.noise_profile),
    )


def _noise_options_from_backend_options(options: Mapping[str, Any]) -> dict[str, Any]:
    """Extract noise-model options for the circuit transpilation boundary."""
    return {
        key: options[key]
        for key in ("noise_model", "basis_gates", "coupling_map")
        if key in options
    }


def _requested_shots(context: BackendExecutionContext) -> int:
    return context.requested_shots if context.requested_shots is not None else context.shots


def _requested_estimator_precision(context: BackendExecutionContext) -> float:
    return (
        context.requested_estimator_precision
        if context.requested_estimator_precision is not None
        else context.estimator_precision
    )


def _measurement_mode(precision: float) -> str:
    return "exact" if precision == 0.0 else "precision_sampled"


def _run_options(context: BackendExecutionContext) -> dict[str, Any]:
    run_options: dict[str, Any] = {"shots": context.shots}
    seed_simulator = context.backend_options.get("seed_simulator")
    if isinstance(seed_simulator, int) and not isinstance(seed_simulator, bool):
        run_options["seed_simulator"] = seed_simulator
    return run_options


def _freeze_cache_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return tuple(
            sorted((str(key), _freeze_cache_value(nested)) for key, nested in value.items())
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_cache_value(item) for item in value)
    if isinstance(value, set):
        return tuple(sorted(_freeze_cache_value(item) for item in value))
    return value
