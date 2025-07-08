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


permission_group_permissions = Table(
    "permission_group_permissions",
    Base.metadata,
    Column("permission_group_id", Integer, ForeignKey("auth.permission_group.id"), primary_key=True),
    Column("permission_name_id", Integer, ForeignKey("auth.permissions_name.id"), primary_key=True),
    schema="auth",
)