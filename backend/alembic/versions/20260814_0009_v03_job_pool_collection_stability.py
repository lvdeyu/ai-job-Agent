"""v0.3 job pool and collection stability

Revision ID: 20260814_0009
Revises: 20260813_0008
Create Date: 2026-08-14
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op


revision = "20260814_0009"
down_revision = "20260813_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("application_status", sa.String(length=30), nullable=True))
    op.add_column("jobs", sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "jobs",
        sa.Column("application_resume_version_id", sa.String(length=36), nullable=True),
    )
    op.add_column("jobs", sa.Column("contact_name", sa.String(length=120), nullable=True))
    op.add_column("jobs", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("status_changed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "fk_jobs_application_resume_version_id",
        "jobs",
        "resume_versions",
        ["application_resume_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute("UPDATE jobs SET application_status = CASE WHEN is_in_pool THEN 'CONFIRMED' ELSE 'NEW' END")
    op.alter_column(
        "jobs",
        "application_status",
        existing_type=sa.String(length=30),
        nullable=False,
        server_default="NEW",
    )

    op.add_column(
        "job_collection_sessions",
        sa.Column("idempotency_key", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "job_collection_sessions",
        sa.Column("extension_version", sa.String(length=30), nullable=True),
    )
    op.add_column(
        "job_collection_sessions",
        sa.Column(
            "adapter_name",
            sa.String(length=50),
            nullable=False,
            server_default="boss-browser",
        ),
    )
    op.add_column(
        "job_collection_sessions",
        sa.Column("adapter_enabled_snapshot", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "job_collection_sessions",
        sa.Column("page_limit", sa.Integer(), nullable=False, server_default="3"),
    )
    op.create_unique_constraint(
        "uq_job_collection_sessions_user_idempotency",
        "job_collection_sessions",
        ["user_id", "idempotency_key"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_job_collection_sessions_user_idempotency",
        "job_collection_sessions",
        type_="unique",
    )
    op.drop_column("job_collection_sessions", "page_limit")
    op.drop_column("job_collection_sessions", "adapter_enabled_snapshot")
    op.drop_column("job_collection_sessions", "adapter_name")
    op.drop_column("job_collection_sessions", "extension_version")
    op.drop_column("job_collection_sessions", "idempotency_key")

    op.drop_constraint("fk_jobs_application_resume_version_id", "jobs", type_="foreignkey")
    op.drop_column("jobs", "status_changed_at")
    op.drop_column("jobs", "notes")
    op.drop_column("jobs", "contact_name")
    op.drop_column("jobs", "application_resume_version_id")
    op.drop_column("jobs", "applied_at")
    op.drop_column("jobs", "application_status")
