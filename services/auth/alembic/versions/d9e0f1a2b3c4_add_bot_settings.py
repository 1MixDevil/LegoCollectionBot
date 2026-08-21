"""add bot_settings table for collage watermark

Revision ID: d9e0f1a2b3c4
Revises: c7d8e9f0a1b2
Create Date: 2026-08-21

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d9e0f1a2b3c4"
down_revision: Union[str, None] = "c7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bot_settings",
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("value", sa.String(), nullable=False, server_default=""),
        sa.PrimaryKeyConstraint("key"),
        schema="auth",
    )
    op.execute(
        """
        INSERT INTO auth.bot_settings (key, value)
        VALUES ('collage_watermark_text', '')
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("bot_settings", schema="auth")
