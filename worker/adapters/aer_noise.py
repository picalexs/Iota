"""Explicit Aer noise-profile resolution and provenance."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from worker.exceptions import NoiseConfigurationError

BackendLoader = Callable[[str, Mapping[str, Any]], Any]

_SIMULATOR_REFERENCE_NAMES = {
    "aer_simulator",
    "aer_simulator_statevector",
    "statevector",
}
_NOISE_SOURCES = {"backend_derived", "custom_preset"}
_CUSTOM_PRESETS = {"depolarizing_cx", "thermal_relaxation", "readout_bias"}
_CUSTOM_PARAMETER_KEYS = {
    "strength",
    "p01",
    "p10",
    "t1_us",
    "t2_us",
    "gate_time_us",
}
_AER_UNSUPPORTED_BASIS_GATES = frozenset({"delay"})


@dataclass(frozen=True, slots=True)
class AerNoiseConfiguration:
    """Resolved Aer noise model plus the simulator topology it requires."""

    noise_model: Any | None
    summary: dict[str, Any]
    basis_gates: tuple[str, ...] = ()
    coupling_map: tuple[tuple[int, int], ...] = ()

    def simulator_options(self) -> dict[str, Any]:
        """Return non-secret options for an AerSimulator constructor."""
        options: dict[str, Any] = {}
        if self.noise_model is not None:
            options["noise_model"] = self.noise_model
        if self.basis_gates:
            options["basis_gates"] = list(self.basis_gates)
        if self.coupling_map:
            options["coupling_map"] = [list(edge) for edge in self.coupling_map]
        return options


def normalize_noise_profile(profile: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Validate and copy a persisted noise profile at the worker boundary."""
    if profile is None:
        return None
    if not isinstance(profile, Mapping):
        raise NoiseConfigurationError("noise_profile must be an object")

    source = _required_string(profile, "source").lower()
    if source not in _NOISE_SOURCES:
        raise NoiseConfigurationError(
            f"Unsupported Aer noise_profile source '{source}'"
        )

    if source == "backend_derived":
        _reject_unexpected_keys(
            profile,
            {"source", "reference_backend", "temperature_mk"},
        )
        reference_backend = _required_string(profile, "reference_backend")
        if reference_backend.lower() in _SIMULATOR_REFERENCE_NAMES:
            raise NoiseConfigurationError(
                "backend_derived noise requires an IBM backend reference, not a simulator"
            )
        temperature_mk = _optional_finite_float(profile.get("temperature_mk"))
        if temperature_mk is not None and temperature_mk < 0:
            raise NoiseConfigurationError("temperature_mk must be non-negative")
        return {
            "source": source,
            "reference_backend": reference_backend,
            "temperature_mk": temperature_mk,
        }

    preset = _required_string(profile, "preset").lower()
    if preset not in _CUSTOM_PRESETS:
        raise NoiseConfigurationError(f"Unsupported custom Aer noise preset '{preset}'")
    _reject_unexpected_keys(profile, {"source", "preset", *_CUSTOM_PARAMETER_KEYS})
    provided_parameters = {
        key for key in _CUSTOM_PARAMETER_KEYS if profile.get(key) is not None
    }

    if preset == "depolarizing_cx":
        _require_parameter_set(provided_parameters, {"strength"}, preset)
        return {
            "source": source,
            "preset": preset,
            "strength": _required_unit_interval(profile, "strength"),
        }
    if preset == "readout_bias":
        _require_parameter_set(provided_parameters, {"p01", "p10"}, preset)
        return {
            "source": source,
            "preset": preset,
            "p01": _required_unit_interval(profile, "p01"),
            "p10": _required_unit_interval(profile, "p10"),
        }

    _require_parameter_set(
        provided_parameters,
        {"t1_us", "t2_us", "gate_time_us"},
        preset,
    )
    t1_us = _required_positive_float(profile, "t1_us")
    t2_us = _required_positive_float(profile, "t2_us")
    gate_time_us = _required_positive_float(profile, "gate_time_us")
    if t2_us > 2.0 * t1_us:
        raise NoiseConfigurationError("t2_us must not exceed 2 * t1_us")
    return {
        "source": source,
        "preset": preset,
        "t1_us": t1_us,
        "t2_us": t2_us,
        "gate_time_us": gate_time_us,
    }


def resolve_aer_noise_profile(
    profile: Mapping[str, Any] | None,
    backend_options: Mapping[str, Any] | None = None,
    *,
    backend_loader: BackendLoader | None = None,
) -> AerNoiseConfiguration:
    """Build a validated Aer noise model and its reproducibility metadata."""
    normalized = normalize_noise_profile(profile)
    if normalized is None:
        return AerNoiseConfiguration(noise_model=None, summary={"enabled": False})

    if normalized["source"] == "backend_derived":
        return _resolve_backend_derived_noise(
            normalized,
            backend_options or {},
            backend_loader=backend_loader or _load_runtime_backend,
        )
    return _resolve_custom_noise(normalized)


def _resolve_backend_derived_noise(
    profile: dict[str, Any],
    backend_options: Mapping[str, Any],
    *,
    backend_loader: BackendLoader,
) -> AerNoiseConfiguration:
    from qiskit_aer.noise import NoiseModel

    reference_backend = str(profile["reference_backend"])
    try:
        backend = backend_loader(reference_backend, backend_options)
        temperature_mk = profile.get("temperature_mk")
        noise_model = NoiseModel.from_backend(
            backend,
            gate_error=True,
            readout_error=True,
            thermal_relaxation=True,
            temperature=temperature_mk if temperature_mk is not None else 0.0,
        )
    except NoiseConfigurationError:
        raise
    except Exception as exc:
        raise NoiseConfigurationError(
            f"Unable to build backend-derived Aer noise for '{reference_backend}' "
            f"({type(exc).__name__})"
        ) from exc

    resolved_backend = _backend_name(backend) or reference_backend
    basis_gates = _basis_gates(noise_model)
    coupling_map = _coupling_map(backend)
    summary: dict[str, Any] = {
        "enabled": True,
        "source": "backend_derived",
        "requested_reference_backend": reference_backend,
        "resolved_reference_backend": resolved_backend,
        "calibration_source": "IBM Runtime backend properties",
        "temperature_mk": profile.get("temperature_mk") or 0.0,
        "backend_version": _backend_version(backend),
        "basis_gates": list(basis_gates),
        "coupling_map": [list(edge) for edge in coupling_map],
    }
    summary["model_fingerprint_sha256"] = _model_fingerprint(
        noise_model,
        summary,
    )
    return AerNoiseConfiguration(
        noise_model=noise_model,
        summary=summary,
        basis_gates=basis_gates,
        coupling_map=coupling_map,
    )


def _resolve_custom_noise(profile: dict[str, Any]) -> AerNoiseConfiguration:
    from qiskit_aer.noise import NoiseModel

    preset = profile["preset"]
    noise_model = NoiseModel()
    if preset == "depolarizing_cx":
        from qiskit_aer.noise import depolarizing_error

        strength = float(profile["strength"])
        if strength > 0:
            noise_model.add_all_qubit_quantum_error(
                depolarizing_error(strength, 2),
                ["cx"],
            )
    elif preset == "readout_bias":
        from qiskit_aer.noise import ReadoutError

        p01 = float(profile["p01"])
        p10 = float(profile["p10"])
        if p01 > 0 or p10 > 0:
            noise_model.add_all_qubit_readout_error(
                ReadoutError([[1.0 - p01, p01], [p10, 1.0 - p10]])
            )
    elif preset == "thermal_relaxation":
        from qiskit_aer.noise import thermal_relaxation_error

        one_qubit_error = thermal_relaxation_error(
            float(profile["t1_us"]),
            float(profile["t2_us"]),
            float(profile["gate_time_us"]),
        )
        noise_model.add_all_qubit_quantum_error(
            one_qubit_error,
            ["id", "sx", "x"],
        )
        noise_model.add_all_qubit_quantum_error(one_qubit_error.tensor(one_qubit_error), ["cx"])

    basis_gates = _basis_gates(noise_model)
    enabled = _noise_model_has_errors(noise_model)
    summary = {
        "enabled": enabled,
        "source": "custom_preset",
        **profile,
        "units": "microseconds" if preset == "thermal_relaxation" else None,
        "calibration_source": "synthetic Aer preset",
        "basis_gates": list(basis_gates),
    }
    summary["model_fingerprint_sha256"] = _model_fingerprint(noise_model, summary)
    return AerNoiseConfiguration(
        noise_model=noise_model if enabled else None,
        summary=summary,
        basis_gates=basis_gates,
    )


def _load_runtime_backend(backend_name: str, backend_options: Mapping[str, Any]) -> Any:
    from qiskit_ibm_runtime import QiskitRuntimeService

    token = backend_options.get("token")
    instance = backend_options.get("instance")
    if not token or not instance:
        raise NoiseConfigurationError(
            f"Backend-derived Aer noise requires credentials for '{backend_name}'"
        )
    channel = backend_options.get("channel") or "ibm_quantum_platform"
    try:
        service = QiskitRuntimeService(channel=channel, token=token, instance=instance)
        return service.backend(backend_name)
    except Exception as exc:
        raise NoiseConfigurationError(
            f"Unable to load IBM backend '{backend_name}' ({type(exc).__name__})"
        ) from exc


def _required_string(profile: Mapping[str, Any], key: str) -> str:
    value = profile.get(key)
    if not isinstance(value, str) or not value.strip():
        raise NoiseConfigurationError(f"noise_profile.{key} is required")
    return value.strip()


def _optional_finite_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise NoiseConfigurationError("noise profile numeric values must be finite numbers")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise NoiseConfigurationError("noise profile numeric values must be finite numbers")
    return numeric


def _required_unit_interval(profile: Mapping[str, Any], key: str) -> float:
    value = _optional_finite_float(profile.get(key))
    if value is None or not 0.0 <= value <= 1.0:
        raise NoiseConfigurationError(f"noise_profile.{key} must be between 0 and 1")
    return value


def _required_positive_float(profile: Mapping[str, Any], key: str) -> float:
    value = _optional_finite_float(profile.get(key))
    if value is None or value <= 0:
        raise NoiseConfigurationError(f"noise_profile.{key} must be greater than 0")
    return value


def _reject_unexpected_keys(profile: Mapping[str, Any], allowed: set[str]) -> None:
    unexpected = {str(key) for key in profile if key not in allowed}
    if unexpected:
        names = ", ".join(sorted(unexpected))
        raise NoiseConfigurationError(f"Unsupported noise_profile fields: {names}")


def _require_parameter_set(
    provided: set[str],
    required: set[str],
    preset: str,
) -> None:
    if provided != required:
        expected = ", ".join(sorted(required))
        raise NoiseConfigurationError(f"preset '{preset}' requires exactly: {expected}")


def _noise_model_has_errors(noise_model: Any) -> bool:
    to_dict = getattr(noise_model, "to_dict", None)
    if not callable(to_dict):
        return bool(_basis_gates(noise_model))
    model_dict = to_dict()
    return bool(model_dict.get("errors")) if isinstance(model_dict, dict) else False


def _basis_gates(noise_model: Any) -> tuple[str, ...]:
    values = getattr(noise_model, "basis_gates", ())
    if not isinstance(values, (list, tuple, set)):
        return ()
    return tuple(
        gate
        for gate in (str(value) for value in values)
        if gate not in _AER_UNSUPPORTED_BASIS_GATES
    )


def _coupling_map(backend: Any) -> tuple[tuple[int, int], ...]:
    value = getattr(backend, "coupling_map", None)
    if callable(value):
        value = value()
    if value is None:
        configuration = getattr(backend, "configuration", None)
        if callable(configuration):
            try:
                value = getattr(configuration(), "coupling_map", None)
            except (AttributeError, TypeError, ValueError):
                value = None
    if hasattr(value, "get_edges") and callable(value.get_edges):
        value = value.get_edges()
    if not isinstance(value, (list, tuple)):
        return ()
    edges: list[tuple[int, int]] = []
    for edge in value:
        if (
            isinstance(edge, (list, tuple))
            and len(edge) == 2
            and all(isinstance(item, int) and not isinstance(item, bool) for item in edge)
        ):
            edges.append((int(edge[0]), int(edge[1])))
    return tuple(edges)


def _backend_name(backend: Any) -> str | None:
    value = getattr(backend, "name", None)
    if callable(value):
        value = value()
    return value.strip() if isinstance(value, str) and value.strip() else None


def _backend_version(backend: Any) -> str | None:
    for key in ("backend_version", "version"):
        value = getattr(backend, key, None)
        if callable(value):
            value = value()
        if value is not None:
            return str(value)
    return None


def _model_fingerprint(noise_model: Any, summary: Mapping[str, Any]) -> str:
    model_dict = noise_model.to_dict() if callable(getattr(noise_model, "to_dict", None)) else {}
    payload = json.dumps(
        {"model": model_dict, "summary": dict(summary)},
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


__all__ = [
    "AerNoiseConfiguration",
    "normalize_noise_profile",
    "resolve_aer_noise_profile",
]
