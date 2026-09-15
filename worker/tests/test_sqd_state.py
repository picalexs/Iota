"""Tests for the SQD state and setup boundary."""

from worker.chemistry.algorithms.sqd import state as sqd_state
from worker.chemistry.algorithms.sqd import workflow as sqd_solver


def test_solver_keeps_state_helpers_as_compatibility_aliases() -> None:
    assert sqd_solver._SQDRunState is sqd_state.SQDRunState
    assert sqd_solver._import_sqd_dependencies is sqd_state.import_sqd_dependencies
    assert sqd_solver._initial_sqd_run_state is sqd_state.initial_sqd_run_state
    assert sqd_solver._log_sqd_setup is sqd_state.log_sqd_setup
