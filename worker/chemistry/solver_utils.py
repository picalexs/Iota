"""Shared helpers for chemistry solver runtime configuration."""

from __future__ import annotations

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
    return max(low, min(int(value), high))
