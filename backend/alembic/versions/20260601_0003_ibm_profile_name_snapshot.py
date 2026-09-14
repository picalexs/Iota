"""Snapshot IBM profile names on runs.

Revision ID: 20260601_0003
Revises: 20260531_0002
Create Date: 2026-06-01 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]

revision: str = "20260601_0003"
down_revision: str | Sequence[str] | None = "20260531_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add a persistent IBM profile name snapshot to runs."""

    op.add_column(
        "runs", sa.Column("credential_profile_name", sa.String(length=255), nullable=True)
    )
    op.execute(
        """
        UPDATE runs
        SET credential_profile_name = (
            SELECT name
            FROM ibm_credential_profiles
            WHERE ibm_credential_profiles.id = runs.credential_profile_id
        )
        WHERE credential_profile_id IS NOT NULL AND credential_profile_name IS NULL
        """
    )


def downgrade() -> None:
    """Remove the IBM profile name snapshot from runs."""

    op.drop_column("runs", "credential_profile_name")
