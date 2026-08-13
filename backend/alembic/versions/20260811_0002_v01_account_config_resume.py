"""v0.1 account config resume

Revision ID: 20260811_0002
Revises: 20260811_0001
Create Date: 2026-08-11
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op


revision = "20260811_0002"
down_revision = "20260811_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "user_profiles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("target_role", sa.String(length=120)),
        sa.Column("salary_min", sa.Integer()),
        sa.Column("salary_max", sa.Integer()),
        sa.Column("cities", sa.String(length=255)),
        sa.Column("work_type", sa.String(length=30)),
        sa.Column("deal_breakers", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_user_profiles_user_id"),
    )

    op.create_table(
        "model_provider_configs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("api_key", sa.String(length=512), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("base_url", sa.String(length=255)),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "provider", name="uq_model_provider_user_provider"),
    )

    op.create_table(
        "resume_files",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("file_ext", sa.String(length=10), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("content_type", sa.String(length=120)),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "resume_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("resume_file_id", sa.String(length=36), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("structured_summary", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["resume_file_id"], ["resume_files.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("resume_versions")
    op.drop_table("resume_files")
    op.drop_table("model_provider_configs")
    op.drop_table("user_profiles")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
