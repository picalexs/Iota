"""Benchmark batch persistence endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse
from redis import Redis
from sqlalchemy.orm import Session

from app.dependencies import ensure_local_operator_access, get_db, get_redis
from app.models.enums import BackendTarget
from app.schemas.benchmark import (
    BenchmarkRegistrationCreate,
    BenchmarkRunCreate,
    BenchmarkRunListResponse,
    BenchmarkRunResponse,
    BenchmarkRunUpdate,
)
from app.services.benchmark import BenchmarkRunService

router = APIRouter()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_benchmark_run(
    benchmark_in: BenchmarkRunCreate,
    db: Annotated[Session, Depends(get_db)],
) -> BenchmarkRunResponse:
    """Persist a benchmark batch snapshot."""
    service = BenchmarkRunService(db)
    benchmark = service.create(benchmark_in)
    return BenchmarkRunResponse.model_validate(benchmark)


@router.post(
    "/register",
    responses={
        200: {"model": BenchmarkRunResponse, "description": "Campaign already registered"},
        201: {"model": BenchmarkRunResponse, "description": "Campaign registered"},
    },
)
def register_benchmark(
    benchmark_in: BenchmarkRegistrationCreate,
    db: Annotated[Session, Depends(get_db)],
) -> JSONResponse:
    """Register one validated campaign as a persisted benchmark."""
    service = BenchmarkRunService(db)
    benchmark, is_new = service.register(benchmark_in)
    return JSONResponse(
        content=BenchmarkRunResponse.model_validate(benchmark).model_dump(
            mode="json", by_alias=True
        ),
        status_code=status.HTTP_201_CREATED if is_new else status.HTTP_200_OK,
    )


@router.get("")
def list_benchmark_runs(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=1000, description="Maximum results")] = 50,
    offset: Annotated[int, Query(ge=0, description="Pagination offset")] = 0,
) -> BenchmarkRunListResponse:
    """List persisted benchmark batches ordered by most recent update."""
    service = BenchmarkRunService(db)
    benchmarks, total = service.list(limit=limit, offset=offset)
    return BenchmarkRunListResponse(
        items=[BenchmarkRunResponse.model_validate(benchmark) for benchmark in benchmarks],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{benchmark_id}")
def get_benchmark_run(
    benchmark_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> BenchmarkRunResponse:
    """Get a persisted benchmark batch by id."""
    service = BenchmarkRunService(db)
    benchmark = service.get_by_id(benchmark_id)
    return BenchmarkRunResponse.model_validate(benchmark)


@router.patch("/{benchmark_id}")
def update_benchmark_run(
    benchmark_id: UUID,
    benchmark_in: BenchmarkRunUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> BenchmarkRunResponse:
    """Patch a persisted benchmark batch snapshot."""
    service = BenchmarkRunService(db)
    benchmark = service.update(benchmark_id, benchmark_in)
    return BenchmarkRunResponse.model_validate(benchmark)


@router.delete("/{benchmark_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_benchmark_run(
    benchmark_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    redis: Annotated[Redis | None, Depends(get_redis)],
    http_request: Request,
    delete_associated_runs: Annotated[
        bool,
        Query(
            description="Also delete any persisted runs referenced by the benchmark snapshot.",
        ),
    ] = False,
) -> None:
    """Delete a persisted benchmark batch."""
    service = BenchmarkRunService(db)
    if delete_associated_runs:
        associated_runs = service.list_associated_runs(benchmark_id)
        if any(
            run.backend_target == BackendTarget.IBM_RUNTIME
            or run.credential_profile_id is not None
            or run.ibm_job_id is not None
            for run in associated_runs
        ):
            ensure_local_operator_access(http_request)
    service.delete(
        benchmark_id,
        delete_associated_runs=delete_associated_runs,
        redis_client=redis,
    )
