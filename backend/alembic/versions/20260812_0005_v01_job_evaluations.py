"""v0.1 job evaluations

Revision ID: 20260812_0005
Revises: 20260812_0004
Create Date: 2026-08-12
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op


revision = "20260812_0005"
down_revision = "20260812_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_evaluations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("resume_version_id", sa.String(length=36), nullable=False),
        sa.Column("model_provider_id", sa.String(length=36)),
        sa.Column("framework_version", sa.String(length=30), nullable=False),
        sa.Column("prompt_version", sa.String(length=30), nullable=False),
        sa.Column("raw_weighted_score", sa.Float(), nullable=False),
        sa.Column("final_score", sa.Float(), nullable=False),
        sa.Column("recommendation", sa.String(length=30), nullable=False),
        sa.Column("one_sentence_reason", sa.Text(), nullable=False),
        sa.Column("language_gate_triggered", sa.Boolean(), nullable=False),
        sa.Column("dealbreakers_hit", sa.Text(), nullable=False),
        sa.Column("dimensions_json", sa.Text(), nullable=False),
        sa.Column("highlights_json", sa.Text(), nullable=False),
        sa.Column("risks_and_gaps_json", sa.Text(), nullable=False),
        sa.Column("salary_benchmark_json", sa.Text(), nullable=False),
        sa.Column("evidence_json", sa.Text(), nullable=False),
        sa.Column("resume_focus_suggestions_json", sa.Text(), nullable=False),
        sa.Column("honest_gap_statements_json", sa.Text(), nullable=False),
        sa.Column("raw_report_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["model_provider_id"], ["model_provider_configs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["resume_version_id"], ["resume_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_evaluations_user_job", "job_evaluations", ["user_id", "job_id"])


def downgrade() -> None:
    op.drop_index("ix_job_evaluations_user_job", table_name="job_evaluations")
    op.drop_table("job_evaluations")
