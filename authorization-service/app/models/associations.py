from sqlalchemy import Table, Column, Integer, ForeignKey
from app.core.db import Base

user_permission_group = Table(
    "user_permission_group",
    Base.metadata,
    Column(
        "user_id",
        Integer,
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        primary_key=True
    ),
    Column(
        "group_id",
        Integer,
        ForeignKey("auth.permission_group.id", ondelete="CASCADE"),
        primary_key=True
    ),
    schema="auth"
)
