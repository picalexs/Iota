"""Main API v1 router."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    backends,
    basis_sets,
    benchmarks,
    health,
    molecules,
    runs,
    settings,
    validate,
)

api_router = APIRouter()

api_router.include_router(
    molecules.router,
    prefix="/molecules",
    tags=["Molecules"],
)

api_router.include_router(
    runs.router,
    prefix="/runs",
    tags=["Runs"],
)

api_router.include_router(
    benchmarks.router,
    prefix="/benchmarks",
    tags=["Benchmarks"],
)

api_router.include_router(
    backends.router,
    prefix="/backends",
    tags=["Backends"],
)

api_router.include_router(
    basis_sets.router,
    prefix="/basis-sets",
    tags=["Basis Sets"],
)

api_router.include_router(
    settings.router,
    prefix="/settings",
    tags=["Settings"],
)

api_router.include_router(
    health.router,
    prefix="/health",
    tags=["Health"],
)

api_router.include_router(
    health.status_router,
    prefix="/status",
    tags=["Health"],
)

api_router.include_router(
    validate.router,
    prefix="/validate",
    tags=["Validation"],
)
