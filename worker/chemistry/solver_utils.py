"""Shared helpers for chemistry solver runtime configuration."""

from __future__ import annotations

import math
from typing import Any


def resolve_algorithm_config(config: dict[str, Any], algorithm: str) -> dict[str, Any]:
    """Resolve legacy and advanced algorithm options into one runtime config map."""
    advanced_config = config.get("advanced_config")
    if (
        isinstance(advanced_config, dict)
        and str(advanced_config.get("algorithm", "")).lower() == algorithm.lower()
    ):
        return advanced_config
    return config


def bounded_int(value: Any, *, default: int, low: int, high: int) -> int:
    """Normalize integer settings to rollout-safe bounds."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    if isinstance(value, float) and not math.isfinite(value):
        return default
    return max(low, min(int(value), high))


def positive_float(value: Any, *, default: float, name: str) -> float:
    """Resolve a finite positive float, using ``default`` only when absent."""
    if value is None:
        return default
    if isinstance(value, bool):
        raise ValueError(f"{name} must be finite and positive")
    try:
        resolved = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be finite and positive") from exc
    if not math.isfinite(resolved) or resolved <= 0.0:
        raise ValueError(f"{name} must be finite and positive")
    return resolved


def nonnegative_float(value: Any, *, default: float, name: str) -> float:
    """Resolve a finite non-negative float, using ``default`` only when absent."""
    if value is None:
        return default
    if isinstance(value, bool):
        raise ValueError(f"{name} must be finite and non-negative")
    try:
        resolved = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be finite and non-negative") from exc
    if not math.isfinite(resolved) or resolved < 0.0:
        raise ValueError(f"{name} must be finite and non-negative")
    return resolved
