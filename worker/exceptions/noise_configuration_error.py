"""Errors raised when a requested simulator noise profile is invalid."""

from __future__ import annotations

from worker.exceptions.backend_error import BackendError


class NoiseConfigurationError(BackendError):
    """The worker cannot construct the requested Aer noise configuration."""

