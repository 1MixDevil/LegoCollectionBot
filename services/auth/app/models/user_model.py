from sqlalchemy import Column, Integer, String, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.core.db import Base
from app.models.associations import user_permission_group

class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "auth"}

    id                 = Column(Integer, primary_key=True, index=True)
    username           = Column(String, unique=False, nullable=True)
    telegram_username  = Column(String, unique=True, nullable=False)

    settings = relationship("UserSettings", back_populates="user", uselist=False)

    permission_groups = relationship(
        "PermissionGroup",
        secondary=user_permission_group,
        back_populates="users",
    )

class UserSettings(Base):
    __tablename__ = "user_settings"
    __table_args__ = {"schema": "auth"}

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("auth.users.id"), unique=True)

    # Примеры настроек:
    request_price_buy   = Column(Boolean, default=True)   # Запрашивать цену покупки?
    request_price_sale  = Column(Boolean, default=True)   # Запрашивать цену продажи?
    is_seller           = Column(Boolean, default=True)  # Является продавцом?
    show_description    = Column(Boolean, default=True)   # Показывать описание?
    auto_fill_dates     = Column(Boolean, default=True)  # Автоматически проставлять даты?

    # Обратная связь с User
    user = relationship("User", back_populates="settings")
