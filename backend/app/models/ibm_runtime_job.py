"""Persisted IBM Runtime primitive jobs observed during worker execution."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.run import Run


class IbmRuntimeJob(Base):
    """Non-secret IBM Runtime job metadata for reattachment and audit."""

    __tablename__ = "ibm_runtime_jobs"
    __table_args__ = (
        Index("idx_ibm_runtime_jobs_run_id", "run_id"),
        Index("idx_ibm_runtime_jobs_job_id", "ibm_job_id"),
        Index("idx_ibm_runtime_jobs_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    execution_generation: Mapped[int] = mapped_column(Integer, nullable=False)
    ibm_job_id: Mapped[str] = mapped_column(String(255), nullable=False)
    primitive_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    backend_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    job_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=True,
    )
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

    run: Mapped[Run] = relationship("Run", back_populates="ibm_runtime_jobs")

    def __repr__(self) -> str:
        return f"<IbmRuntimeJob(run_id={self.run_id}, ibm_job_id={self.ibm_job_id!r})>"
