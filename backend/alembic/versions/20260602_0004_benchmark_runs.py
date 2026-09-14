"""Persist benchmark batches.

Revision ID: 20260602_0004
Revises: 20260601_0003
Create Date: 2026-06-02 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]
from sqlalchemy.dialects import postgresql

revision: str = "20260602_0004"
down_revision: str | Sequence[str] | None = "20260601_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _json_type() -> sa.TypeEngine:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def upgrade() -> None:
    """Create persisted benchmark batch table."""

    op.create_table(
        "benchmark_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("selected_molecule_keys", _json_type(), nullable=False),
        sa.Column("selected_algorithms", _json_type(), nullable=False),
        sa.Column("selected_basis", sa.String(length=255), nullable=False),
        sa.Column("selected_backend_mode", sa.String(length=64), nullable=False),
        sa.Column("selected_backend_name", sa.String(length=255), nullable=True),
        sa.Column("chemical_accuracy_ha", sa.Float(), nullable=False),
        sa.Column("custom_molecules", _json_type(), nullable=False),
        sa.Column("entries", _json_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_benchmark_runs_created_at",
        "benchmark_runs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "idx_benchmark_runs_updated_at",
        "benchmark_runs",
        ["updated_at"],
        unique=False,
    )


def downgrade() -> None:
    """Drop persisted benchmark batch table."""

    op.drop_index("idx_benchmark_runs_updated_at", table_name="benchmark_runs")
    op.drop_index("idx_benchmark_runs_created_at", table_name="benchmark_runs")
    op.drop_table("benchmark_runs")
