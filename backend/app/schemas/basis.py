"""Basis-set metadata schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class BasisSetMetadata(BaseModel):
    """A selectable chemistry basis set."""

    id: str
    label: str
    description: str
    family: str
    recommended: bool = False
    supported_elements: list[str] = Field(default_factory=list)


class BasisSetListResponse(BaseModel):
    """Basis metadata returned to frontend selectors."""

    default_basis_set: str
    basis_sets: list[BasisSetMetadata]
