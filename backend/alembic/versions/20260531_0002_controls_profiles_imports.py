"""Add run controls, checkpoints, IBM profiles, and result provenance.

Revision ID: 20260531_0002
Revises: 20260511_0001
Create Date: 2026-05-31 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]
from sqlalchemy.dialects import postgresql

revision: str = "20260531_0002"
down_revision: str | Sequence[str] | None = "20260511_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RUN_STATUS_VALUES = (
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

RUN_EVENT_TYPE_VALUES = (
    "status_changed",
    "iteration_update",
    "error",
    "result",
    "estimate_updated",
    "ibm_job_submitted",
    "ibm_status_poll",
    "control_requested",
    "checkpoint_saved",
    "resume_enqueued",
    "restart_created",
)


def _recreate_check_constraint(
    table_name: str,
    column_name: str,
    constraint_name: str,
    values: tuple[str, ...],
) -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return
    op.execute(sa.text(f'ALTER TABLE "{table_name}" DROP CONSTRAINT IF EXISTS "{constraint_name}"'))
    quoted = ", ".join(f"'{value}'" for value in values)
    op.create_check_constraint(
        constraint_name,
        table_name,
        f"{column_name} IN ({quoted})",
    )


def upgrade() -> None:
    """Apply schema changes."""

    _recreate_check_constraint("runs", "status", "run_status", RUN_STATUS_VALUES)
    _recreate_check_constraint("run_events", "type", "run_event_type", RUN_EVENT_TYPE_VALUES)

    op.create_table(
        "ibm_credential_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("encrypted_token", sa.Text(), nullable=False),
        sa.Column("encrypted_crn", sa.Text(), nullable=False),
        sa.Column("channel", sa.String(length=64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("token_hint", sa.String(length=32), nullable=True),
        sa.Column("crn_hint", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="ibm_credential_profiles_name_key"),
    )
    op.create_index(
        "idx_ibm_credential_profiles_active",
        "ibm_credential_profiles",
        ["active"],
        unique=False,
    )
    op.create_index(
        "idx_ibm_credential_profiles_name",
        "ibm_credential_profiles",
        ["name"],
        unique=False,
    )

    op.add_column(
        "runs",
        sa.Column("execution_generation", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "runs",
        sa.Column("restarted_from_run_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "runs",
        sa.Column("credential_profile_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_runs_restarted_from_run_id_runs",
        "runs",
        "runs",
        ["restarted_from_run_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_runs_credential_profile_id_ibm_profiles",
        "runs",
        "ibm_credential_profiles",
        ["credential_profile_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_runs_restarted_from_run_id",
        "runs",
        ["restarted_from_run_id"],
        unique=False,
    )
    op.create_index(
        "idx_runs_credential_profile_id",
        "runs",
        ["credential_profile_id"],
        unique=False,
    )

    op.create_table(
        "run_checkpoints",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("execution_generation", sa.Integer(), nullable=False),
        sa.Column("algorithm", sa.String(length=32), nullable=False),
        sa.Column("checkpoint_version", sa.String(length=32), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("event_sequence", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_run_checkpoints_run_generation",
        "run_checkpoints",
        ["run_id", "execution_generation"],
        unique=False,
    )

    op.create_table(
        "ibm_runtime_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("execution_generation", sa.Integer(), nullable=False),
        sa.Column("ibm_job_id", sa.String(length=255), nullable=False),
        sa.Column("primitive_type", sa.String(length=64), nullable=True),
        sa.Column("backend_name", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_ibm_runtime_jobs_run_id", "ibm_runtime_jobs", ["run_id"], unique=False)
    op.create_index(
        "idx_ibm_runtime_jobs_job_id",
        "ibm_runtime_jobs",
        ["ibm_job_id"],
        unique=False,
    )
    op.create_index("idx_ibm_runtime_jobs_status", "ibm_runtime_jobs", ["status"], unique=False)

    op.add_column("run_results", sa.Column("final_energy", sa.Float(), nullable=True))
    op.add_column("run_results", sa.Column("best_observed_energy", sa.Float(), nullable=True))
    op.add_column("run_results", sa.Column("reported_energy", sa.Float(), nullable=True))
    op.add_column(
        "run_results", sa.Column("reported_energy_source", sa.String(length=128), nullable=True)
    )
    op.add_column("run_results", sa.Column("reference_energy", sa.Float(), nullable=True))
    op.add_column("run_results", sa.Column("reference_basis", sa.String(length=255), nullable=True))
    op.add_column("run_results", sa.Column("signed_error", sa.Float(), nullable=True))


def downgrade() -> None:
    """Revert schema changes."""

    op.drop_column("run_results", "signed_error")
    op.drop_column("run_results", "reference_basis")
    op.drop_column("run_results", "reference_energy")
    op.drop_column("run_results", "reported_energy_source")
    op.drop_column("run_results", "reported_energy")
    op.drop_column("run_results", "best_observed_energy")
    op.drop_column("run_results", "final_energy")

    op.drop_index("idx_ibm_runtime_jobs_status", table_name="ibm_runtime_jobs")
    op.drop_index("idx_ibm_runtime_jobs_job_id", table_name="ibm_runtime_jobs")
    op.drop_index("idx_ibm_runtime_jobs_run_id", table_name="ibm_runtime_jobs")
    op.drop_table("ibm_runtime_jobs")

    op.drop_index("idx_run_checkpoints_run_generation", table_name="run_checkpoints")
    op.drop_table("run_checkpoints")

    op.drop_index("idx_runs_credential_profile_id", table_name="runs")
    op.drop_index("idx_runs_restarted_from_run_id", table_name="runs")
    op.drop_constraint("fk_runs_credential_profile_id_ibm_profiles", "runs", type_="foreignkey")
    op.drop_constraint("fk_runs_restarted_from_run_id_runs", "runs", type_="foreignkey")
    op.drop_column("runs", "credential_profile_id")
    op.drop_column("runs", "restarted_from_run_id")
    op.drop_column("runs", "execution_generation")

    op.drop_index("idx_ibm_credential_profiles_name", table_name="ibm_credential_profiles")
    op.drop_index("idx_ibm_credential_profiles_active", table_name="ibm_credential_profiles")
    op.drop_table("ibm_credential_profiles")

    _recreate_check_constraint(
        "runs",
        "status",
        "run_status",
        (
            "CREATED",
            "QUEUED",
            "RUNNING",
            "COMPLETED",
            "FAILED",
            "CANCELLED",
            "SUBMITTED_TO_IBM",
        ),
    )
    _recreate_check_constraint(
        "run_events",
        "type",
        "run_event_type",
        (
            "status_changed",
            "iteration_update",
            "error",
            "result",
            "estimate_updated",
            "ibm_job_submitted",
            "ibm_status_poll",
        ),
    )
