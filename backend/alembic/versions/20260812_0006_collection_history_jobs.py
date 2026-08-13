"""v0.1 collection history jobs

Revision ID: 20260812_0006
Revises: 20260812_0005
Create Date: 2026-08-12
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op


revision = "20260812_0006"
down_revision = "20260812_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "job_collection_sessions",
        sa.Column("accepted_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "job_collection_sessions",
        sa.Column("created_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "job_collection_sessions",
        sa.Column("duplicated_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "job_collection_sessions",
        sa.Column("filtered_count", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "job_collection_session_jobs",
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("was_duplicate", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["job_collection_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("session_id", "job_id"),
        sa.UniqueConstraint("session_id", "job_id", name="uq_job_collection_session_jobs"),
    )

    op.execute(
        """
        INSERT INTO job_collection_session_jobs (session_id, job_id, position, was_duplicate)
        SELECT collection_session_id, id, 0, false
        FROM jobs
        WHERE collection_session_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE job_collection_sessions
        SET created_count = (
            SELECT COUNT(*)
            FROM jobs
            WHERE jobs.collection_session_id = job_collection_sessions.id
        ),
        accepted_count = (
            SELECT COUNT(*)
            FROM jobs
            WHERE jobs.collection_session_id = job_collection_sessions.id
        )
        """
    )


def downgrade() -> None:
    op.drop_table("job_collection_session_jobs")
    op.drop_column("job_collection_sessions", "filtered_count")
    op.drop_column("job_collection_sessions", "duplicated_count")
    op.drop_column("job_collection_sessions", "created_count")
    op.drop_column("job_collection_sessions", "accepted_count")
