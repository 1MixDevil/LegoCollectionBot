from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.core.db import Base
from app.models.associations import user_permission_group

class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "auth"}

    id                 = Column(Integer, primary_key=True, index=True)
    username           = Column(String, unique=True, nullable=False)
    telegram_username  = Column(String, unique=True, nullable=False)

    permission_groups = relationship(
        "PermissionGroup",
        secondary=user_permission_group,
        back_populates="users",
    )
