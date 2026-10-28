from sqlalchemy import Column, String

from app.core.db import Base


class BotSetting(Base):
    """Глобальные настройки бота (ключ → значение)."""

    __tablename__ = "bot_settings"
    __table_args__ = {"schema": "auth"}

    key = Column(String, primary_key=True)
    value = Column(String, nullable=False, default="")
