"""Squashed initial schema for the current database state.

Revision ID: 20260511_0001
Revises:
Create Date: 2026-05-11 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260511_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RUN_STATUS_VALUES = (
    "CREATED",
    "QUEUED",
    "RUNNING",
    "COMPLETED",
    "FAILED",
    "CANCELLED",
    "SUBMITTED_TO_IBM",
)

RUN_ALGORITHM_VALUES = ("vqe", "qse", "kqd", "qfd", "sqd", "skqd")

RUN_MODE_VALUES = ("easy", "advanced")

BACKEND_TARGET_VALUES = ("statevector", "aer_simulator", "ibm_runtime")

RUN_EVENT_TYPE_VALUES = (
    "status_changed",
    "iteration_update",
    "error",
    "result",
    "estimate_updated",
    "ibm_job_submitted",
    "ibm_status_poll",
)


def upgrade() -> None:
    """Create all tables in their final schema state."""

    # --- molecules -----------------------------------------------------------
    op.create_table(
        "molecules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("atoms", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("charge", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("multiplicity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("active_space", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("pubchem_cid", sa.Integer(), nullable=True),
        sa.Column("iupac_name", sa.String(length=512), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("synonyms", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("smiles", sa.String(length=512), nullable=True),
        sa.Column("inchi", sa.Text(), nullable=True),
        sa.Column("inchi_key", sa.String(length=27), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_molecules_name_non_empty"),
        sa.CheckConstraint("multiplicity >= 1", name="ck_molecules_multiplicity_ge_1"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="molecules_name_key"),
        sa.UniqueConstraint("pubchem_cid", name="molecules_pubchem_cid_key"),
    )

    # --- runs ----------------------------------------------------------------
    op.create_table(
        "runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("molecule_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("basis_set", sa.String(length=255), nullable=False, server_default="sto-3g"),
        sa.Column(
            "algorithm",
            sa.Enum(
                *RUN_ALGORITHM_VALUES,
                name="run_algorithm",
                native_enum=False,
                validate_strings=True,
                create_constraint=True,
            ),
            nullable=True,
        ),
        sa.Column(
            "mode",
            sa.Enum(
                *RUN_MODE_VALUES,
                name="run_mode",
                native_enum=False,
                validate_strings=True,
                create_constraint=True,
            ),
            nullable=True,
        ),
        sa.Column(
            "backend_target",
            sa.Enum(
                *BACKEND_TARGET_VALUES,
                name="backend_target",
                native_enum=False,
                validate_strings=True,
                create_constraint=True,
            ),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.Enum(
                *RUN_STATUS_VALUES,
                name="run_status",
                native_enum=False,
                validate_strings=True,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("config_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("ibm_job_id", sa.String(length=255), nullable=True),
        sa.Column("client_request_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("versions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("initial_estimate", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("latest_estimate", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["molecule_id"], ["molecules.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_request_id"),
    )
    op.create_index("idx_runs_status", "runs", ["status"], unique=False)
    op.create_index("idx_runs_molecule_id", "runs", ["molecule_id"], unique=False)
    op.create_index("idx_runs_client_request_id", "runs", ["client_request_id"], unique=False)
    op.create_index("idx_runs_molecule_status", "runs", ["molecule_id", "status"], unique=False)

    # --- run_results ---------------------------------------------------------
    op.create_table(
        "run_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("energy", sa.Float(), nullable=False),
        sa.Column("iterations", sa.Integer(), nullable=False),
        sa.Column("optimal_parameters", sa.JSON(), nullable=False),
        sa.Column("converged", sa.Boolean(), nullable=False),
        sa.Column("algorithm_metrics", sa.JSON(), nullable=True),
        sa.Column("raw_result", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id"),
    )
    op.create_index("idx_run_results_run_id", "run_results", ["run_id"], unique=False)

    # --- run_events ----------------------------------------------------------
    op.create_table(
        "run_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                *RUN_EVENT_TYPE_VALUES,
                name="run_event_type",
                native_enum=False,
                validate_strings=True,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "sequence", name="uq_run_events_run_id_sequence"),
    )
    op.create_index("idx_run_events_run_id", "run_events", ["run_id"], unique=False)
    op.create_index("idx_run_events_type", "run_events", ["type"], unique=False)


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table("run_events")
    op.drop_table("run_results")
    op.drop_table("runs")
    op.drop_table("molecules")
