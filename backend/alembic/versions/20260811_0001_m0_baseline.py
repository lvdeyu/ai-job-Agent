"""m0 baseline

Revision ID: 20260811_0001
Revises:
Create Date: 2026-08-11
"""

from __future__ import annotations

from alembic import op


revision = "20260811_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    pass

