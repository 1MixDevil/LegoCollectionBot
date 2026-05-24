"""add user role column

Revision ID: b1c2d3e4f5a6
Revises: 57d5ffd62a20
Create Date: 2026-05-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "57d5ffd62a20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", sa.String(), nullable=False, server_default="member"),
        schema="auth",
    )
    op.create_index(
        "ix_auth_users_role",
        "users",
        ["role"],
        unique=False,
        schema="auth",
    )


def downgrade() -> None:
    op.drop_index("ix_auth_users_role", table_name="users", schema="auth")
    op.drop_column("users", "role", schema="auth")
