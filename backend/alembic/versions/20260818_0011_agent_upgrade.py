"""v0.5 agent upgrade tables

Revision ID: 20260818_0011
Revises: 20260814_0010
Create Date: 2026-08-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260818_0011"
down_revision = "20260814_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interview_messages",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(length=36),
            sa.ForeignKey("interview_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "turn_id",
            sa.String(length=36),
            sa.ForeignKey("interview_turns.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("phase", sa.String(length=40), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index("ix_interview_messages_session_id", "interview_messages", ["session_id"])

    op.create_table(
        "resume_project_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "resume_version_id",
            sa.String(length=36),
            sa.ForeignKey("resume_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("project_name", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("responsibility", sa.Text(), nullable=False, server_default=""),
        sa.Column("tech_stack", sa.Text(), nullable=False, server_default=""),
        sa.Column("achievement", sa.Text(), nullable=False, server_default=""),
        sa.Column("risk_points", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("raw_snippet", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index("ix_resume_project_items_resume_version_id", "resume_project_items", ["resume_version_id"])

    op.create_table(
        "user_interview_memory",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            sa.String(length=36),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("skill", sa.String(length=120), nullable=False),
        sa.Column("strength_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("weak_points", sa.Text(), nullable=False, server_default="[]"),
        sa.Column(
            "last_session_id",
            sa.String(length=36),
            sa.ForeignKey("interview_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "job_id", "skill", name="uq_user_job_skill_memory"),
    )

    op.create_table(
        "agent_event_logs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            sa.String(length=36),
            sa.ForeignKey("interview_sessions.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("node_name", sa.String(length=120), nullable=True),
        sa.Column("detail_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index("ix_agent_event_logs_session_id", "agent_event_logs", ["session_id"])


def downgrade() -> None:
    op.drop_table("agent_event_logs")
    op.drop_table("user_interview_memory")
    op.drop_table("resume_project_items")
    op.drop_table("interview_messages")
