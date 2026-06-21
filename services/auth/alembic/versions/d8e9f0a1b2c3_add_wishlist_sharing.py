"""add wishlist sharing settings

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
Create Date: 2026-06-21

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d8e9f0a1b2c3"
down_revision: Union[str, None] = "c7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column(
            "wishlist_public",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        schema="auth",
    )
    op.add_column(
        "user_settings",
        sa.Column("wishlist_share_token", sa.String(length=32), nullable=True),
        schema="auth",
    )
    op.create_index(
        "ix_auth_user_settings_wishlist_share_token",
        "user_settings",
        ["wishlist_share_token"],
        unique=True,
        schema="auth",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_auth_user_settings_wishlist_share_token",
        table_name="user_settings",
        schema="auth",
    )
    op.drop_column("user_settings", "wishlist_share_token", schema="auth")
    op.drop_column("user_settings", "wishlist_public", schema="auth")
