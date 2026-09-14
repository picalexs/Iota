"""Local primitive-job observation and cooperative cancellation."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from .control_state import RunCancelled, RunPaused

logger = logging.getLogger(__name__)

_LOCAL_PRIMITIVE_POLL_INTERVAL_SECONDS = 1.0

RunGuard = Callable[[], None]
RunGuardFactory = Callable[[str], RunGuard]


class ObservedLocalPrimitiveJob:
    """Proxy a local primitive job while enforcing the run control state."""

    def __init__(self, job: Any, *, run_guard: RunGuard, run_id: str) -> None:
        self._job = job
        self._run_guard = run_guard
        self._run_id = run_id

    def __getattr__(self, name: str) -> Any:
        return getattr(self._job, name)

    def _cancel_job(self) -> None:
        cancel = getattr(self._job, "cancel", None)
        if not callable(cancel):
            return
        try:
            cancel()
        except Exception:
            logger.warning(
                "Failed to cancel local primitive job for run %s",
                self._run_id,
                exc_info=True,
            )

    def _wait_until_ready(self) -> None:
        done = getattr(self._job, "done", None)
        in_final_state = getattr(self._job, "in_final_state", None)

        while True:
            try:
                self._run_guard()
            except (RunCancelled, RunPaused):
                self._cancel_job()
                raise

            job_done = bool(done()) if callable(done) else False
            job_final = bool(in_final_state()) if callable(in_final_state) else False
            if job_done or job_final:
                return
            time.sleep(_LOCAL_PRIMITIVE_POLL_INTERVAL_SECONDS)

    def result(self, *args: Any, **kwargs: Any) -> Any:
        self._wait_until_ready()
        self._run_guard()
        return self._job.result(*args, **kwargs)


def build_local_primitive_job_observer(
    *,
    run_id: str,
    run_guard_factory: RunGuardFactory,
) -> Callable[[Any, dict[str, Any]], Any | None]:
    """Build a local primitive observer with an injected control-state guard."""
    run_guard = run_guard_factory(run_id)

    def observe(job: Any, metadata: dict[str, Any]) -> Any | None:
        del metadata
        return ObservedLocalPrimitiveJob(job, run_guard=run_guard, run_id=run_id)

    return observe
