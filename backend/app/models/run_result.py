"""
SQLAlchemy model for run results.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.run import Run


class RunResult(Base):
    """
    RunResult model representing the final output of a completed run.

    Separated from Run to keep the runs table narrow and handle large results.
    """

    __tablename__ = "run_results"
    __table_args__ = (Index("idx_run_results_run_id", "run_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    energy: Mapped[float] = mapped_column(Float, nullable=False)  # Ground-state energy in Hartree
    final_energy: Mapped[float | None] = mapped_column(Float, nullable=True)
    best_observed_energy: Mapped[float | None] = mapped_column(Float, nullable=True)
    reported_energy: Mapped[float | None] = mapped_column(Float, nullable=True)
    reported_energy_source: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reference_energy: Mapped[float | None] = mapped_column(Float, nullable=True)
    reference_basis: Mapped[str | None] = mapped_column(String(255), nullable=True)
    signed_error: Mapped[float | None] = mapped_column(Float, nullable=True)
    iterations: Mapped[int] = mapped_column(Integer, nullable=False)  # Total optimizer iterations
    optimal_parameters: Mapped[list[float]] = mapped_column(
        JSON, nullable=False
    )  # Final variational parameters
    converged: Mapped[bool] = mapped_column(Boolean, nullable=False)  # Optimizer convergence flag
    algorithm_metrics: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )  # Normalized algorithm diagnostics
    raw_result: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )  # Full Qiskit result for debugging
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    run: Mapped[Run] = relationship("Run", back_populates="result")

    def __repr__(self) -> str:
        return f"<RunResult(id={self.id}, run_id={self.run_id}, energy={self.energy})>"
