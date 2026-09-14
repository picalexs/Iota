"""VQE initial-point selection helpers for the algorithm package."""

from __future__ import annotations

from typing import Any

import numpy as np


def _coerce_explicit_point(
    raw: Any,
    *,
    key: str,
    num_parameters: int,
) -> np.ndarray | None:
    """Return a validated explicit point or raise when the supplied shape is invalid."""
    if raw is None:
        return None
    if not isinstance(raw, (list, tuple)):
        raise ValueError(f"VQE {key} must be a numeric list of length {num_parameters}")
    if len(raw) != num_parameters:
        raise ValueError(f"VQE {key} must contain exactly {num_parameters} values")
    if not all(isinstance(value, (int, float)) for value in raw):
        raise ValueError(f"VQE {key} must contain only numeric values")
    return np.asarray(raw, dtype=float)


def _clip_to_parameter_bounds(
    point: np.ndarray,
    *,
    parameter_bounds: list[tuple[float, float]] | None,
) -> np.ndarray:
    """Project a candidate point into the configured parameter bounds."""
    if parameter_bounds is None:
        return np.asarray(point, dtype=float)
    lower = np.asarray([pair[0] for pair in parameter_bounds], dtype=float)
    upper = np.asarray([pair[1] for pair in parameter_bounds], dtype=float)
    return np.clip(np.asarray(point, dtype=float), lower, upper)


def _resolve_initial_point(
    config: dict[str, Any],
    *,
    num_parameters: int,
    seed: int | None = 42,
    parameter_bounds: list[tuple[float, float]] | None = None,
) -> np.ndarray:
    """Resolve the ansatz initial point from config or random uniform in [-pi, pi]."""
    for key in ("initial_parameters", "initial_point"):
        explicit = _coerce_explicit_point(
            config.get(key),
            key=key,
            num_parameters=num_parameters,
        )
        if explicit is not None:
            return _clip_to_parameter_bounds(explicit, parameter_bounds=parameter_bounds)

    rng = np.random.default_rng(seed if isinstance(seed, int) else 42)
    return _clip_to_parameter_bounds(
        rng.uniform(-np.pi, np.pi, size=num_parameters),
        parameter_bounds=parameter_bounds,
    )


def _resolve_explicit_initial_point(
    config: dict[str, Any],
    *,
    num_parameters: int,
) -> np.ndarray | None:
    """Resolve a caller-supplied initial point, if one is present and well-formed."""
    for key in ("initial_parameters", "initial_point"):
        explicit = _coerce_explicit_point(
            config.get(key),
            key=key,
            num_parameters=num_parameters,
        )
        if explicit is not None:
            return explicit
    return None


def _bounded_candidate_count(value: Any, *, default: int) -> int:
    """Normalize VQE candidate count to the rollout-safe search budget."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        count = default
    else:
        count = int(value)
    return max(1, min(count, 16))


def _build_initial_point_candidates(
    config: dict[str, Any],
    *,
    num_parameters: int,
    seed: int | None = 42,
    parameter_bounds: list[tuple[float, float]] | None = None,
) -> tuple[list[np.ndarray], dict[str, Any]]:
    """Build deterministic starting-point candidates for VQE.

    A single random point is fragile for shallow chemistry ansatzes. When the
    caller does not provide an explicit initial point, the default strategy
    evaluates the zero vector plus seeded random candidates and starts the
    optimizer from the lowest-energy candidate.
    """
    explicit = _resolve_explicit_initial_point(config, num_parameters=num_parameters)
    if explicit is not None:
        return [_clip_to_parameter_bounds(explicit, parameter_bounds=parameter_bounds)], {
            "initial_point_strategy": "provided",
            "initial_point_candidates": 1,
            "initial_point_selection_evaluations": 0,
        }

    strategy = str(config.get("initial_point_strategy") or "zero_plus_seeded_random").lower()
    rng = np.random.default_rng(seed if isinstance(seed, int) else 42)

    if strategy == "zero":
        return [
            _clip_to_parameter_bounds(
                np.zeros(num_parameters, dtype=float),
                parameter_bounds=parameter_bounds,
            )
        ], {
            "initial_point_strategy": "zero",
            "initial_point_candidates": 1,
            "initial_point_selection_evaluations": 0,
        }

    if strategy == "seeded_random":
        candidate_count = _bounded_candidate_count(
            config.get("initial_point_candidates"),
            default=1,
        )
        candidates = [
            _clip_to_parameter_bounds(
                rng.uniform(-np.pi, np.pi, size=num_parameters),
                parameter_bounds=parameter_bounds,
            )
            for _ in range(candidate_count)
        ]
        return candidates, {
            "initial_point_strategy": "seeded_random",
            "initial_point_candidates": candidate_count,
            "initial_point_selection_evaluations": candidate_count if candidate_count > 1 else 0,
        }

    candidate_count = _bounded_candidate_count(
        config.get("initial_point_candidates"),
        default=2,
    )
    candidates = [
        _clip_to_parameter_bounds(
            np.zeros(num_parameters, dtype=float),
            parameter_bounds=parameter_bounds,
        )
    ]
    candidates.extend(
        _clip_to_parameter_bounds(
            rng.uniform(-np.pi, np.pi, size=num_parameters),
            parameter_bounds=parameter_bounds,
        )
        for _ in range(candidate_count - 1)
    )
    return candidates, {
        "initial_point_strategy": "zero_plus_seeded_random",
        "initial_point_candidates": candidate_count,
        "initial_point_selection_evaluations": candidate_count if candidate_count > 1 else 0,
    }


def _select_initial_point(
    *,
    objective: Any,
    candidates: list[np.ndarray],
) -> tuple[np.ndarray, dict[str, Any]]:
    """Evaluate candidate starting points and return the lowest-energy one."""
    if len(candidates) == 1:
        return candidates[0], {}

    best_index = 0
    best_energy: float | None = None
    energies: list[float] = []
    for index, candidate in enumerate(candidates):
        energy = float(objective(candidate))
        energies.append(energy)
        if best_energy is None or energy < best_energy:
            best_energy = energy
            best_index = index

    return candidates[best_index], {
        "initial_point_best_index": best_index,
        "initial_point_best_energy": best_energy,
        "initial_point_candidate_energies": energies,
    }
