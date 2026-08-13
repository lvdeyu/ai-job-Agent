"""v0.2 resume versions

Revision ID: 20260813_0008
Revises: 20260813_0007
Create Date: 2026-08-13
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op


revision = "20260813_0008"
down_revision = "20260813_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "resume_versions",
        sa.Column("source_version_id", sa.String(length=36), nullable=True),
    )
    op.add_column("resume_versions", sa.Column("job_id", sa.String(length=36), nullable=True))
    op.add_column(
        "resume_versions",
        sa.Column("source_type", sa.String(length=30), nullable=False, server_default="uploaded"),
    )
    op.add_column(
        "resume_versions",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_foreign_key(
        "fk_resume_versions_source_version_id",
        "resume_versions",
        "resume_versions",
        ["source_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_resume_versions_job_id",
        "resume_versions",
        "jobs",
        ["job_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_resume_versions_user_job", "resume_versions", ["user_id", "job_id"])
    op.add_column(
        "job_evaluations",
        sa.Column(
            "output_schema_version",
            sa.String(length=30),
            nullable=False,
            server_default="evaluation-json-v1",
        ),
    )


def downgrade() -> None:
    op.drop_column("job_evaluations", "output_schema_version")
    op.drop_index("ix_resume_versions_user_job", table_name="resume_versions")
    op.drop_constraint("fk_resume_versions_job_id", "resume_versions", type_="foreignkey")
    op.drop_constraint(
        "fk_resume_versions_source_version_id",
        "resume_versions",
        type_="foreignkey",
    )
    op.drop_column("resume_versions", "updated_at")
    op.drop_column("resume_versions", "source_type")
    op.drop_column("resume_versions", "job_id")
    op.drop_column("resume_versions", "source_version_id")
