"""Persist benchmark execution settings.

Revision ID: 20260606_0008
Revises: 20260605_0007
Create Date: 2026-06-06 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]

revision: str = "20260606_0008"
down_revision: str | Sequence[str] | None = "20260605_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add non-destructive benchmark execution settings."""
    op.add_column(
        "benchmark_runs",
        sa.Column("shots", sa.Integer(), nullable=False, server_default="1024"),
    )
    op.alter_column("benchmark_runs", "shots", server_default=None)
    op.add_column(
        "benchmark_runs",
        sa.Column("selected_aer_method", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "benchmark_runs",
        sa.Column("selected_device", sa.String(length=16), nullable=True),
    )


def downgrade() -> None:
    """Remove benchmark execution settings without changing benchmark rows."""
    op.drop_column("benchmark_runs", "selected_device")
    op.drop_column("benchmark_runs", "selected_aer_method")
    op.drop_column("benchmark_runs", "shots")
