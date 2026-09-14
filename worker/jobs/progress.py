"""Progress payload normalization for worker execution."""

from __future__ import annotations

from typing import Any

from worker.contracts import ProgressSink


def _coerce_int(value: object) -> int | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)
    return None


def prepare_progress_payload(
    payload: dict[str, Any],
    *,
    algorithm: str,
    progress_state: dict[str, Any],
) -> dict[str, Any]:
    """Normalize a solver progress event into monotonic run-level counters."""
    payload_to_store = dict(payload)
    payload_to_store.setdefault("algorithm", algorithm)
    payload_to_store.setdefault("stage", "progress")

    progress_state["count"] += 1
    raw_completed_iterations = _coerce_int(payload_to_store.get("completed_iterations"))
    if raw_completed_iterations is None:
        raw_completed_iterations = int(progress_state["count"])
    raw_iteration = _coerce_int(payload_to_store.get("iteration"))
    if raw_iteration is None:
        raw_iteration = raw_completed_iterations

    if payload_to_store.get("progress_phase") == "reference":
        # Nested VQE work belongs to SQD state preparation. Keep its local
        # counter in the event without advancing the SQD recovery axis.
        monotonic_completed = int(progress_state.get("monotonic_completed_iterations", 0))
        payload_to_store["phase_iteration"] = raw_iteration
        payload_to_store["phase_completed_iterations"] = raw_completed_iterations
        payload_to_store["iteration"] = monotonic_completed
        payload_to_store["completed_iterations"] = monotonic_completed
        return payload_to_store

    last_raw_completed = progress_state.get("last_raw_completed_iterations")
    monotonic_completed = int(progress_state.get("monotonic_completed_iterations", 0))
    if isinstance(last_raw_completed, int) and raw_completed_iterations < last_raw_completed:
        progress_state["phase_offset"] = monotonic_completed

    phase_offset = int(progress_state.get("phase_offset", 0))
    completed_iterations = max(phase_offset + raw_completed_iterations, monotonic_completed, 0)

    progress_state["last_raw_completed_iterations"] = raw_completed_iterations
    progress_state["monotonic_completed_iterations"] = completed_iterations
    payload_to_store["phase_iteration"] = raw_iteration
    payload_to_store["phase_completed_iterations"] = raw_completed_iterations
    payload_to_store["iteration"] = completed_iterations
    payload_to_store["completed_iterations"] = completed_iterations
    return payload_to_store


def estimated_total_iterations_for_progress(
    payload_to_store: dict[str, Any],
    *,
    progress_total: int,
    progress_state: dict[str, Any],
) -> int:
    completed_iterations = int(payload_to_store["completed_iterations"])
    event_total_iterations = payload_to_store.get("total_iterations")
    if isinstance(event_total_iterations, int):
        return max(
            progress_total,
            int(progress_state.get("phase_offset", 0)) + event_total_iterations,
            completed_iterations,
        )
    return max(progress_total, completed_iterations)


def reconcile_reported_iterations(
    result: dict[str, Any],
    *,
    progress_state: dict[str, Any],
    preserve_branch_matrix_elements: bool,
) -> None:
    monotonic_iterations = int(progress_state.get("monotonic_completed_iterations", 0))
    reported_iterations = int(result.get("primary_iterations", result.get("iterations", 0)) or 0)
    if monotonic_iterations > reported_iterations and not preserve_branch_matrix_elements:
        result["primary_iterations"] = monotonic_iterations
        result["iterations"] = monotonic_iterations


def emit_fallback_completion_progress(
    result: dict[str, Any],
    *,
    progress_state: dict[str, Any],
    algorithm: str,
    progress_callback: ProgressSink,
) -> None:
    """Emit one completion event when a solver produced no progress callbacks."""
    if progress_state["count"] != 0:
        return

    final_energy = result.get("primary_energy", result.get("energy"))
    fallback_payload: dict[str, Any] = {
        "algorithm": algorithm,
        "stage": "completed",
        "step": "solve",
        "completed_iterations": int(
            result.get("primary_iterations", result.get("iterations", 1)) or 1
        ),
    }
    if isinstance(final_energy, (int, float)):
        fallback_payload["energy"] = round(float(final_energy), 6)
    progress_callback(fallback_payload)
