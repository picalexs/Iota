"""
Common Pydantic schemas used across multiple resources.
"""

from pydantic import BaseModel, ConfigDict


class BaseORMModel(BaseModel):
    """
    Base model with ORM mode enabled for SQLAlchemy integration.
    """

    model_config = ConfigDict(from_attributes=True)


class ErrorDetail(BaseModel):
    """Standard error response format."""

    code: str
    message: str
    field: str | None = None


class ErrorResponse(BaseModel):
    """API error response envelope."""

    detail: ErrorDetail
