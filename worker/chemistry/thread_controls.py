"""Bound CPU-side numerical thread pools for one worker job."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

_THREAD_ENVIRONMENT_VARIABLES = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)
_DEFAULT_THREAD_LIMIT = 8


def configure_thread_limits(
    backend_options: Mapping[str, Any] | None = None,
    *,
    default_limit: int = _DEFAULT_THREAD_LIMIT,
) -> dict[str, Any]:
    """Apply a bounded CPU thread policy and return provenance metadata.

    RQ runs each job in a child work-horse process. Setting these variables at
    the job boundary therefore does not change the parent worker or another
    queue's process. Aer still receives its own numerical limits through the
    backend options; this policy covers CPU libraries used by chemistry and
    projected solves.
    """
    options = backend_options or {}
    configured_default = os.getenv("QSS_CPU_THREAD_LIMIT")
    if configured_default is not None:
        try:
            default_limit = int(configured_default)
        except ValueError as exc:
            raise ValueError("QSS_CPU_THREAD_LIMIT must be a positive integer") from exc
    requested = options.get("max_parallel_threads")
    if isinstance(default_limit, bool) or not isinstance(default_limit, int) or default_limit < 1:
        raise ValueError("default_limit must be a positive integer")

    if requested is None:
        limit = default_limit
        source = "worker_default"
    elif isinstance(requested, bool) or not isinstance(requested, (int, float)):
        raise ValueError("max_parallel_threads must be a positive integer")
    else:
        limit = int(requested)
        if limit < 1 or float(requested) != float(limit):
            raise ValueError("max_parallel_threads must be a positive integer")
        source = "backend_options"

    for name in _THREAD_ENVIRONMENT_VARIABLES:
        os.environ[name] = str(limit)

    return {
        "configured": True,
        "cpu_thread_limit": limit,
        "source": source,
        "environment_variables": list(_THREAD_ENVIRONMENT_VARIABLES),
        "aer_thread_options": {
            key: options[key]
            for key in (
                "max_parallel_threads",
                "max_parallel_experiments",
                "max_parallel_shots",
            )
            if key in options
        },
    }


__all__ = ["configure_thread_limits"]
