"""Basis-set metadata endpoints."""

from fastapi import APIRouter

from app.schemas.basis import BasisSetListResponse
from app.services.basis_sets import list_basis_sets

router = APIRouter()


@router.get("")
def get_basis_sets() -> BasisSetListResponse:
    """Return selectable basis sets supported by the chemistry runtime."""
    return list_basis_sets()
