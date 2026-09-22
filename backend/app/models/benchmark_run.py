"""SQLAlchemy model for persisted benchmark batches."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Float, Index, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base


class BenchmarkRun(Base):
    """Persisted benchmark workspace snapshot and row results."""

    __tablename__ = "benchmark_runs"
    __table_args__ = (
        Index("idx_benchmark_runs_updated_at", "updated_at"),
        Index("idx_benchmark_runs_created_at", "created_at"),
        Index("uq_benchmark_runs_campaign_id", "campaign_id", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    campaign_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    registration_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    campaign_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
        default=dict,
    )
    selected_molecule_keys: Mapped[list[str]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
        default=list,
    )
    selected_algorithms: Mapped[list[str]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
        default=list,
    )
    selected_basis: Mapped[str] = mapped_column(String(255), nullable=False, default="sto-3g")
    selected_backend_mode: Mapped[str] = mapped_column(String(64), nullable=False)
    selected_backend_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    shots: Mapped[int] = mapped_column(nullable=False, default=1024)
    chemical_accuracy_ha: Mapped[float] = mapped_column(Float, nullable=False, default=1.6e-3)
    custom_molecules: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
        default=list,
    )
    entries: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
        default=list,
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

    def __repr__(self) -> str:
        return f"<BenchmarkRun(id={self.id}, name={self.name!r})>"
