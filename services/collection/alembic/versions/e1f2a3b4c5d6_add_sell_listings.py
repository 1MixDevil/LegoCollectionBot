"""placeholder — revision already applied on some DBs (sell_listings removed from repo)

Revision ID: e1f2a3b4c5d6
Revises: d4e5f6a7b8c9
Create Date: 2026-05-21

"""
from typing import Sequence, Union

revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # No-op: таблицы sell_listings могли быть созданы вручную на старых инсталляциях.
    pass


def downgrade() -> None:
    pass
