"""Durable run checkpoints for pause/resume execution."""

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


class RunCheckpoint(Base):
    """Algorithm checkpoint payload tied to a run execution generation."""

    __tablename__ = "run_checkpoints"
    __table_args__ = (
        Index(
            "idx_run_checkpoints_run_generation",
            "run_id",
            "execution_generation",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    execution_generation: Mapped[int] = mapped_column(Integer, nullable=False)
    algorithm: Mapped[str] = mapped_column(String(32), nullable=False)
    checkpoint_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0")
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
    )
    event_sequence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    run: Mapped[Run] = relationship("Run", back_populates="checkpoints")

    def __repr__(self) -> str:
        return (
            "<RunCheckpoint("
            f"run_id={self.run_id}, generation={self.execution_generation}, "
            f"algorithm={self.algorithm!r})>"
        )
