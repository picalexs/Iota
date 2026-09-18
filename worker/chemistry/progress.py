"""Canonical progress event types emitted by chemistry solvers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

ProgressEvent = dict[str, Any]
ProgressCallback = Callable[[ProgressEvent], None]
