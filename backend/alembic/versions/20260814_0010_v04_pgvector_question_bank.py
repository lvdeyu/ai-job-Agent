"""v0.4 pgvector question bank embedding column

Revision ID: 20260814_0010
Revises: 20260814_0009
Create Date: 2026-08-14
"""

from __future__ import annotations

from alembic import op


revision = "20260814_0010"
down_revision = "20260814_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("ALTER TABLE question_bank_items ADD COLUMN embedding_vector vector(1024)")
    op.execute(
        "CREATE INDEX ix_question_bank_items_embedding_vector "
        "ON question_bank_items USING hnsw (embedding_vector vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_question_bank_items_embedding_vector")
    op.execute("ALTER TABLE question_bank_items DROP COLUMN IF EXISTS embedding_vector")
