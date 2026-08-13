"""v0.1 boss collection

Revision ID: 20260812_0003
Revises: 20260811_0002
Create Date: 2026-08-12
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op


revision = "20260812_0003"
down_revision = "20260811_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_collection_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("keyword", sa.String(length=120), nullable=False),
        sa.Column("city", sa.String(length=80)),
        sa.Column("work_type", sa.String(length=30)),
        sa.Column("limit", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("collection_token", sa.String(length=255), nullable=False),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("error_code", sa.String(length=50)),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("collection_token"),
    )

    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("collection_session_id", sa.String(length=36)),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("source_job_id", sa.String(length=120)),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("company", sa.String(length=180), nullable=False),
        sa.Column("location", sa.String(length=120)),
        sa.Column("salary", sa.String(length=120)),
        sa.Column("experience", sa.String(length=120)),
        sa.Column("education", sa.String(length=120)),
        sa.Column("tags", sa.Text()),
        sa.Column("job_url", sa.String(length=500)),
        sa.Column("description", sa.Text()),
        sa.Column("raw_payload", sa.Text()),
        sa.Column("is_in_pool", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["collection_session_id"], ["job_collection_sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "source_fingerprint", name="uq_jobs_user_source_fp"),
    )


def downgrade() -> None:
    op.drop_table("jobs")
    op.drop_table("job_collection_sessions")
