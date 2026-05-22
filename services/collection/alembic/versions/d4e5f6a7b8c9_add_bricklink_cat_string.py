"""add bricklink_cat_string to type_of_collect

Revision ID: d4e5f6a7b8c9
Revises: acff3046c539
Create Date: 2026-05-21

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "acff3046c539"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "type_of_collect",
        sa.Column("bricklink_cat_string", sa.String(), nullable=True),
        schema="figure",
    )


def downgrade() -> None:
    op.drop_column("type_of_collect", "bricklink_cat_string", schema="figure")
