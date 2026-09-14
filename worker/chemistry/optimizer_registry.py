"""Optimizer registry for worker VQE execution."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from shared.contracts.registry_metadata import (
    supported_optimizer_aliases as _shared_supported_optimizer_aliases,
)
from shared.contracts.registry_metadata import (
    supported_optimizer_metadata as _shared_supported_optimizer_metadata,
)


@dataclass(frozen=True)
class OptimizerConfig:
    """Normalized optimizer configuration consumed by VQE runtime."""

    name: str
    kind: str
    max_iterations: int
    max_function_evaluations: int | None = None
    scipy_method: str | None = None
    options: dict[str, Any] | None = None


@lru_cache(maxsize=1)
def _cached_supported_optimizer_aliases() -> dict[str, str]:
    """Build normalized aliases from the shared public catalog."""
    return _shared_supported_optimizer_aliases()


def _supported_optimizer_aliases() -> dict[str, str]:
    """Return a defensive copy of the cached normalized alias map."""
    return dict(_cached_supported_optimizer_aliases())


def _supported_optimizer_specs() -> dict[str, dict[str, Any]]:
    """Adapt public metadata into worker-only option sets."""
    return {
        canonical_id: {
            "kind": metadata["kind"],
            "scipy_method": metadata["scipy_method"],
            "allowed_options": set(metadata["allowed_options"]),
        }
        for canonical_id, metadata in _shared_supported_optimizer_metadata().items()
    }


def supported_optimizers() -> set[str]:
    """Return canonical optimizer names supported in the current rollout."""
    return set(_shared_supported_optimizer_metadata())


def supported_optimizer_metadata() -> dict[str, dict[str, Any]]:
    """Return public metadata without importing API code."""
    return _shared_supported_optimizer_metadata()


def build_optimizer(
    *,
    optimizer_name: str,
    max_iterations: int,
    minimum_iterations: int = 1,
    max_function_evaluations: int | None = None,
    optimizer_options: dict[str, Any] | None = None,
) -> OptimizerConfig:
    """Build a supported optimizer with safe option filtering.

    This registry returns normalized runtime configs for scipy-backed
    optimization and SPSA execution.
    """
    canonical_name = _supported_optimizer_aliases().get(optimizer_name.strip().upper())
    normalized = canonical_name or optimizer_name.strip().upper()
    optimizer_spec = _supported_optimizer_specs().get(normalized)
    if optimizer_spec is None:
        supported = ", ".join(sorted(supported_optimizers()))
        raise ValueError(f"Unsupported optimizer '{optimizer_name}'. Supported: {supported}")

    effective_max_iterations = max(int(max_iterations), int(minimum_iterations))
    effective_max_function_evaluations = (
        max(int(max_function_evaluations), 1) if max_function_evaluations is not None else None
    )
    supplied_options = dict(optimizer_options or {})
    filtered_options = {
        key: value
        for key, value in supplied_options.items()
        if key in optimizer_spec["allowed_options"]
    }

    if optimizer_spec["kind"] == "scipy":
        filtered_options["maxiter"] = effective_max_iterations
        if (
            effective_max_function_evaluations is not None
            and "maxfun" in optimizer_spec["allowed_options"]
        ):
            filtered_options["maxfun"] = effective_max_function_evaluations

    return OptimizerConfig(
        name=normalized,
        kind=str(optimizer_spec["kind"]),
        max_iterations=effective_max_iterations,
        max_function_evaluations=effective_max_function_evaluations,
        scipy_method=optimizer_spec.get("scipy_method"),
        options=filtered_options,
    )
