"""grant permanent admin to owner telegram id

Revision ID: c7d8e9f0a1b2
Revises: b1c2d3e4f5a6
Create Date: 2026-05-18

"""
from typing import Sequence, Union

from alembic import op

revision: str = "c7d8e9f0a1b2"
down_revision: Union[str, None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OWNER_TELEGRAM_ID = "539686459"


def upgrade() -> None:
    op.execute(
        f"""
        UPDATE auth.users
        SET role = 'admin'
        WHERE telegram_username = '{OWNER_TELEGRAM_ID}'
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        UPDATE auth.users
        SET role = 'member'
        WHERE telegram_username = '{OWNER_TELEGRAM_ID}'
        """
    )
