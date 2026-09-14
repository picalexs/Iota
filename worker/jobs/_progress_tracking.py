"""Runtime progress estimation and persistence helpers."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from worker.chemistry.types import HamiltonianBundle
from worker.persistence.run_repository import SqlRunRepository

_EMA_ALPHA = 0.3
_ETA_WARMUP_SAMPLES = 4
_ETA_WARMUP_PROGRESS_FRACTION = 0.25
_ETA_WARMUP_ELAPSED_SECONDS = 15.0
_MAX_EMA_TRUST = 0.9


def _compute_elapsed_seconds(progress_state: dict[str, Any]) -> float | None:
    """Return elapsed wall-clock seconds since the run started, or None."""
    start = progress_state.get("start_time")
    if start is None:
        return None
    return time.monotonic() - float(start)


def _seeded_baseline_cost(seed_seconds_per_iteration: float | None) -> float | None:
    if not isinstance(seed_seconds_per_iteration, (int, float)) or seed_seconds_per_iteration <= 0:
        return None
    return float(seed_seconds_per_iteration)


def _seeded_baseline_confidence(seed_confidence: float | None) -> float | None:
    if not isinstance(seed_confidence, (int, float)):
        return None
    return min(0.85, max(float(seed_confidence), 0.0))


def _progress_counts(total_iterations: int, completed_iterations: int) -> tuple[int, int]:
    completed = max(completed_iterations, 0)
    adjusted_total_iterations = max(total_iterations, completed)
    return completed, adjusted_total_iterations


def _update_ema_cost(
    *,
    elapsed_seconds: float | None,
    completed: int,
    ema_state: dict[str, Any] | None,
) -> tuple[float | None, int]:
    ema_cost = ema_state.get("ema_cost") if ema_state is not None else None
    sample_count = int(ema_state.get("eta_sample_count", 0)) if ema_state is not None else 0

    if elapsed_seconds is None or completed <= 0 or ema_state is None:
        return ema_cost, sample_count

    instant_cost: float | None = None
    previous_elapsed = ema_state.get("last_eta_elapsed_seconds")
    previous_completed = ema_state.get("last_eta_completed_iterations")
    if (
        isinstance(previous_elapsed, (int, float))
        and isinstance(previous_completed, int)
        and completed > previous_completed
        and elapsed_seconds > float(previous_elapsed)
    ):
        instant_cost = (elapsed_seconds - float(previous_elapsed)) / (
            completed - previous_completed
        )
    elif previous_completed is None and elapsed_seconds > 0:
        instant_cost = elapsed_seconds / completed

    ema_state["last_eta_elapsed_seconds"] = elapsed_seconds
    ema_state["last_eta_completed_iterations"] = completed
    if instant_cost is None or instant_cost <= 0:
        return ema_cost, sample_count

    previous_ema = ema_state.get("ema_cost")
    new_ema = (
        instant_cost
        if previous_ema is None
        else _EMA_ALPHA * instant_cost + (1.0 - _EMA_ALPHA) * float(previous_ema)
    )
    ema_state["ema_cost"] = new_ema
    sample_count += 1
    ema_state["eta_sample_count"] = sample_count
    return new_ema, sample_count


def _trust_metrics(
    *,
    sample_count: int,
    progress_fraction: float,
    elapsed_seconds: float | None,
) -> tuple[float, float, float]:
    sample_trust = min(sample_count / _ETA_WARMUP_SAMPLES, 1.0)
    progress_trust = min(progress_fraction / _ETA_WARMUP_PROGRESS_FRACTION, 1.0)
    elapsed_trust = (
        min(float(elapsed_seconds) / _ETA_WARMUP_ELAPSED_SECONDS, 1.0)
        if elapsed_seconds is not None and elapsed_seconds > 0
        else 0.0
    )
    return sample_trust, progress_trust, elapsed_trust


def _effective_cost(
    *,
    ema_cost: float | None,
    baseline_cost: float | None,
    sample_trust: float,
    progress_trust: float,
    elapsed_trust: float,
) -> float | None:
    if ema_cost is not None:
        ema_trust = min(
            _MAX_EMA_TRUST,
            0.6 * sample_trust + 0.25 * progress_trust + 0.15 * elapsed_trust,
        )
        if baseline_cost is not None:
            return (1.0 - ema_trust) * baseline_cost + ema_trust * float(ema_cost)
        return float(ema_cost)
    return baseline_cost


def _estimate_confidence(
    *,
    ema_cost: float | None,
    baseline_confidence: float | None,
    effective_cost: float | None,
    sample_trust: float,
    progress_trust: float,
    elapsed_trust: float,
) -> float | None:
    if ema_cost is not None:
        return min(
            0.92,
            max(
                baseline_confidence or 0.0,
                0.35 + 0.30 * sample_trust + 0.20 * progress_trust + 0.15 * elapsed_trust,
            ),
        )
    if baseline_confidence is not None and effective_cost is not None:
        return baseline_confidence
    return None


def _estimate_runtime_seconds(
    *,
    effective_cost: float | None,
    elapsed_seconds: float | None,
    completed: int,
    adjusted_total_iterations: int,
    remaining_iterations: int,
) -> tuple[float | None, float | None]:
    if effective_cost is None:
        return None, None
    if elapsed_seconds is not None and completed > 0:
        return (
            float(elapsed_seconds) + float(remaining_iterations) * effective_cost,
            float(remaining_iterations) * effective_cost,
        )
    return (
        float(adjusted_total_iterations) * effective_cost,
        float(remaining_iterations) * effective_cost,
    )


def _build_telemetry_estimate(
    *,
    algorithm: str,
    total_iterations: int,
    completed_iterations: int,
    hamiltonian_bundle: HamiltonianBundle | None = None,
    backend_target: str = "statevector",
    elapsed_seconds: float | None = None,
    ema_state: dict[str, Any] | None = None,
    seed_seconds_per_iteration: float | None = None,
    seed_confidence: float | None = None,
    workload_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an estimate payload from runtime telemetry.

    Uses live EMA of observed wall-clock time when available, optionally seeded
    by a trusted history-based estimate from the runs table.
    """
    completed, adjusted_total_iterations = _progress_counts(total_iterations, completed_iterations)
    remaining_iterations = max(adjusted_total_iterations - completed, 0)
    _ = hamiltonian_bundle, backend_target
    baseline_cost = _seeded_baseline_cost(seed_seconds_per_iteration)
    baseline_confidence = _seeded_baseline_confidence(seed_confidence)
    ema_cost, sample_count = _update_ema_cost(
        elapsed_seconds=elapsed_seconds,
        completed=completed,
        ema_state=ema_state,
    )
    progress_fraction = completed / adjusted_total_iterations if adjusted_total_iterations else 0.0
    sample_trust, progress_trust, elapsed_trust = _trust_metrics(
        sample_count=sample_count,
        progress_fraction=progress_fraction,
        elapsed_seconds=elapsed_seconds,
    )
    effective_cost = _effective_cost(
        ema_cost=ema_cost,
        baseline_cost=baseline_cost,
        sample_trust=sample_trust,
        progress_trust=progress_trust,
        elapsed_trust=elapsed_trust,
    )
    confidence = _estimate_confidence(
        ema_cost=ema_cost,
        baseline_confidence=baseline_confidence,
        effective_cost=effective_cost,
        sample_trust=sample_trust,
        progress_trust=progress_trust,
        elapsed_trust=elapsed_trust,
    )
    estimated_total_seconds, estimated_remaining_seconds = _estimate_runtime_seconds(
        effective_cost=effective_cost,
        elapsed_seconds=elapsed_seconds,
        completed=completed,
        adjusted_total_iterations=adjusted_total_iterations,
        remaining_iterations=remaining_iterations,
    )

    estimate = {
        "source": "telemetry",
        "algorithm": algorithm,
        "estimated_total_iterations": adjusted_total_iterations,
        "estimated_remaining_iterations": remaining_iterations,
        "estimated_total_seconds": estimated_total_seconds,
        "estimated_remaining_seconds": estimated_remaining_seconds,
        "confidence": confidence,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    if effective_cost is not None:
        estimate["estimated_seconds_per_iteration"] = effective_cost
    if workload_fields:
        estimate.update(workload_fields)
    return estimate


def _persist_latest_estimate(session: Any, run_id: str, estimate: dict[str, Any]) -> None:
    """Persist the latest estimate snapshot on the runs table."""
    SqlRunRepository(session).save_progress(run_id, estimate)
