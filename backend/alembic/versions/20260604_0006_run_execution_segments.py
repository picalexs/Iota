"""Persist worker execution segments for restart-safe timing.

Revision ID: 20260604_0006
Revises: 20260603_0005
Create Date: 2026-06-04 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]
from sqlalchemy.dialects import postgresql

revision: str = "20260604_0006"
down_revision: str | Sequence[str] | None = "20260603_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the durable execution-segment ledger."""
    op.create_table(
        "run_execution_segments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("execution_generation", sa.Integer(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("rq_job_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("worker_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("worker_finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_heartbeat_duration_seconds", sa.Float(), nullable=True),
        sa.Column("termination_reason", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_run_execution_segments_run_generation",
        "run_execution_segments",
        ["run_id", "execution_generation"],
        unique=False,
    )
    op.create_index(
        "idx_run_execution_segments_status",
        "run_execution_segments",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the durable execution-segment ledger."""
    op.drop_index("idx_run_execution_segments_status", table_name="run_execution_segments")
    op.drop_index(
        "idx_run_execution_segments_run_generation",
        table_name="run_execution_segments",
    )
    op.drop_table("run_execution_segments")
