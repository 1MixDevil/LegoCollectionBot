from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.core.db import Base
from app.models.associations import user_permission_group

class PermissionName(Base):
    __tablename__ = "permissions_name"
    __table_args__ = {"schema": "auth"}

    id   = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    
    group_id = Column(Integer, ForeignKey("auth.permission_group.id"))  # ВАЖНО: внешний ключ
    group = relationship("PermissionGroup", back_populates="permissions")  # Обратная связь


class PermissionGroup(Base):
    __tablename__ = "permission_group"
    __table_args__ = {"schema": "auth"}

    id   = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)

    permissions = relationship(
        "PermissionName",
        back_populates="group",
        cascade="all, delete-orphan",
    )

    users = relationship(
        "User",
        secondary=user_permission_group,
        back_populates="permission_groups",
    )
