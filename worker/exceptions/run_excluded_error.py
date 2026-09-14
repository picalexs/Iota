"""Exclusion signal for runs that are valid but unsupported at this size."""


class RunExcludedError(ValueError):
    """Raised when a run cannot execute on the requested target by policy.

    This is not a failure. The configuration is valid and may run on other
    targets or smaller active spaces; it is out of scope for the requested
    target. The worker marks such runs EXCLUDED, not FAILED. It subclasses
    ``ValueError`` so existing value-error handling still catches it, while the
    failure callback routes it to the EXCLUDED terminal state by type.
    """

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason
