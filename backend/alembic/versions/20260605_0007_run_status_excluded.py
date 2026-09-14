"""Add EXCLUDED run status.

Revision ID: 20260605_0007
Revises: 20260604_0006
Create Date: 2026-06-05 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]

revision: str = "20260605_0007"
down_revision: str | Sequence[str] | None = "20260604_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RUN_STATUS_VALUES_WITH_EXCLUDED = (
    "CREATED",
    "QUEUED",
    "RUNNING",
    "PAUSING",
    "PAUSED",
    "COMPLETED",
    "FAILED",
    "CANCELLED",
    "EXCLUDED",
    "SUBMITTED_TO_IBM",
)

RUN_STATUS_VALUES_WITHOUT_EXCLUDED = (
    "CREATED",
    "QUEUED",
    "RUNNING",
    "PAUSING",
    "PAUSED",
    "COMPLETED",
    "FAILED",
    "CANCELLED",
    "SUBMITTED_TO_IBM",
)


def _recreate_check_constraint(values: tuple[str, ...]) -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return
    op.execute(sa.text('ALTER TABLE "runs" DROP CONSTRAINT IF EXISTS "run_status"'))
    quoted = ", ".join(f"'{value}'" for value in values)
    op.create_check_constraint("run_status", "runs", f"status IN ({quoted})")


def upgrade() -> None:
    """Allow the EXCLUDED terminal run status."""
    _recreate_check_constraint(RUN_STATUS_VALUES_WITH_EXCLUDED)


def downgrade() -> None:
    """Revert to the run status set without EXCLUDED."""
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.execute(sa.text("UPDATE runs SET status = 'FAILED' WHERE status = 'EXCLUDED'"))
    _recreate_check_constraint(RUN_STATUS_VALUES_WITHOUT_EXCLUDED)
