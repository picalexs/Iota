"""Durable worker execution-segment ledger."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.run import Run


class RunExecutionSegment(Base):
    """One worker-owned execution attempt for one run generation."""

    __tablename__ = "run_execution_segments"
    __table_args__ = (
        Index("idx_run_execution_segments_run_generation", "run_id", "execution_generation"),
        Index("idx_run_execution_segments_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    execution_generation: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    rq_job_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    worker_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    worker_finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    duration_seconds: Mapped[float | None] = mapped_column(nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_heartbeat_duration_seconds: Mapped[float | None] = mapped_column(nullable=True)
    termination_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    run: Mapped[Run] = relationship("Run", back_populates="execution_segments")

    def __repr__(self) -> str:
        return (
            "<RunExecutionSegment("
            f"run_id={self.run_id}, generation={self.execution_generation}, "
            f"attempt={self.attempt_number}, status={self.status!r})>"
        )
