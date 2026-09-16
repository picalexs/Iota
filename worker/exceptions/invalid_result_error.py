"""Errors raised when a solver returns an invalid result payload."""

from __future__ import annotations

from worker.exceptions.chemistry_error import ChemistryError


class InvalidResultError(ChemistryError):
    """The solver result cannot satisfy the worker persistence contract."""

    def __init__(self, reason: str, message: str | None = None) -> None:
        self.reason = reason
        super().__init__(message or reason)
