"""Tests for the SQD selected-CI recovery boundary."""

from worker.chemistry.algorithms.sqd import recovery as sqd_recovery
from worker.chemistry.algorithms.sqd import workflow as sqd_solver


def test_solver_keeps_recovery_types_and_entrypoint_as_compatibility_aliases() -> None:
    assert sqd_solver._SQDDependencies is sqd_recovery.SQDDependencies
    assert sqd_solver._SQDBatchOutcome is sqd_recovery.SQDBatchOutcome
    assert sqd_solver._run_selected_ci_batches is sqd_recovery.run_selected_ci_batches
