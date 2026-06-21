"""add wishlist_items table

Revision ID: f7a8b9c0d1e2
Revises: d4e5f6a7b8c9
Create Date: 2026-06-02

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "wishlist_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("price_estimate", sa.Numeric(10, 2), nullable=True),
        sa.Column("product_url", sa.String(length=500), nullable=True),
        sa.Column("bricklink_id", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="figure",
    )
    op.create_index(
        "ix_figure_wishlist_items_user_id",
        "wishlist_items",
        ["user_id"],
        unique=False,
        schema="figure",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_figure_wishlist_items_user_id",
        table_name="wishlist_items",
        schema="figure",
    )
    op.drop_table("wishlist_items", schema="figure")
