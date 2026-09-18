"""Tests for the SQD recovery-loop boundary."""

from worker.chemistry.algorithms.sqd import controller as sqd_controller
from worker.chemistry.algorithms.sqd import workflow as sqd_solver


def test_solver_keeps_recovery_loop_as_compatibility_alias() -> None:
    assert sqd_solver._run_sqd_recovery_loop is sqd_controller.run_sqd_recovery_loop
