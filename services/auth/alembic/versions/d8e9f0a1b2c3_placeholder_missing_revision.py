"""placeholder for missing revision present on some servers

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
Create Date: 2026-05-20

На части окружений в auth.alembic_version уже стоит d8e9f0a1b2c3,
но файла миграции в репозитории не было. Пустая заглушка, чтобы
цепочка Alembic снова сходилась.
"""
from typing import Sequence, Union

revision: str = "d8e9f0a1b2c3"
down_revision: Union[str, None] = "c7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
