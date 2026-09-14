"""Table-driven characterization of worker lifecycle control checkpoints."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from worker.jobs.control_state import handle_pre_start_control_state, handle_setup_control_state
from worker.jobs.execute_run import execute_run


@pytest.mark.parametrize(
    ("phase", "status", "expected"),
    [
        ("before_start", "RUNNING", None),
        ("before_start", "CANCELLED", {"algorithm": "vqe", "status": "STOPPED"}),
        ("before_start", "PAUSED", {"algorithm": "vqe", "status": "STOPPED"}),
        ("before_start", "PAUSING", {"algorithm": "vqe", "status": "PAUSED"}),
        ("setup", "RUNNING", None),
        ("setup", "CANCELLED", {"algorithm": "vqe", "status": "STOPPED"}),
        ("setup", "PAUSING", {"algorithm": "vqe", "status": "PAUSED"}),
    ],
)
def test_lifecycle_control_matrix(phase: str, status: str, expected: dict | None) -> None:
    session = MagicMock()
    repository = MagicMock()
    repository.request_control_state.return_value = status
    repository.save_pause_checkpoint.return_value = "checkpoint-1"
    repository.mark_paused.return_value = 1

    def stopped_run_result(algorithm: str, **kwargs: object) -> dict[str, object]:
        return {"algorithm": algorithm, "status": kwargs.get("status", "STOPPED")}

    if phase == "before_start":
        actual = handle_pre_start_control_state(
            session,
            run_id="run-1",
            execution_generation=1,
            algorithm="vqe",
            progress_state={},
            repository_factory=lambda _: repository,
            stopped_run_result=stopped_run_result,
        )
    else:
        actual = handle_setup_control_state(
            session,
            run_id="run-1",
            execution_generation=1,
            algorithm="vqe",
            progress_state={},
            config_snapshot={},
            hamiltonian_bundle=SimpleNamespace(metadata={"pipeline": "test"}),
            repository_factory=lambda _: repository,
            stopped_run_result=stopped_run_result,
        )

    assert actual == expected
    if status == "PAUSING":
        repository.save_pause_checkpoint.assert_called_once()
        session.commit.assert_called_once()
    else:
        repository.save_pause_checkpoint.assert_not_called()


def test_missing_run_fails_before_backend_or_solver_setup() -> None:
    session = MagicMock()

    def execute_side_effect(*_: object, **__: object) -> MagicMock:
        result = MagicMock()
        result.fetchone.return_value = None
        result.rowcount = 0
        return result

    session.execute.side_effect = execute_side_effect
    session_context = MagicMock()
    session_context.__enter__.return_value = session
    session_context.__exit__.return_value = False

    with patch("worker.jobs.execute_run.get_db_session", return_value=session_context):
        with pytest.raises(RuntimeError, match="Unable to resolve molecule"):
            execute_run("missing-run")
