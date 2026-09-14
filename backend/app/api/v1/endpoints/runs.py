"""
Run management endpoints.
"""

import asyncio
import json
import logging
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query, Request, status
from fastapi.responses import JSONResponse, Response
from redis import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse
from starlette.concurrency import run_in_threadpool

from app.dependencies import (
    ensure_local_operator_access,
    get_async_db,
    get_db,
    get_redis,
    run_requires_local_operator_access,
)
from app.exceptions import NotFoundError
from app.models import Run, RunEvent
from app.models.enums import BackendTarget, RunStatus
from app.schemas.run_events import RunEventListResponse, RunEventResponse
from app.schemas.run_metadata import RunConfigMetadataResponse
from app.schemas.run_requests import (
    RunCheckpointCreate,
    RunControlRequest,
    RunCreate,
    RunRestartRequest,
)
from app.schemas.run_responses import (
    ExportBundle,
    RunActionResponse,
    RunCancelResponse,
    RunCheckpointListResponse,
    RunCheckpointResponse,
    RunListResponse,
    RunResponse,
    RunSummaryListResponse,
    RunSummaryResponse,
)
from app.schemas.run_results import RunResultResponse
from app.services.run import RunService
from app.services.run_config_metadata import get_run_config_metadata
from app.services.run_control import RunControlService
from app.services.run_estimation import seed_initial_estimate_for_run
from app.services.run_event_service import RunEventService
from app.services.run_export_service import RunExportService

router = APIRouter()
logger = logging.getLogger(__name__)

_TERMINAL_STATUSES = frozenset(
    {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED, RunStatus.PAUSED}
)
_SSE_HEADERS = {"X-Accel-Buffering": "no"}


def _parse_last_event_id(last_event_id: str | None) -> int:
    return int(last_event_id) if last_event_id and last_event_id.isdigit() else 0


def _format_run_event(event: RunEvent) -> dict[str, str]:
    return {
        "id": str(event.sequence),
        "data": RunEventResponse.model_validate(event).model_dump_json(),
    }


def _stream_end_event(status_value: str) -> dict[str, str]:
    return {"data": json.dumps({"type": "stream_end", "status": status_value})}


def _fetch_run_events(
    db: Session,
    *,
    run_id: UUID,
    after_sequence: int,
) -> list[RunEvent]:
    return list(
        db.execute(
            select(RunEvent)
            .where(RunEvent.run_id == run_id, RunEvent.sequence > after_sequence)
            .order_by(RunEvent.sequence)
        )
        .scalars()
        .all()
    )


async def _fetch_run_events_async(
    async_db: AsyncSession,
    *,
    run_id: UUID,
    after_sequence: int,
) -> list[RunEvent]:
    result = await async_db.execute(
        select(RunEvent)
        .where(RunEvent.run_id == run_id, RunEvent.sequence > after_sequence)
        .order_by(RunEvent.sequence)
    )
    return list(result.scalars().all())


def _create_run_for_request(
    db: Session,
    run_in: RunCreate,
    redis: Redis | None,
) -> tuple[Run, bool]:
    return RunService(db).create(run_in, redis_client=redis)


def _seed_post_create_estimate(
    session_factory: Any | None,
    run_id: UUID,
) -> None:
    if session_factory is None:
        return
    try:
        seed_initial_estimate_for_run(run_id=run_id, session_factory=session_factory)
    except Exception:
        # ETA seeding is best-effort only; the worker telemetry path remains authoritative.
        logger.warning("Failed to seed async estimate for run %s", run_id, exc_info=True)


def _list_runs_for_request(
    db: Session,
    *,
    molecule_id: UUID | None,
    status: RunStatus | None,
    backend_target: BackendTarget | None,
    converged: bool | None,
    chemical_accurate: bool | None,
    limit: int,
    offset: int,
) -> RunListResponse:
    service = RunService(db)
    runs, total = service.list(
        molecule_id=molecule_id,
        status=status,
        backend_target=backend_target,
        converged=converged,
        chemical_accurate=chemical_accurate,
        limit=limit,
        offset=offset,
    )
    return RunListResponse(
        items=[RunResponse.model_validate(r) for r in runs],
        total=total,
        limit=limit,
        offset=offset,
    )


def _list_run_summaries_for_request(
    db: Session,
    *,
    molecule_id: UUID | None,
    status: RunStatus | None,
    backend_target: BackendTarget | None,
    converged: bool | None,
    chemical_accurate: bool | None,
    limit: int,
    offset: int,
) -> RunSummaryListResponse:
    service = RunService(db)
    runs, total = service.list(
        molecule_id=molecule_id,
        status=status,
        backend_target=backend_target,
        converged=converged,
        chemical_accurate=chemical_accurate,
        limit=limit,
        offset=offset,
    )
    return RunSummaryListResponse(
        items=[RunSummaryResponse.from_run(r) for r in runs],
        total=total,
        limit=limit,
        offset=offset,
    )


def _get_run_for_request(
    db: Session,
    run_id: UUID,
) -> RunResponse:
    service = RunService(db)
    run = service.get_by_id(run_id)
    return RunResponse.model_validate(run)


async def _fetch_current_run(async_db: AsyncSession, *, run_id: UUID) -> Run:
    result = await async_db.execute(select(Run).where(Run.id == run_id))
    return result.scalar_one()


async def _terminal_event_generator(
    events: list[RunEvent],
    *,
    status_value: str,
):
    for event in events:
        yield _format_run_event(event)

    yield _stream_end_event(status_value)


async def _live_event_generator(
    *,
    request: Request,
    async_db: AsyncSession,
    run_id: UUID,
    after_sequence: int,
):
    while True:
        if await request.is_disconnected():
            break

        new_events = await _fetch_run_events_async(
            async_db,
            run_id=run_id,
            after_sequence=after_sequence,
        )
        for event in new_events:
            after_sequence = event.sequence
            yield _format_run_event(event)

        current_run = await _fetch_current_run(async_db, run_id=run_id)
        if current_run.status in _TERMINAL_STATUSES:
            final_events = await _fetch_run_events_async(
                async_db,
                run_id=run_id,
                after_sequence=after_sequence,
            )
            for event in final_events:
                yield _format_run_event(event)

            yield _stream_end_event(current_run.status.value)
            break

        await asyncio.sleep(0.5)


@router.post(
    "",
    responses={
        200: {"model": RunResponse, "description": "Run already exists (idempotent match)"},
        201: {"model": RunResponse, "description": "New run created"},
    },
)
async def create_run(
    run_in: RunCreate,
    db: Annotated[Session, Depends(get_db)],
    redis: Annotated[Redis | None, Depends(get_redis)],
    background_tasks: BackgroundTasks,
    http_request: Request,
) -> JSONResponse:
    """
    Create and queue a new quantum run.

    If client_request_id is provided and matches an existing run,
    returns the existing run (idempotency).

    Returns 201 for new run, 200 for idempotent match.
    Status is QUEUED when Redis is available, CREATED otherwise (graceful degradation).

    Raises:
        404: If molecule not found
    """
    if run_requires_local_operator_access(run_in):
        ensure_local_operator_access(http_request)
    run, is_new = await run_in_threadpool(_create_run_for_request, db, run_in, redis)
    if is_new:
        background_tasks.add_task(
            _seed_post_create_estimate,
            getattr(http_request.app.state, "session_factory", None),
            run.id,
        )

    status_code = status.HTTP_201_CREATED if is_new else status.HTTP_200_OK
    return JSONResponse(
        content=RunResponse.model_validate(run).model_dump(mode="json"), status_code=status_code
    )


@router.get("")
def list_runs(
    db: Annotated[Session, Depends(get_db)],
    molecule_id: Annotated[UUID | None, Query(description="Filter by molecule")] = None,
    status: Annotated[RunStatus | None, Query(description="Filter by status")] = None,
    backend_target: Annotated[
        BackendTarget | None, Query(description="Filter by backend target")
    ] = None,
    converged: Annotated[bool | None, Query(description="Filter by convergence flag")] = None,
    chemical_accurate: Annotated[
        bool | None, Query(description="Filter by chemical-accuracy verdict")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=1000, description="Maximum results")] = 50,
    offset: Annotated[int, Query(ge=0, description="Pagination offset")] = 0,
) -> RunListResponse:
    """
    List runs with optional filtering and pagination.

    Returns runs ordered by creation date (newest first).
    """
    return _list_runs_for_request(
        molecule_id=molecule_id,
        db=db,
        status=status,
        backend_target=backend_target,
        converged=converged,
        chemical_accurate=chemical_accurate,
        limit=limit,
        offset=offset,
    )


@router.get("/summaries")
def list_run_summaries(
    db: Annotated[Session, Depends(get_db)],
    molecule_id: Annotated[UUID | None, Query(description="Filter by molecule")] = None,
    status: Annotated[RunStatus | None, Query(description="Filter by status")] = None,
    backend_target: Annotated[
        BackendTarget | None, Query(description="Filter by backend target")
    ] = None,
    converged: Annotated[bool | None, Query(description="Filter by convergence flag")] = None,
    chemical_accurate: Annotated[
        bool | None, Query(description="Filter by chemical-accuracy verdict")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=1000, description="Maximum results")] = 50,
    offset: Annotated[int, Query(ge=0, description="Pagination offset")] = 0,
) -> RunSummaryListResponse:
    """
    List lightweight run summaries for the runs history table.

    Query parameters mirror ``GET /api/runs`` but return only the fields the
    runs list needs for status, timing, backend, and live progress rendering.
    """
    return _list_run_summaries_for_request(
        molecule_id=molecule_id,
        db=db,
        status=status,
        backend_target=backend_target,
        converged=converged,
        chemical_accurate=chemical_accurate,
        limit=limit,
        offset=offset,
    )


@router.get("/config-metadata")
def get_config_metadata() -> RunConfigMetadataResponse:
    """Return registry-backed metadata for run configuration selectors."""
    return get_run_config_metadata()


@router.get("/{run_id}")
def get_run(
    run_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> RunResponse:
    """
    Get a specific run by ID.

    Raises:
        404: If run not found
    """
    return _get_run_for_request(db, run_id)


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_run(
    run_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    redis: Annotated[Redis | None, Depends(get_redis)],
    http_request: Request,
) -> None:
    """
    Delete a run and its dependent artifacts.

    Active queue-local work is cancelled before the row is removed. IBM-backed
    runs require local-operator access and request a best-effort remote Runtime
    cancellation when an IBM job id is available.

    Raises:
        404: If run not found
        403: If IBM-backed deletion lacks local-operator access
    """
    existing = db.get(Run, run_id)
    if existing is None:
        raise NotFoundError(f"Run {run_id} not found")
    if (
        existing.backend_target == BackendTarget.IBM_RUNTIME
        or existing.credential_profile_id is not None
        or existing.ibm_job_id is not None
    ):
        ensure_local_operator_access(http_request)
    RunService(db).delete(run_id, redis_client=redis)


@router.post("/{run_id}/cancel")
def cancel_run(
    run_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    redis: Annotated[Redis | None, Depends(get_redis)],
    http_request: Request,
) -> RunCancelResponse:
    """
    Cancel a run.

    Idempotent: returns 200 if the run is already CANCELLED.
    For QUEUED/RUNNING runs, attempts to remove or stop the Redis/RQ job.
    IBM-backed runs also require local-operator access and request a best-effort
    remote Runtime cancellation immediately when an IBM job ID is available.

    Raises:
        404: If run not found
        409: If run is in COMPLETED or FAILED state
    """
    existing = db.get(Run, run_id)
    if existing is not None and (
        existing.backend_target == BackendTarget.IBM_RUNTIME
        or existing.credential_profile_id is not None
        or existing.ibm_job_id is not None
    ):
        ensure_local_operator_access(http_request)
    service = RunService(db)
    run = service.cancel(run_id, redis_client=redis)
    return RunCancelResponse(id=run.id, status=run.status)


@router.post("/{run_id}/pause")
def pause_run(
    run_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    redis: Annotated[Redis | None, Depends(get_redis)],
    http_request: Request,
    request: RunControlRequest | None = None,
) -> RunActionResponse:
    """Request pause for a run or pause queue-local work immediately."""
    existing = db.get(Run, run_id)
    if existing is None:
        raise NotFoundError(f"Run {run_id} not found")
    if (
        existing.backend_target == BackendTarget.IBM_RUNTIME
        or existing.credential_profile_id is not None
        or existing.ibm_job_id is not None
    ):
        ensure_local_operator_access(http_request)
    service = RunControlService(db)
    run = service.pause(run_id, reason=request.reason if request else None, redis_client=redis)
    return RunActionResponse(
        id=run.id,
        status=run.status,
        execution_generation=run.execution_generation,
        message="Pause requested" if run.status == RunStatus.PAUSING else "Run paused",
    )


@router.post("/{run_id}/resume")
def resume_run(
    run_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    redis: Annotated[Redis | None, Depends(get_redis)],
    http_request: Request,
    request: RunControlRequest | None = None,
) -> RunActionResponse:
    """Resume a paused or failed run by returning it to CREATED or QUEUED."""
    existing = db.get(Run, run_id)
    if existing is None:
        raise NotFoundError(f"Run {run_id} not found")
    if (
        existing.backend_target == BackendTarget.IBM_RUNTIME
        or existing.credential_profile_id is not None
    ):
        ensure_local_operator_access(http_request)
    service = RunControlService(db)
    run = service.resume(run_id, reason=request.reason if request else None, redis_client=redis)
    return RunActionResponse(
        id=run.id,
        status=run.status,
        execution_generation=run.execution_generation,
        message="Run resumed",
    )


@router.post("/{run_id}/restart")
def restart_run(
    run_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    redis: Annotated[Redis | None, Depends(get_redis)],
    http_request: Request,
    request: RunRestartRequest | None = None,
) -> RunActionResponse:
    """Clone a terminal or paused run into a restart child run."""
    existing = db.get(Run, run_id)
    if existing is None:
        raise NotFoundError(f"Run {run_id} not found")
    if (
        existing.backend_target == BackendTarget.IBM_RUNTIME
        or existing.credential_profile_id is not None
    ):
        ensure_local_operator_access(http_request)
    service = RunControlService(db)
    parent, child = service.restart(
        run_id,
        reason=request.reason if request else None,
        client_request_id=request.client_request_id if request else None,
        cancel_active=request.cancel_active if request else False,
        redis_client=redis,
    )
    return RunActionResponse(
        id=parent.id,
        status=parent.status,
        execution_generation=parent.execution_generation,
        child_run_id=child.id,
        message="Restart run created",
    )


@router.post("/{run_id}/checkpoints", status_code=status.HTTP_201_CREATED)
def create_run_checkpoint(
    run_id: UUID,
    checkpoint_in: RunCheckpointCreate,
    db: Annotated[Session, Depends(get_db)],
) -> RunCheckpointResponse:
    """Persist a checkpoint payload for the current run generation."""
    checkpoint = RunControlService(db).create_checkpoint(run_id, checkpoint_in)
    return RunCheckpointResponse.model_validate(checkpoint)


@router.get("/{run_id}/checkpoints")
def list_run_checkpoints(
    run_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    execution_generation: Annotated[int | None, Query(ge=1)] = None,
) -> RunCheckpointListResponse:
    """List checkpoints for a run."""
    checkpoints, total = RunControlService(db).list_checkpoints(
        run_id,
        execution_generation=execution_generation,
    )
    return RunCheckpointListResponse(
        items=[RunCheckpointResponse.model_validate(checkpoint) for checkpoint in checkpoints],
        total=total,
    )


@router.get("/{run_id}/result")
def get_run_result(
    run_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> RunResultResponse:
    """
    Get the result of a completed run.

    Only available for runs in COMPLETED status.

    Raises:
        404: If run not found or no result available
    """
    service = RunExportService(db)
    result = service.get_result(run_id)
    return RunResultResponse.model_validate(result)


@router.get("/{run_id}/events")
def get_run_events(
    run_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    after_sequence: Annotated[
        int, Query(ge=0, description="Return events after this sequence")
    ] = 0,
) -> RunEventListResponse:
    """
    Get events for a run (polling endpoint).

    Returns all events with sequence > after_sequence.
    For real-time updates, use the /events/stream SSE endpoint instead.

    Raises:
        404: If run not found
    """
    service = RunEventService(db)
    events, last_sequence = service.get_events(run_id, after_sequence)

    return RunEventListResponse(
        events=[RunEventResponse.model_validate(e) for e in events],
        last_sequence=last_sequence,
    )


@router.get("/{run_id}/events/stream")
async def stream_run_events(
    run_id: UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    async_db: Annotated[AsyncSession, Depends(get_async_db)],
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> EventSourceResponse:
    """
    Stream run events via Server-Sent Events.

    Polls Postgres every 500ms for new RunEvent rows and pushes them to the client.
    Set the Last-Event-ID header to the last received sequence number to reconnect
    mid-stream without replaying already-seen events.

    The stream closes automatically when the run reaches a terminal status
    (COMPLETED, FAILED, or CANCELLED).

    Raises:
        404: If run not found
    """
    after_sequence = _parse_last_event_id(last_event_id)

    # Validate run exists before opening the stream without blocking the event loop.
    run = await run_in_threadpool(RunService(db).get_by_id, run_id)

    if run.status in _TERMINAL_STATUSES:
        events = await run_in_threadpool(
            _fetch_run_events,
            db,
            run_id=run_id,
            after_sequence=after_sequence,
        )
        return EventSourceResponse(
            _terminal_event_generator(
                events,
                status_value=run.status.value,
            ),
            headers=_SSE_HEADERS,
        )

    return EventSourceResponse(
        _live_event_generator(
            request=request,
            async_db=async_db,
            run_id=run_id,
            after_sequence=after_sequence,
        ),
        headers=_SSE_HEADERS,
    )


@router.get("/{run_id}/export", response_model=ExportBundle)
def export_run(
    run_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    """
    Download a reproducibility bundle for a run as a JSON file.

    Returns a self-contained document with the molecule geometry, run config,
    version snapshot, all events, and final result. Available for any run status —
    partial exports (e.g., for FAILED or RUNNING runs) are valid.

    Raises:
        404: If run not found
    """
    service = RunExportService(db)
    bundle = service.build_export(run_id)
    return Response(
        content=bundle.model_dump_json(indent=2),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="run_{run_id}_export.json"',
        },
    )
