"""
Custom exception classes for the application.
"""


class APIException(Exception):
    """Base exception for all API errors."""

    def __init__(self, code: str, message: str, status_code: int = 400, field: str | None = None):
        """
        Initialize API exception.

        Args:
            code: Machine-readable error code
            message: Human-readable error message
            status_code: HTTP status code
            field: Optional field name for validation errors
        """
        self.code = code
        self.message = message
        self.status_code = status_code
        self.field = field
        super().__init__(message)


class NotFoundError(APIException):
    """Exception raised when a resource is not found."""

    def __init__(self, message: str, field: str | None = None):
        """Initialize NotFoundError with 404 status."""
        super().__init__("NOT_FOUND", message, 404, field)


class ConflictError(APIException):
    """Exception raised when there's a conflict (e.g., invalid state transition)."""

    def __init__(self, message: str, field: str | None = None):
        """Initialize ConflictError with 409 status."""
        super().__init__("CONFLICT", message, 409, field)


class ValidationError(APIException):
    """Exception raised for validation errors."""

    def __init__(self, message: str, field: str | None = None):
        """Initialize ValidationError with 422 status."""
        super().__init__("VALIDATION_ERROR", message, 422, field)


class InternalError(APIException):
    """Exception raised for internal server errors."""

    def __init__(self, message: str = "An unexpected error occurred"):
        """Initialize InternalError with 500 status."""
        super().__init__("INTERNAL_ERROR", message, 500)


__all__ = [
    "APIException",
    "NotFoundError",
    "ConflictError",
    "ValidationError",
    "InternalError",
]
