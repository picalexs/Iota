"""
SQLAlchemy model for algorithm-aware quantum runs.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Uuid
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database.base import Base
from app.models.enums import BackendTarget, RunAlgorithm, RunMode, RunStatus
from app.models.run_result import RunResult

if TYPE_CHECKING:
    from app.models.ibm_credential_profile import IbmCredentialProfile
    from app.models.ibm_runtime_job import IbmRuntimeJob
    from app.models.molecule import Molecule
    from app.models.run_checkpoint import RunCheckpoint
    from app.models.run_event import RunEvent
    from app.models.run_execution_segment import RunExecutionSegment

_DELETE_ORPHAN_CASCADE = "all, delete-orphan"


class Run(Base):
    """
    Run model representing a quantum execution configuration and status.

    Stores the immutable configuration snapshot and tracks execution state.
    """

    __tablename__ = "runs"
    __table_args__ = (
        Index("idx_runs_status", "status"),
        Index("idx_runs_molecule_id", "molecule_id"),
        Index("idx_runs_molecule_status", "molecule_id", "status"),
        Index("idx_runs_client_request_id", "client_request_id"),
        Index("idx_runs_restarted_from_run_id", "restarted_from_run_id"),
        Index("idx_runs_credential_profile_id", "credential_profile_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    molecule_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("molecules.id"),
        nullable=False,
    )
    basis_set: Mapped[str] = mapped_column(String(255), nullable=False, server_default="sto-3g")
    algorithm: Mapped[RunAlgorithm | None] = mapped_column(
        SAEnum(
            RunAlgorithm,
            name="run_algorithm",
            native_enum=False,
            validate_strings=True,
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=True,
    )
    mode: Mapped[RunMode | None] = mapped_column(
        SAEnum(
            RunMode,
            name="run_mode",
            native_enum=False,
            validate_strings=True,
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=True,
    )
    backend_target: Mapped[BackendTarget | None] = mapped_column(
        SAEnum(
            BackendTarget,
            name="backend_target",
            native_enum=False,
            validate_strings=True,
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=True,
    )
    status: Mapped[RunStatus] = mapped_column(
        SAEnum(
            RunStatus,
            name="run_status",
            native_enum=False,
            validate_strings=True,
            create_constraint=True,
        ),
        nullable=False,
        default=RunStatus.CREATED,
    )
    config_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
    )  # Full configuration snapshot
    ibm_job_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )  # For IBM Quantum runs
    client_request_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
        unique=True,
    )  # Idempotency key
    execution_generation: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
    restarted_from_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("runs.id"),
        nullable=True,
    )
    credential_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ibm_credential_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    credential_profile_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    versions: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=True,
    )  # Package versions at execution start
    run_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=True,
    )  # Arbitrary metadata attached to the run
    initial_estimate: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=True,
    )  # Initial estimate snapshot generated during validation/create
    latest_estimate: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=True,
    )  # Most recent runtime estimate snapshot emitted by worker telemetry
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    molecule: Mapped[Molecule] = relationship("Molecule", back_populates="runs")
    credential_profile: Mapped[IbmCredentialProfile | None] = relationship(
        "IbmCredentialProfile",
        back_populates="runs",
    )
    restarted_from: Mapped[Run | None] = relationship(
        "Run",
        remote_side=[id],
        back_populates="restarts",
    )
    restarts: Mapped[list[Run]] = relationship("Run", back_populates="restarted_from")
    checkpoints: Mapped[list[RunCheckpoint]] = relationship(
        "RunCheckpoint",
        back_populates="run",
        cascade=_DELETE_ORPHAN_CASCADE,
        order_by="RunCheckpoint.created_at",
    )
    execution_segments: Mapped[list[RunExecutionSegment]] = relationship(
        "RunExecutionSegment",
        back_populates="run",
        cascade=_DELETE_ORPHAN_CASCADE,
        order_by="RunExecutionSegment.attempt_number",
    )
    ibm_runtime_jobs: Mapped[list[IbmRuntimeJob]] = relationship(
        "IbmRuntimeJob",
        back_populates="run",
        cascade=_DELETE_ORPHAN_CASCADE,
        order_by="IbmRuntimeJob.created_at",
    )
    events: Mapped[list[RunEvent]] = relationship(
        "RunEvent",
        back_populates="run",
        cascade=_DELETE_ORPHAN_CASCADE,
        order_by="RunEvent.sequence",
    )
    result: Mapped[RunResult | None] = relationship(
        "RunResult",
        back_populates="run",
        uselist=False,
        cascade=_DELETE_ORPHAN_CASCADE,
    )

    def __repr__(self) -> str:
        return f"<Run(id={self.id}, status={self.status}, molecule_id={self.molecule_id})>"
