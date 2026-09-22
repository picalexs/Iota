"""Canonical progress event types emitted by chemistry solvers."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypedDict


class ProgressEvent(TypedDict, total=False):
    """Common fields available on chemistry progress events."""

    algorithm: str
    stage: str
    step: str
    progress_phase: str
    completed_iterations: int
    total_iterations: int
    overall_iterations: int
    converged: bool
    convergence_reason: str
    execution_mode: str
    actual_execution_target: str
    primitive_family: str
    selection_reason: str


ProgressCallback = Callable[[ProgressEvent], None]
