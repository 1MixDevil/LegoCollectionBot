from typing import List, Optional
from pydantic import BaseModel, Field
from app.schemas.permissions_schema import PermissionGroupRead

# Для создания пользователя
class UserCreate(BaseModel):
    username: Optional[str] = Field(None, example="ivan")
    telegram_username: str = Field(..., example="ivan_telegram")

# Для частичного обновления
class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, example="petr")
    telegram_username: Optional[str] = Field(None, example="petr_telegram")

# Для чтения пользователя
class UserRead(BaseModel):
    id: int
    username: Optional[str]
    telegram_username: str
    permission_groups: List[PermissionGroupRead] = []

    class Config:
        orm_mode = True
