"""Persist bounded benchmark execution controls.

Revision ID: 20260606_0009
Revises: 20260606_0008
Create Date: 2026-06-06 00:09:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]

revision: str = "20260606_0009"
down_revision: str | Sequence[str] | None = "20260606_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add bounded execution controls with conservative defaults."""
    op.add_column(
        "benchmark_runs",
        sa.Column("optimization_level", sa.Integer(), nullable=False, server_default="1"),
    )
    op.alter_column("benchmark_runs", "optimization_level", server_default=None)
    op.add_column("benchmark_runs", sa.Column("seed_transpiler", sa.Integer(), nullable=True))
    op.add_column(
        "benchmark_runs",
        sa.Column("dynamical_decoupling", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("benchmark_runs", "dynamical_decoupling", server_default=None)
    op.add_column(
        "benchmark_runs",
        sa.Column("twirling", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("benchmark_runs", "twirling", server_default=None)


def downgrade() -> None:
    """Remove execution controls without changing benchmark rows."""
    op.drop_column("benchmark_runs", "twirling")
    op.drop_column("benchmark_runs", "dynamical_decoupling")
    op.drop_column("benchmark_runs", "seed_transpiler")
    op.drop_column("benchmark_runs", "optimization_level")
