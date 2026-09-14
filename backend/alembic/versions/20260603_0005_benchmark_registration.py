"""Add campaign registration identity to benchmark batches.

Revision ID: 20260603_0005
Revises: 20260602_0004
Create Date: 2026-06-03 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]
from sqlalchemy.dialects import postgresql

revision: str = "20260603_0005"
down_revision: str | Sequence[str] | None = "20260602_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _json_type() -> sa.TypeEngine:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def upgrade() -> None:
    """Add immutable campaign registration metadata."""

    op.add_column("benchmark_runs", sa.Column("campaign_id", sa.String(length=255)))
    op.add_column("benchmark_runs", sa.Column("registration_digest", sa.String(length=64)))
    op.add_column(
        "benchmark_runs",
        sa.Column("campaign_metadata", _json_type(), nullable=False, server_default="{}"),
    )
    op.alter_column("benchmark_runs", "campaign_metadata", server_default=None)
    op.create_index(
        "uq_benchmark_runs_campaign_id",
        "benchmark_runs",
        ["campaign_id"],
        unique=True,
    )


def downgrade() -> None:
    """Remove campaign registration metadata."""

    op.drop_index("uq_benchmark_runs_campaign_id", table_name="benchmark_runs")
    op.drop_column("benchmark_runs", "campaign_metadata")
    op.drop_column("benchmark_runs", "registration_digest")
    op.drop_column("benchmark_runs", "campaign_id")
