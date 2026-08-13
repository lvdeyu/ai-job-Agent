"""model provider network mode

Revision ID: 20260812_0004
Revises: 20260812_0003
Create Date: 2026-08-12
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op


revision = "20260812_0004"
down_revision = "20260812_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "model_provider_configs",
        sa.Column("network_mode", sa.String(length=30), nullable=False, server_default="auto"),
    )
    op.add_column("model_provider_configs", sa.Column("proxy_url", sa.String(length=255)))
    op.alter_column("model_provider_configs", "network_mode", server_default=None)


def downgrade() -> None:
    op.drop_column("model_provider_configs", "proxy_url")
    op.drop_column("model_provider_configs", "network_mode")
