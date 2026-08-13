"""v0.1 interviews

Revision ID: 20260813_0007
Revises: 20260812_0006
Create Date: 2026-08-13
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op


revision = "20260813_0007"
down_revision = "20260812_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "question_bank_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("external_id", sa.String(length=120), nullable=False),
        sa.Column("locale", sa.String(length=20), nullable=False),
        sa.Column("domain", sa.String(length=80), nullable=False),
        sa.Column("question_type", sa.String(length=40), nullable=False),
        sa.Column("difficulty", sa.String(length=20), nullable=False),
        sa.Column("skill_tags_json", sa.Text(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("reference_answer", sa.Text(), nullable=False),
        sa.Column("scoring_rubric_json", sa.Text(), nullable=False),
        sa.Column("followup_suggestions_json", sa.Text(), nullable=False),
        sa.Column("embedding_text", sa.Text(), nullable=False),
        sa.Column("source_json", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding", sa.Text()),
        sa.Column("embedding_model", sa.String(length=120)),
        sa.Column("source_file", sa.String(length=500), nullable=False),
        sa.Column("source_line", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id", name="uq_question_bank_external_id"),
    )
    op.create_index("ix_question_bank_domain", "question_bank_items", ["domain"])
    op.create_index("ix_question_bank_type", "question_bank_items", ["question_type"])

    op.create_table(
        "interview_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("resume_version_id", sa.String(length=36), nullable=False),
        sa.Column("job_evaluation_id", sa.String(length=36)),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("retrieval_mode", sa.String(length=40), nullable=False),
        sa.Column("scoring_mode", sa.String(length=40), nullable=False),
        sa.Column("max_questions", sa.Integer(), nullable=False),
        sa.Column("main_questions_answered", sa.Integer(), nullable=False),
        sa.Column("report_json", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["job_evaluation_id"], ["job_evaluations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resume_version_id"], ["resume_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_interview_sessions_user_job", "interview_sessions", ["user_id", "job_id"])

    op.create_table(
        "interview_turns",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("question_bank_item_id", sa.String(length=36)),
        sa.Column("parent_turn_id", sa.String(length=36)),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("question_type", sa.String(length=40), nullable=False),
        sa.Column("skill_tags_json", sa.Text(), nullable=False),
        sa.Column("reference_answer_snapshot", sa.Text(), nullable=False),
        sa.Column("scoring_rubric_json", sa.Text(), nullable=False),
        sa.Column("followup_suggestions_json", sa.Text(), nullable=False),
        sa.Column("is_followup", sa.Boolean(), nullable=False),
        sa.Column("followup_depth", sa.Integer(), nullable=False),
        sa.Column("answer_text", sa.Text()),
        sa.Column("score", sa.Float()),
        sa.Column("feedback", sa.Text()),
        sa.Column("evidence_json", sa.Text()),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("answered_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["parent_turn_id"], ["interview_turns.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["question_bank_item_id"], ["question_bank_items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["interview_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_interview_turns_session", "interview_turns", ["session_id", "turn_index"])


def downgrade() -> None:
    op.drop_index("ix_interview_turns_session", table_name="interview_turns")
    op.drop_table("interview_turns")
    op.drop_index("ix_interview_sessions_user_job", table_name="interview_sessions")
    op.drop_table("interview_sessions")
    op.drop_index("ix_question_bank_type", table_name="question_bank_items")
    op.drop_index("ix_question_bank_domain", table_name="question_bank_items")
    op.drop_table("question_bank_items")
