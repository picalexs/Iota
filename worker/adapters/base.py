"""Backend adapter abstractions for worker execution."""

from __future__ import annotations

import logging
import math
import signal
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

PrimitiveJobObserver = Callable[[Any, dict[str, Any]], Any | None]
PrimitiveRunGuard = Callable[[], None]
PrimitiveTimeoutFactory = Callable[[float], Exception]
PrimitiveRunFailureObserver = Callable[[BaseException, tuple[Any, ...], dict[str, Any]], None]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AdapterCapabilities:
    """Capability descriptor exposed by each backend adapter."""

    backend_target: str
    enabled: bool
    supports_noise_profile: bool


@dataclass(frozen=True)
class BackendExecutionContext:
    """Resolved backend execution options passed separately from algorithm config."""

    backend_target: str
    backend_options: dict[str, Any] = field(default_factory=dict)
    noise_profile: dict[str, Any] | None = None
    selection_policy: str = "requested"
    shots: int = 4096
    requested_shots: int | None = None
    estimator_precision: float = 0.0
    requested_estimator_precision: float | None = None
    optimization_level: int = 1
    simulator_method: str = "automatic"
    primitive_job_observer: PrimitiveJobObserver | None = field(
        default=None,
        compare=False,
        repr=False,
    )
    primitive_run_guard: PrimitiveRunGuard | None = field(
        default=None,
        compare=False,
        repr=False,
    )


class BackendAdapter(ABC):
    """Abstract backend adapter used by dispatcher and execution flow."""

    @property
    @abstractmethod
    def capabilities(self) -> AdapterCapabilities:
        """Return capability flags for this adapter."""

    @abstractmethod
    def create_estimator(self, context: BackendExecutionContext | None = None) -> Any:
        """Create an estimator primitive or an execution placeholder."""

    @abstractmethod
    def create_sampler(self, context: BackendExecutionContext | None = None) -> Any:
        """Create a sampler primitive or an execution placeholder."""

    def execution_metadata(self, context: BackendExecutionContext | None = None) -> dict[str, Any]:
        """Return backend metadata suitable for setup/result payloads."""
        del context
        return {}


class TrackingPrimitive:
    """Small wrapper that records primitive job ids without changing solver calls."""

    def __init__(
        self,
        primitive: Any,
        job_ids: list[str],
        run_observer: Callable[[tuple[Any, ...], dict[str, Any], Any], None] | None = None,
        run_transform: Callable[
            [tuple[Any, ...], dict[str, Any]],
            tuple[tuple[Any, ...], dict[str, Any]],
        ]
        | None = None,
        run_guard: PrimitiveRunGuard | None = None,
        job_observer: PrimitiveJobObserver | None = None,
        job_metadata: dict[str, Any] | None = None,
        submission_timeout_seconds: float | None = None,
        run_timeout_error_factory: PrimitiveTimeoutFactory | None = None,
        run_label: str | None = None,
        run_failure_observer: PrimitiveRunFailureObserver | None = None,
    ) -> None:
        self._primitive = primitive
        self._job_ids = job_ids
        self._run_observer = run_observer
        self._run_transform = run_transform
        self._run_guard = run_guard
        self._job_observer = job_observer
        self._job_metadata = dict(job_metadata or {})
        self._submission_timeout_seconds = submission_timeout_seconds
        self._run_timeout_error_factory = run_timeout_error_factory
        self._run_label = run_label
        self._run_failure_observer = run_failure_observer

    def __getattr__(self, name: str) -> Any:
        return getattr(self._primitive, name)

    def _prepare_run_call(
        self,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> tuple[tuple[Any, ...], dict[str, Any], int | None]:
        run_args = args
        run_kwargs = dict(kwargs)
        if self._run_guard is not None:
            self._run_guard()
        if self._run_transform is not None:
            run_args, run_kwargs = self._run_transform(run_args, run_kwargs)
        if self._run_guard is not None:
            self._run_guard()
        return run_args, run_kwargs, _extract_pub_count(run_args, run_kwargs)

    def _record_job_observation(
        self,
        job: Any,
        run_args: tuple[Any, ...],
        run_kwargs: dict[str, Any],
        job_id: str | None,
    ) -> Any:
        if self._run_observer is not None:
            self._run_observer(run_args, run_kwargs, job)
        if self._job_observer is None:
            return job
        metadata = dict(self._job_metadata)
        if job_id is not None:
            metadata["job_id"] = job_id
        pub_count = _extract_pub_count(run_args, run_kwargs)
        if pub_count is not None:
            metadata["pub_count"] = pub_count
        shots = _extract_shots(run_kwargs)
        if shots is not None:
            metadata["shots"] = shots
        observed_job = self._job_observer(job, metadata)
        return job if observed_job is None else observed_job

    def run(self, *args: Any, **kwargs: Any) -> Any:
        try:
            run_args, run_kwargs, pub_count = self._prepare_run_call(args, kwargs)
        except Exception as exc:
            if self._run_failure_observer is not None:
                self._run_failure_observer(exc, args, kwargs)
            raise
        label = self._run_label or self._primitive.__class__.__name__
        started = time.monotonic()
        submission_timeout = _normalize_timeout_seconds(self._submission_timeout_seconds)
        if submission_timeout is not None:
            logger.info(
                "%s: submitting primitive run pub_count=%s timeout=%.1fs",
                label,
                pub_count,
                submission_timeout,
            )
        try:
            job = _call_with_submission_timeout(
                lambda: self._primitive.run(*run_args, **run_kwargs),
                timeout_seconds=submission_timeout,
                error_factory=self._run_timeout_error_factory,
            )
        except Exception as exc:
            if self._run_failure_observer is not None:
                self._run_failure_observer(exc, run_args, run_kwargs)
            logger.exception(
                "%s: primitive submission failed after %.2fs pub_count=%s",
                label,
                time.monotonic() - started,
                pub_count,
            )
            raise
        job_id = _extract_job_id(job)
        if submission_timeout is not None:
            logger.info(
                "%s: primitive run returned after %.2fs job_id=%s pub_count=%s",
                label,
                time.monotonic() - started,
                job_id or "<unknown>",
                pub_count,
            )
        if job_id is not None:
            self._job_ids.append(job_id)
        return self._record_job_observation(job, run_args, run_kwargs, job_id)


def _extract_job_id(job: Any) -> str | None:
    """Best-effort extraction for local and Runtime primitive job identifiers."""
    for attr in ("job_id", "id"):
        candidate = getattr(job, attr, None)
        if callable(candidate):
            try:
                value = candidate()
            except TypeError:
                value = None
        else:
            value = candidate
        if value:
            return str(value)
    return None


def _extract_pub_count(args: tuple[Any, ...], kwargs: dict[str, Any]) -> int | None:
    if "pubs" in kwargs:
        pubs = kwargs.get("pubs")
    elif args:
        pubs = args[0]
    else:
        pubs = None
    if isinstance(pubs, (list, tuple)):
        return len(pubs)
    return None


def _extract_shots(kwargs: dict[str, Any]) -> int | None:
    shots = kwargs.get("shots")
    if isinstance(shots, bool) or not isinstance(shots, (int, float)):
        return None
    return int(shots)


def _normalize_timeout_seconds(value: float | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    normalized = float(value)
    if not math.isfinite(normalized) or normalized <= 0.0:
        return None
    return normalized


def _default_timeout_error_factory(timeout_seconds: float) -> Exception:
    return TimeoutError(f"Primitive submission exceeded {timeout_seconds:.1f}s")


def _call_with_submission_timeout(
    callback: Callable[[], Any],
    *,
    timeout_seconds: float | None,
    error_factory: PrimitiveTimeoutFactory | None = None,
) -> Any:
    if timeout_seconds is None:
        return callback()

    if threading.current_thread() is not threading.main_thread() or not hasattr(
        signal, "setitimer"
    ):
        logger.warning(
            "Primitive submission timeout %.1fs requested, but signal timers are unavailable; "
            "continuing without a hard timeout.",
            timeout_seconds,
        )
        return callback()

    timeout_builder = error_factory or _default_timeout_error_factory

    def handle_timeout(_signum: int, _frame: Any) -> None:
        raise timeout_builder(timeout_seconds)

    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_delay, previous_interval = signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
    signal.signal(signal.SIGALRM, handle_timeout)
    try:
        return callback()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_delay > 0.0 or previous_interval > 0.0:
            signal.setitimer(signal.ITIMER_REAL, previous_delay, previous_interval)
