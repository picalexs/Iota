"""Tests for the SQD iteration-execution boundary."""

from worker.chemistry.algorithms.sqd import iteration as sqd_iteration
from worker.chemistry.algorithms.sqd import workflow as sqd_solver


def test_solver_keeps_iteration_helpers_as_compatibility_aliases() -> None:
    assert sqd_solver._SQDIterationOutcome is sqd_iteration.SQDIterationOutcome
    assert sqd_solver._update_best_observed_state is sqd_iteration.update_best_observed_state
