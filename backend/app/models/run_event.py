"""
SQLAlchemy model for run events.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, UniqueConstraint, Uuid
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database.base import Base
from app.models.enums import RunEventType

if TYPE_CHECKING:
    from app.models.run import Run


class RunEvent(Base):
    """
    RunEvent model representing an append-only event log for runs.

    Events are never updated or deleted - they form an immutable audit trail.
    """

    __tablename__ = "run_events"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence", name="uq_run_events_run_id_sequence"),
        Index("idx_run_events_run_id", "run_id"),
        Index("idx_run_events_type", "type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)  # Per-run sequence number
    type: Mapped[RunEventType] = mapped_column(
        SAEnum(
            RunEventType,
            name="run_event_type",
            native_enum=False,
            validate_strings=True,
            create_constraint=True,
            # Use enum .value ("status_changed") not .name ("STATUS_CHANGED")
            # so SQLAlchemy matches what the worker inserts via raw SQL.
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )  # Event type
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
    )  # Event-specific data
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    run: Mapped[Run] = relationship("Run", back_populates="events")

    def __repr__(self) -> str:
        return (
            f"<RunEvent(id={self.id}, run_id={self.run_id}, "
            f"sequence={self.sequence}, type={self.type})>"
        )
