"""
Service layer for run business logic.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, load_only, selectinload

from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.models import Molecule, Run, RunResult
from app.models.enums import BackendTarget, RunEventType, RunMode, RunStatus
from app.schemas.backend import BackendResolveRequest
from app.schemas.run_config import BackendSelectionPolicy, NoiseModelSource
from app.schemas.run_requests import RunCreate
from app.schemas.run_responses import resolve_run_chemical_accurate
from app.schemas.settings import IbmRuntimeCredentials
from app.services import queue_service
from app.services.active_space import extract_active_space
from app.services.backend_runtime import resolve_backend
from app.services.basis_sets import normalize_basis_set
from app.services.credential_profiles import IbmCredentialProfileService
from app.services.easy_mode_presets import build_easy_mode_metadata
from app.services.run_event_service import RunEventService
from app.services.validation_service import validate_run_request

logger = logging.getLogger(__name__)


def _run_summary_load_options():
    return (
        load_only(
            Run.id,
            Run.molecule_id,
            Run.status,
            Run.algorithm,
            Run.backend_target,
            Run.config_json,
            Run.execution_generation,
            Run.restarted_from_run_id,
            Run.credential_profile_id,
            Run.credential_profile_name,
            Run.basis_set,
            Run.run_metadata,
            Run.latest_estimate,
            Run.created_at,
            Run.updated_at,
        ),
        selectinload(Run.molecule).load_only(Molecule.id, Molecule.name),
        selectinload(Run.result).load_only(
            RunResult.run_id,
            RunResult.converged,
            RunResult.signed_error,
            RunResult.reference_energy,
        ),
    )


def _required_qubits_for_ibm_resolution(n_orbitals: int | None) -> int:
    if isinstance(n_orbitals, int) and n_orbitals > 0:
        return max(1, 2 * n_orbitals)
    return 4


def _freeze_ibm_backend_selection(
    *,
    run_in: RunCreate,
    n_orbitals: int | None,
    profile_credentials: IbmRuntimeCredentials | None,
    snapshot_config: dict[str, Any],
) -> None:
    if run_in.backend_target != BackendTarget.IBM_RUNTIME or profile_credentials is None:
        return

    selection_policy = run_in.backend_options.selection_policy
    if selection_policy == BackendSelectionPolicy.MANUAL:
        return

    resolved = resolve_backend(
        BackendResolveRequest(
            target=run_in.backend_target,
            backend_options=run_in.backend_options,
            required_qubits=_required_qubits_for_ibm_resolution(n_orbitals),
            algorithm=run_in.algorithm,
        ),
        ibm_credentials=profile_credentials,
    )
    if not resolved.resolved or not resolved.backend_name:
        logger.warning(
            "Could not freeze IBM backend selection during run creation; "
            "selection_policy=%s warnings=%s",
            selection_policy.value,
            resolved.warnings,
        )
        return

    snapshot_backend_options = dict(snapshot_config.get("backend_options") or {})
    snapshot_backend_options["backend_name"] = resolved.backend_name
    snapshot_config["backend_options"] = snapshot_backend_options


def _build_runtime_service(credentials: IbmRuntimeCredentials) -> Any:
    from qiskit_ibm_runtime import QiskitRuntimeService

    return QiskitRuntimeService(
        channel=cast(Any, credentials.channel),
        token=credentials.token,
        instance=credentials.instance,
    )


def _best_effort_cancel_ibm_runtime_job(
    *,
    run: Run,
    profile_service: IbmCredentialProfileService,
    runtime_service_factory: Callable[[IbmRuntimeCredentials], Any] | None = None,
) -> None:
    """Request remote IBM job cancellation without blocking the local transition."""
    if run.backend_target != BackendTarget.IBM_RUNTIME or not run.ibm_job_id:
        return

    try:
        credentials = profile_service.resolve_credentials(run.credential_profile_id)
    except Exception:
        logger.warning(
            "Unable to resolve IBM credentials for remote cancel of run %s job %s",
            run.id,
            run.ibm_job_id,
            exc_info=True,
        )
        return

    if credentials is None:
        logger.warning(
            "Run %s has IBM job %s but no resolvable credential profile for remote cancel",
            run.id,
            run.ibm_job_id,
        )
        return

    try:
        service = (
            runtime_service_factory(credentials)
            if runtime_service_factory is not None
            else _build_runtime_service(credentials)
        )
        job = service.job(str(run.ibm_job_id))
        cancel = getattr(job, "cancel", None)
        if not callable(cancel):
            logger.warning(
                "IBM Runtime job %s for run %s does not expose cancel()",
                run.ibm_job_id,
                run.id,
            )
            return
        cancel()
    except Exception:
        logger.warning(
            "Failed remote IBM cancel for run %s job %s",
            run.id,
            run.ibm_job_id,
            exc_info=True,
        )
    else:
        logger.info(
            "Requested remote IBM cancel for run %s job %s",
            run.id,
            run.ibm_job_id,
        )


def _needs_ibm_credentials(run_in: RunCreate) -> bool:
    return run_in.backend_target == BackendTarget.IBM_RUNTIME or (
        run_in.backend_target == BackendTarget.AER_SIMULATOR
        and run_in.noise_profile is not None
        and run_in.noise_profile.source == NoiseModelSource.BACKEND_DERIVED
    )


def _resolve_create_profile_credentials(
    *,
    run_in: RunCreate,
    profile_service: IbmCredentialProfileService,
) -> IbmRuntimeCredentials | None:
    if not _needs_ibm_credentials(run_in):
        return None
    return profile_service.resolve_credentials(run_in.backend_options.credential_profile_id)


def _validate_create_request(
    *,
    run_in: RunCreate,
    molecule: Molecule,
    n_electrons: int | None,
    n_orbitals: int | None,
    profile_credentials: IbmRuntimeCredentials | None,
) -> None:
    validation = validate_run_request(
        run_in,
        molecule_active_space_n_electrons=n_electrons,
        molecule_active_space_n_orbitals=n_orbitals,
        molecule_multiplicity=int(molecule.multiplicity),
        molecule_atoms=molecule.atoms,
        molecule_charge=int(molecule.charge or 0),
        molecule_active_space_method=(
            molecule.active_space.get("method")
            if isinstance(molecule.active_space, dict)
            else None
        ),
        require_ibm_confirmation=True,
        ibm_credentials_available=bool(profile_credentials),
    )
    if validation.valid or not validation.errors:
        return

    first_error = validation.errors[0]
    raise ValidationError(first_error.message, field=first_error.field)


def _find_idempotent_run(db: Session, run_in: RunCreate) -> Run | None:
    if not run_in.client_request_id:
        return None
    return db.scalars(select(Run).where(Run.client_request_id == run_in.client_request_id)).first()


def _apply_credential_profile_to_snapshot(
    *,
    snapshot_config: dict[str, Any],
    credential_profile_id: UUID | None,
) -> None:
    if credential_profile_id is None:
        return

    snapshot_backend_options = dict(snapshot_config.get("backend_options") or {})
    snapshot_backend_options["credential_profile_id"] = str(credential_profile_id)
    snapshot_config["backend_options"] = snapshot_backend_options


def _build_run_metadata(run_in: RunCreate, molecule: Molecule) -> dict[str, Any]:
    run_metadata: dict[str, Any] = {
        "algorithm": run_in.algorithm.value,
        "mode": run_in.mode.value,
        "backend_target": run_in.backend_target.value,
    }
    if run_in.mode == RunMode.EASY:
        run_metadata["easy_mode"] = build_easy_mode_metadata(
            algorithm=run_in.algorithm,
            goal=run_in.easy_options.goal if run_in.easy_options else None,
            molecule=molecule,
            backend_target=run_in.backend_target,
            has_noise_profile=run_in.noise_profile is not None,
        )
    return run_metadata


def _rollback_failed_enqueue(db: Session, *, run: Run, rq_job_id: str | None, redis_client) -> None:
    try:
        db.rollback()
    except Exception:
        logger.warning(
            "Rollback after failed enqueue/commit for run %s raised",
            run.id,
            exc_info=True,
        )

    if rq_job_id is None:
        return

    try:
        queue_service.cancel_queued_job(rq_job_id, redis_client)
    except Exception:
        logger.warning(
            "Failed to cancel orphan RQ job %s for run %s",
            rq_job_id,
            run.id,
            exc_info=True,
        )


def _enqueue_created_run(db: Session, *, run: Run, redis_client) -> None:
    if redis_client is None:
        return

    rq_job_id: str | None = None
    try:
        queue_routing = queue_service.queue_routing_for_run(run)
        queue_service.record_queue_routing_metadata(run, queue_routing)
        rq_job_id = queue_service.enqueue_run(
            run.id,
            redis_client,
            execution_generation=run.execution_generation,
            queue_name=queue_routing.queue_name,
        )
        run.run_metadata = {
            **(run.run_metadata or {}),
            "rq_job_id": rq_job_id,
        }
        run.status = RunStatus.QUEUED
        db.commit()
        db.refresh(run)
    except Exception:
        logger.warning(
            "Failed to enqueue run %s — leaving in CREATED state; retry or enqueue manually.",
            run.id,
            exc_info=True,
        )
        _rollback_failed_enqueue(db, run=run, rq_job_id=rq_job_id, redis_client=redis_client)


class RunService:
    """
    Business logic for run creation, queries, deletion, and cancellation.

    Run control transitions live in :class:`RunControlService`. The small
    compatibility wrappers below preserve older service imports while keeping
    one implementation for pause, resume, and restart behavior.
    """

    def __init__(self, db: Session):
        """Initialize service with database session."""
        self.db = db

    def create(self, run_in: RunCreate, redis_client=None) -> tuple[Run, bool]:
        """
        Create a new run and attempt to enqueue it for execution.

        On successful Redis enqueue the run transitions to QUEUED immediately.
        If Redis is unavailable the run is left in CREATED (graceful degradation).

        Args:
            run_in: Run creation data.
            redis_client: Optional Redis client; if None, enqueue is skipped.

        Returns:
            Tuple of (Run instance, is_new) where is_new=True if created, False if idempotent match.

        Raises:
            NotFoundError: If molecule not found.
        """
        molecule = self.db.get(Molecule, run_in.molecule_id)
        if not molecule:
            raise NotFoundError(f"Molecule {run_in.molecule_id} not found")

        n_electrons, n_orbitals = extract_active_space(molecule)
        profile_service = IbmCredentialProfileService(self.db)
        profile_credentials = _resolve_create_profile_credentials(
            run_in=run_in,
            profile_service=profile_service,
        )
        _validate_create_request(
            run_in=run_in,
            molecule=molecule,
            n_electrons=n_electrons,
            n_orbitals=n_orbitals,
            profile_credentials=profile_credentials,
        )

        existing = _find_idempotent_run(self.db, run_in)
        if existing:
            return existing, False

        snapshot_config = run_in.snapshot_config()
        basis_set = normalize_basis_set(run_in.effective_basis_set(molecule_basis_set="sto-3g"))
        credential_profile_id = profile_credentials.profile_id if profile_credentials else None
        credential_profile_name = profile_credentials.profile_name if profile_credentials else None
        _freeze_ibm_backend_selection(
            run_in=run_in,
            n_orbitals=n_orbitals,
            profile_credentials=profile_credentials,
            snapshot_config=snapshot_config,
        )
        _apply_credential_profile_to_snapshot(
            snapshot_config=snapshot_config,
            credential_profile_id=credential_profile_id,
        )

        run = Run(
            molecule_id=run_in.molecule_id,
            basis_set=basis_set,
            algorithm=run_in.algorithm,
            mode=run_in.mode,
            backend_target=run_in.backend_target,
            status=RunStatus.CREATED,
            config_json=snapshot_config,
            client_request_id=run_in.client_request_id,
            credential_profile_id=credential_profile_id,
            credential_profile_name=credential_profile_name,
            run_metadata=_build_run_metadata(run_in, molecule),
            initial_estimate=None,
            latest_estimate=None,
        )

        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        _enqueue_created_run(self.db, run=run, redis_client=redis_client)

        return run, True

    def pause(self, run_id: UUID, redis_client=None) -> Run:
        """Delegate pause behavior to the canonical control service."""
        from app.services.run_control import RunControlService

        return RunControlService(self.db).pause(run_id, redis_client=redis_client)

    def resume(self, run_id: UUID, redis_client=None) -> Run:
        """Delegate resume behavior to the canonical control service."""
        from app.services.run_control import RunControlService

        return RunControlService(self.db).resume(run_id, redis_client=redis_client)

    def restart(self, run_id: UUID, redis_client=None, *, cancel_active: bool = False) -> Run:
        """Return the child from the canonical control-service restart flow."""
        from app.services.run_control import RunControlService

        _, child = RunControlService(self.db).restart(
            run_id,
            cancel_active=cancel_active,
            redis_client=redis_client,
        )
        return child

    def get_by_id(self, run_id: UUID) -> Run:
        """
        Get run by ID.

        Args:
            run_id: Run UUID

        Returns:
            Run instance

        Raises:
            NotFoundError: If run not found
        """
        run = self.db.get(Run, run_id)
        if not run:
            raise NotFoundError(f"Run {run_id} not found")
        return run

    def delete(
        self,
        run_id: UUID,
        redis_client=None,
        *,
        runtime_service_factory: Callable[[IbmRuntimeCredentials], Any] | None = None,
        commit: bool = True,
    ) -> None:
        """
        Delete a run and its dependent artifacts.

        Active queue-local work is cancelled before deletion so the worker does
        not keep executing a run that no longer exists in Postgres. IBM-backed
        runs request a best-effort remote cancellation when an IBM job id is
        available. Restart children are detached so historical reruns survive
        when the original parent row is removed.

        ``commit=False`` lets a composite service include this deletion in its
        own transaction. The default remains a standalone committed operation
        for the API route and compatibility callers.

        Raises:
            NotFoundError: If run not found.
        """
        run = self.db.scalar(select(Run).where(Run.id == run_id).with_for_update())
        if run is None:
            raise NotFoundError(f"Run {run_id} not found")

        if redis_client is not None:
            rq_job_id = (run.run_metadata or {}).get("rq_job_id")
            if rq_job_id:
                queue_service.cancel_queued_job(rq_job_id, redis_client)

        profile_service = IbmCredentialProfileService(self.db)
        _best_effort_cancel_ibm_runtime_job(
            run=run,
            profile_service=profile_service,
            runtime_service_factory=runtime_service_factory,
        )

        restart_children = list(
            self.db.scalars(
                select(Run).where(Run.restarted_from_run_id == run.id).with_for_update()
            )
        )
        for child in restart_children:
            child.restarted_from = None

        self.db.delete(run)
        if commit:
            self.db.commit()
        else:
            self.db.flush()

    def list(
        self,
        molecule_id: UUID | None = None,
        status: RunStatus | None = None,
        backend_target: BackendTarget | None = None,
        converged: bool | None = None,
        chemical_accurate: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Run], int]:
        """
        List runs with optional filtering and pagination.

        Args:
            molecule_id: Optional molecule filter
            status: Optional status filter
            backend_target: Optional backend target filter
            converged: Optional exact convergence filter
            chemical_accurate: Optional exact chemical-accuracy filter
            limit: Maximum results
            offset: Pagination offset

        Returns:
            Tuple of (runs list, total count)
        """
        base_query = select(Run)

        if molecule_id:
            base_query = base_query.where(Run.molecule_id == molecule_id)
        if status:
            base_query = base_query.where(Run.status == status)
        if backend_target:
            base_query = base_query.where(Run.backend_target == backend_target)
        if converged is not None:
            base_query = base_query.where(Run.result.has(converged=converged))

        if chemical_accurate is not None:
            filtered_runs = list(
                self.db.scalars(
                    base_query.options(*_run_summary_load_options()).order_by(Run.created_at.desc())
                ).all()
            )
            matching_runs = [
                run
                for run in filtered_runs
                if resolve_run_chemical_accurate(run) is chemical_accurate
            ]
            return matching_runs[offset : offset + limit], len(matching_runs)

        total = self.db.scalar(select(func.count()).select_from(base_query.subquery()))

        list_query = base_query.options(*_run_summary_load_options())
        runs = list(
            self.db.scalars(
                list_query.order_by(Run.created_at.desc()).limit(limit).offset(offset)
            ).all()
        )

        return runs, int(total or 0)

    def update_status(self, run_id: UUID, new_status: RunStatus) -> Run:
        """
        Update run status.

        Args:
            run_id: Run UUID
            new_status: New status

        Returns:
            Updated run

        Raises:
            NotFoundError: If run not found
        """
        run = self.get_by_id(run_id)
        run.status = new_status

        self.db.commit()
        self.db.refresh(run)

        return run

    def cancel(
        self,
        run_id: UUID,
        redis_client=None,
        *,
        runtime_service_factory: Callable[[IbmRuntimeCredentials], Any] | None = None,
    ) -> Run:
        """
        Cancel a run.

        Idempotent: returns successfully if the run is already CANCELLED.
        For QUEUED runs, attempts to remove the RQ job from Redis.
        SUBMITTED_TO_IBM runs are cancelled in the DB; the worker handles
        the IBM-side cancellation on its next status poll.

        Args:
            run_id: Run UUID.
            redis_client: Optional Redis client for queue cleanup.

        Returns:
            Cancelled (or already-cancelled) run.

        Raises:
            NotFoundError: If run not found.
            ConflictError: If run is in COMPLETED or FAILED state.
        """
        run = self.db.scalar(select(Run).where(Run.id == run_id).with_for_update())
        if run is None:
            raise NotFoundError(f"Run {run_id} not found")
        profile_service = IbmCredentialProfileService(self.db)

        # Idempotent: already cancelled — return 200, not 409. Still try to stop
        # a lingering RQ job so a previous cancellation cannot keep the only
        # worker busy while the database already says CANCELLED.
        if run.status == RunStatus.CANCELLED:
            if redis_client is not None:
                rq_job_id = (run.run_metadata or {}).get("rq_job_id")
                if rq_job_id:
                    queue_service.cancel_queued_job(rq_job_id, redis_client)
            _best_effort_cancel_ibm_runtime_job(
                run=run,
                profile_service=profile_service,
                runtime_service_factory=runtime_service_factory,
            )
            return run

        terminal_states = [RunStatus.COMPLETED, RunStatus.FAILED]
        if run.status in terminal_states:
            raise ConflictError(f"Cannot cancel a run in {run.status} state")

        # For QUEUED/RUNNING runs, remove the queued job or send an RQ stop
        # command if a worker already started it.
        if run.status in {RunStatus.QUEUED, RunStatus.RUNNING} and redis_client is not None:
            rq_job_id = (run.run_metadata or {}).get("rq_job_id")
            if rq_job_id:
                queue_service.cancel_queued_job(rq_job_id, redis_client)

        _best_effort_cancel_ibm_runtime_job(
            run=run,
            profile_service=profile_service,
            runtime_service_factory=runtime_service_factory,
        )

        run.status = RunStatus.CANCELLED
        RunEventService(self.db)._append_event(
            run.id, RunEventType.STATUS_CHANGED, {"status": RunStatus.CANCELLED.value}
        )

        self.db.commit()
        self.db.refresh(run)

        return run
