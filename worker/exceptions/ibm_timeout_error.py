"""IBM timeout exception."""

from worker.exceptions.backend_error import BackendError


class IBMTimeoutError(BackendError):
    """Raised when IBM Runtime submission or polling exceeds a timeout."""
