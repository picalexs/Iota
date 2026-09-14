"""Tests for local primitive-job observation."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from worker.jobs.control_state import RunCancelled
from worker.jobs.local_observation import (
    ObservedLocalPrimitiveJob,
    build_local_primitive_job_observer,
)


class LocalJob:
    def __init__(self) -> None:
        self.cancel_calls = 0

    def done(self) -> bool:
        return False

    def in_final_state(self) -> bool:
        return False

    def cancel(self) -> None:
        self.cancel_calls += 1

    def result(self) -> dict[str, bool]:
        return {"ok": True}


def test_observer_injects_run_guard_and_cancels_before_reraising() -> None:
    job = LocalJob()
    guard = Mock(side_effect=RunCancelled("run-1"))
    observer = build_local_primitive_job_observer(
        run_id="run-1",
        run_guard_factory=Mock(return_value=guard),
    )

    observed = observer(job, {})

    assert isinstance(observed, ObservedLocalPrimitiveJob)
    with pytest.raises(RunCancelled, match="run-1"):
        observed.result()

    guard.assert_called_once_with()
    assert job.cancel_calls == 1


def test_observer_delegates_result_after_job_is_ready() -> None:
    job = Mock(done=Mock(return_value=True), result=Mock(return_value={"ok": True}))
    guard = Mock()
    observer = build_local_primitive_job_observer(
        run_id="run-2",
        run_guard_factory=lambda _: guard,
    )

    observed = observer(job, {})

    assert observed is not None
    assert observed.result() == {"ok": True}
    assert guard.call_count == 2
    job.result.assert_called_once_with()
