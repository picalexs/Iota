"""Tests for the SQD recovery-loop boundary."""

from types import SimpleNamespace

import numpy as np

from worker.chemistry.algorithms.sqd import controller as sqd_controller
from worker.chemistry.algorithms.sqd import workflow as sqd_solver


def test_solver_keeps_recovery_loop_as_compatibility_alias() -> None:
    assert sqd_solver._run_sqd_recovery_loop is sqd_controller.run_sqd_recovery_loop


def test_recovery_loop_stops_on_non_finite_iteration_values() -> None:
    outcome = SimpleNamespace(
        batch_outcome=SimpleNamespace(energy_value=float("nan")),
        delta_energy=float("inf"),
        occupancy_delta=0.0,
        occupancy_vector=np.asarray([1.0, 0.0]),
        sampling=SimpleNamespace(
            selected_bits=np.zeros((1, 2), dtype=bool),
            raw_bitstring_matrix=np.zeros((1, 2), dtype=bool),
            postselection_weight=1.0,
        ),
        iter_elapsed=0.0,
    )
    events: list[dict[str, object]] = []
    state = sqd_solver._initial_sqd_run_state(
        SimpleNamespace(
            open_shell=False,
            symmetrize_spin=False,
            carryover_threshold=1e-4,
        )
    )

    result = sqd_controller.run_sqd_recovery_loop(
        backend=object(),
        deps=SimpleNamespace(),
        options=SimpleNamespace(max_iterations=3),
        rng=np.random.default_rng(0),
        progress_callback=None,
        initialize_state=lambda _options: state,
        execute_iteration=lambda **_kwargs: outcome,
        emit_progress=lambda **kwargs: events.append(kwargs),
        is_converged=lambda **_kwargs: True,
    )

    assert result.converged is False
    assert result.termination_reason == "invalid_numerics"
    assert events[-1]["termination_reason"] == "invalid_numerics"
