"""
Exception handlers for FastAPI application.
"""

import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError

from app.exceptions import APIException

logger = logging.getLogger(__name__)


def api_exception_handler(_request: Request, exc: APIException) -> JSONResponse:
    """
    Handle custom API exceptions.

    Returns a consistent JSON error response.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": {
                "code": exc.code,
                "message": exc.message,
                "field": exc.field,
            }
        },
    )


def validation_exception_handler(
    _request: Request, exc: RequestValidationError | PydanticValidationError
) -> JSONResponse:
    """
    Handle Pydantic validation errors.

    Converts validation errors to consistent error format.
    """
    errors = exc.errors() if hasattr(exc, "errors") else []

    # Get first error for simple response
    if errors:
        first_error = errors[0]
        field = ".".join(str(loc) for loc in first_error.get("loc", []))
        message = first_error.get("msg", "Validation error")
    else:
        field = None
        message = "Validation error"

    logger.warning("Validation error: %s (field: %s)", message, field)

    return JSONResponse(
        status_code=422,
        content={
            "detail": {
                "code": "VALIDATION_ERROR",
                "message": message,
                "field": field,
            }
        },
    )


def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    """
    Handle unexpected exceptions.

    Logs the full traceback but returns a sanitized error to the client.
    """
    logger.exception("Unhandled exception: %s", exc)

    return JSONResponse(
        status_code=500,
        content={
            "detail": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "field": None,
            }
        },
    )
