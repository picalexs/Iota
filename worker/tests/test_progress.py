"""Unit tests for worker progress payload normalization."""

from worker.jobs.progress import (
    emit_fallback_completion_progress,
    estimated_total_iterations_for_progress,
    prepare_progress_payload,
    reconcile_reported_iterations,
)


def _progress_state() -> dict[str, object]:
    return {
        "count": 0,
        "phase_offset": 0,
        "last_raw_completed_iterations": None,
        "monotonic_completed_iterations": 0,
    }


def test_prepare_progress_payload_keeps_phase_iterations_monotonic() -> None:
    state = _progress_state()

    first = prepare_progress_payload(
        {"completed_iterations": 3, "iteration": 3},
        algorithm="sqd",
        progress_state=state,
    )
    second = prepare_progress_payload(
        {"completed_iterations": 1},
        algorithm="sqd",
        progress_state=state,
    )

    assert first["iteration"] == 3
    assert second["phase_iteration"] == 1
    assert second["iteration"] == 4
    assert state["monotonic_completed_iterations"] == 4


def test_estimated_total_includes_phase_offset_and_completed_work() -> None:
    state = {"phase_offset": 3}

    assert (
        estimated_total_iterations_for_progress(
            {"completed_iterations": 4, "total_iterations": 2},
            progress_total=3,
            progress_state=state,
        )
        == 5
    )


def test_reference_phase_does_not_advance_primary_iteration_axis() -> None:
    state = _progress_state()

    reference = prepare_progress_payload(
        {
            "progress_phase": "reference",
            "completed_iterations": 24,
            "iteration": 24,
        },
        algorithm="sqd",
        progress_state=state,
    )
    primary = prepare_progress_payload(
        {"completed_iterations": 1, "iteration": 1},
        algorithm="sqd",
        progress_state=state,
    )

    assert reference["phase_completed_iterations"] == 24
    assert reference["completed_iterations"] == 0
    assert primary["completed_iterations"] == 1
    assert state["monotonic_completed_iterations"] == 1


def test_reconcile_iterations_can_preserve_branch_matrix_counts() -> None:
    result = {"primary_iterations": 2, "iterations": 2}
    state = {"monotonic_completed_iterations": 4}

    reconcile_reported_iterations(
        result,
        progress_state=state,
        preserve_branch_matrix_elements=False,
    )
    assert result["iterations"] == 4

    branch_result = {"primary_iterations": 2, "iterations": 2}
    reconcile_reported_iterations(
        branch_result,
        progress_state=state,
        preserve_branch_matrix_elements=True,
    )
    assert branch_result["iterations"] == 2


def test_fallback_completion_progress_emits_only_without_progress() -> None:
    emitted: list[dict[str, object]] = []

    emit_fallback_completion_progress(
        {"primary_energy": -1.234567, "primary_iterations": 2},
        progress_state={"count": 0},
        algorithm="vqe",
        progress_callback=emitted.append,
    )
    emit_fallback_completion_progress(
        {"primary_energy": -1.0, "primary_iterations": 1},
        progress_state={"count": 1},
        algorithm="vqe",
        progress_callback=emitted.append,
    )

    assert emitted == [
        {
            "algorithm": "vqe",
            "stage": "completed",
            "step": "solve",
            "completed_iterations": 2,
            "energy": -1.234567,
        }
    ]
