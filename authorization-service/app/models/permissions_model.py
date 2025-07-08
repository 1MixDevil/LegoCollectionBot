from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.core.db import Base
from app.models.associations import user_permission_group

class PermissionName(Base):
    __tablename__ = "permissions_name"
    __table_args__ = {"schema": "auth"}

    id   = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)

class PermissionGroup(Base):
    __tablename__ = "permission_group"
    __table_args__ = {"schema": "auth"}

    id   = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)

    permissions = relationship(
        "PermissionName",
        backref="group",
        cascade="all, delete-orphan",
    )

    users = relationship(
        "User",
        secondary=user_permission_group,
        back_populates="permission_groups",
    )
