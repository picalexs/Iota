"""Pure VQE configuration normalization for the algorithm package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

_MAX_FUNCTION_EVALUATIONS = 250_000
_DEFAULT_VQE_CONVERGENCE_THRESHOLD = 1e-8
_SUPPORTED_OPTIMIZER_POLICIES = {"explicit", "noise_aware_auto"}


@dataclass(frozen=True)
class VQEConfig:
    """Resolved VQE options used by the solver orchestration helpers."""

    max_iterations: int
    optimizer_name: str
    ansatz_name: str
    optimizer_options: object
    seed: object
    convergence_threshold: float
    max_function_evaluations: int | None
    reps: int
    optimizer_policy: str


def bounded_optional_positive_int(value: Any, *, high: int) -> int | None:
    """Return a positive integer capped at ``high`` or ``None`` for invalid input."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    parsed = int(value)
    if parsed <= 0:
        return None
    return max(1, min(parsed, high))


def positive_float_or_default(value: Any, *, default: float) -> float:
    """Return a positive float or the supplied default for invalid input."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    parsed = float(value)
    if parsed <= 0.0:
        return default
    return parsed


def resolve_parameter_bounds(
    config: Mapping[str, Any],
    *,
    num_parameters: int,
) -> list[tuple[float, float]] | None:
    """Resolve optimizer parameter bounds when provided."""
    raw_bounds = config.get("parameter_bounds")
    if raw_bounds is None:
        return None
    if not isinstance(raw_bounds, list):
        raise ValueError("VQE parameter_bounds must be a list of [lower, upper] pairs")
    if len(raw_bounds) != num_parameters:
        raise ValueError(
            f"VQE parameter_bounds must contain exactly {num_parameters} [lower, upper] pairs"
        )

    bounds: list[tuple[float, float]] = []
    for item in raw_bounds:
        if (
            not isinstance(item, (list, tuple))
            or len(item) != 2
            or not all(isinstance(value, (int, float)) for value in item)
        ):
            raise ValueError("VQE parameter_bounds entries must be numeric [lower, upper] pairs")
        lower = float(item[0])
        upper = float(item[1])
        if lower > upper:
            raise ValueError("VQE parameter_bounds lower values cannot exceed upper values")
        bounds.append((lower, upper))

    return bounds


def resolve_vqe_config(resolved: Mapping[str, Any]) -> VQEConfig:
    """Resolve user VQE options into bounded internal values."""
    max_iterations = int(resolved.get("max_iterations") or 500)
    max_iterations = max(1, min(max_iterations, 5000))
    optimizer_name = str(resolved.get("optimizer_name") or resolved.get("optimizer") or "COBYLA")
    optimizer_policy = str(resolved.get("optimizer_policy") or "explicit").strip().lower()
    if optimizer_policy not in _SUPPORTED_OPTIMIZER_POLICIES:
        supported = ", ".join(sorted(_SUPPORTED_OPTIMIZER_POLICIES))
        raise ValueError(
            f"Unsupported VQE optimizer_policy '{optimizer_policy}'. Supported: {supported}"
        )
    ansatz_name = str(resolved.get("ansatz_name") or resolved.get("ansatz") or "EfficientSU2")
    optimizer_options = resolved.get("optimizer_options")
    seed = resolved.get("seed", 42)
    convergence_threshold = positive_float_or_default(
        resolved.get("convergence_threshold"),
        default=_DEFAULT_VQE_CONVERGENCE_THRESHOLD,
    )
    max_function_evaluations = bounded_optional_positive_int(
        resolved.get("max_function_evaluations"),
        high=_MAX_FUNCTION_EVALUATIONS,
    )
    if max_function_evaluations is None and isinstance(optimizer_options, dict):
        max_function_evaluations = bounded_optional_positive_int(
            optimizer_options.get("maxfun"),
            high=_MAX_FUNCTION_EVALUATIONS,
        )
    reps = max(1, min(int(resolved.get("reps") or 2), 6))
    return VQEConfig(
        max_iterations=max_iterations,
        optimizer_name=optimizer_name,
        ansatz_name=ansatz_name,
        optimizer_options=optimizer_options,
        seed=seed,
        convergence_threshold=convergence_threshold,
        max_function_evaluations=max_function_evaluations,
        reps=reps,
        optimizer_policy=optimizer_policy,
    )


def select_vqe_optimizer_name(
    resolved: Mapping[str, Any],
    *,
    optimizer_policy: str,
    backend_target: str | None,
    noise_profile: Mapping[str, Any] | None,
) -> tuple[str, str]:
    """Select an optimizer without changing an explicitly declared protocol."""
    requested = resolved.get("optimizer_name") or resolved.get("optimizer")
    if requested is not None and str(requested).strip():
        return str(requested), "explicit"

    finite_shot_target = backend_target in {"aer_simulator", "ibm_runtime"}
    noisy_aer_target = backend_target == "aer_simulator" and noise_profile is not None
    if optimizer_policy == "noise_aware_auto" and (finite_shot_target or noisy_aer_target):
        return "SPSA", "noise_aware_auto"
    return "COBYLA", "default"


def select_vqe_execution_policy(
    *,
    backend_target: str | None,
    noise_profile: Mapping[str, Any] | None,
) -> tuple[str | None, str]:
    """Classify the resolved VQE path without changing optimizer settings."""
    normalized_target = str(backend_target or "").strip().lower()
    if normalized_target == "statevector":
        return "local_exact", "statevector_exact"
    if normalized_target == "aer_simulator":
        return (
            "sampled_aer",
            "aer_custom_noise" if noise_profile is not None else "aer_simulator",
        )
    if normalized_target == "ibm_runtime":
        return "hardware", "ibm_runtime"
    return None, "backend_target_unavailable"


__all__ = [
    "VQEConfig",
    "bounded_optional_positive_int",
    "positive_float_or_default",
    "resolve_parameter_bounds",
    "resolve_vqe_config",
    "select_vqe_execution_policy",
    "select_vqe_optimizer_name",
]
