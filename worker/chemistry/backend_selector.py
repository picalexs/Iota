"""Quantum backend selection helpers."""

from __future__ import annotations

import math
from typing import Any

from worker.adapters.aer_adapter import AerAdapter
from worker.adapters.aer_noise import normalize_noise_profile
from worker.adapters.base import AdapterCapabilities, BackendAdapter, BackendExecutionContext
from worker.adapters.ibm_adapter import IBMAdapter
from worker.adapters.statevector_adapter import StatevectorAdapter
from worker.chemistry.aer_runtime import validate_aer_method_for_device
from worker.exceptions import BackendError

_AER_METHODS = {
    "automatic",
    "statevector",
    "density_matrix",
    "matrix_product_state",
    "stabilizer",
    "extended_stabilizer",
    "unitary",
    "superop",
}


_BACKEND_REGISTRY: dict[str, BackendAdapter] = {
    "statevector": StatevectorAdapter(),
    "aer_simulator": AerAdapter(),
    "ibm_runtime": IBMAdapter(),
}


def select_backend(backend_name: str) -> BackendAdapter:
    """Return backend adapter for the requested backend target."""
    adapter = _BACKEND_REGISTRY.get(backend_name)
    if adapter is None:
        raise BackendError(f"Unknown backend_target '{backend_name}'")
    if not adapter.capabilities.enabled:
        raise BackendError(f"backend_target '{backend_name}' is not enabled")
    return adapter


def get_backend_capabilities(backend_name: str) -> AdapterCapabilities:
    """Return backend capabilities regardless of enabled status."""
    adapter = _BACKEND_REGISTRY.get(backend_name)
    if adapter is None:
        raise BackendError(f"Unknown backend_target '{backend_name}'")
    return adapter.capabilities


def build_backend_execution_context(
    *,
    backend_target: str,
    backend_options: dict[str, Any] | None = None,
    noise_profile: dict[str, Any] | None = None,
    selection_policy: str = "requested",
) -> BackendExecutionContext:
    """Resolve run-level backend options into a stable execution context."""
    options = dict(backend_options or {})
    requested_shots = _optional_bounded_int(options.get("shots"), low=1, high=1_000_000)
    shots = _bounded_int(options.pop("shots", None), default=4096, low=1, high=1_000_000)
    requested_estimator_precision = _nonnegative_float(options.get("estimator_precision"))
    estimator_precision = _nonnegative_float(
        options.pop("estimator_precision", None),
        default=0.0,
    ) or 0.0
    if (
        backend_target == "aer_simulator"
        and noise_profile is not None
        and (
            "estimator_precision" not in (backend_options or {})
            or (backend_options or {}).get("estimator_precision") is None
        )
    ):
        # A noisy Aer estimator with precision=0 uses exact expectation values.
        # Derive a sampled precision from the run shot budget unless the caller
        # explicitly selected another precision. Ideal Aer keeps its exact path.
        estimator_precision = 1.0 / math.sqrt(float(shots))
        requested_estimator_precision = estimator_precision
    optimization_level = _bounded_int(
        options.pop("optimization_level", None),
        default=1,
        low=0,
        high=3,
    )
    simulator_method = str(
        options.pop("aer_method", options.pop("method", "automatic")) or "automatic"
    ).strip().lower()
    if simulator_method not in _AER_METHODS:
        raise BackendError(f"Unsupported Aer method '{simulator_method}'")
    device = options.get("device")
    if device is not None and (
        not isinstance(device, str) or device.upper() not in {"CPU", "GPU"}
    ):
        raise BackendError("Aer device must be 'CPU' or 'GPU'")
    validate_aer_method_for_device(device=device, method=simulator_method)
    selection_policy = str(options.pop("selection_policy", selection_policy) or selection_policy)
    for key in ("seed_simulator", "seed_transpiler"):
        seed_value = options.get(key)
        if isinstance(seed_value, bool) or not isinstance(seed_value, (int, float)):
            options.pop(key, None)
        else:
            options[key] = max(0, min(int(seed_value), 2**32 - 1))
    noise_profile = normalize_noise_profile(noise_profile)
    if noise_profile is not None and backend_target != "aer_simulator":
        raise BackendError(
            f"noise_profile is only supported for backend_target 'aer_simulator', not '{backend_target}'"
        )

    return BackendExecutionContext(
        backend_target=backend_target,
        backend_options=options,
        noise_profile=noise_profile,
        selection_policy=selection_policy,
        shots=shots,
        requested_shots=requested_shots,
        estimator_precision=estimator_precision,
        requested_estimator_precision=requested_estimator_precision,
        optimization_level=optimization_level,
        simulator_method=simulator_method,
    )


def _bounded_int(value: Any, *, default: int, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return max(low, min(int(value), high))


def _optional_bounded_int(value: Any, *, low: int, high: int) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(float(value)):
        return None
    return max(low, min(int(value), high))


def _nonnegative_float(value: Any, *, default: float | None = None) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    numeric = float(value)
    if numeric < 0.0 or not math.isfinite(numeric):
        return default
    return numeric
