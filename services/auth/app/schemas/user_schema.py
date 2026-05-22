from typing import List, Literal, Optional
from pydantic import BaseModel, Field
from app.schemas.permissions_schema import PermissionGroupRead

UserRole = Literal["admin", "member", "premium"]

# Для создания пользователя
class UserCreate(BaseModel):
    username: Optional[str] = Field(None, example="ivan")
    telegram_username: str = Field(..., example="ivan_telegram")
    role: Optional[UserRole] = Field(None, example="member")

# Для частичного обновления
class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, example="petr")
    telegram_username: Optional[str] = Field(None, example="petr_telegram")
    role: Optional[UserRole] = None


class UserRoleUpdate(BaseModel):
    role: UserRole

# Для чтения пользователя
class UserRead(BaseModel):
    id: int
    username: Optional[str]
    telegram_username: str
    role: str = "member"
    permission_groups: List[PermissionGroupRead] = []

    class Config:
        orm_mode = True

#Для добавления настроек
class UserSettingsUpdate(BaseModel):
    user_id: int
    request_price_buy:  Optional[bool]  = Field(None, example=False)   # Запрашивать цену покупки?
    request_price_sale: Optional[bool]  = Field(None, example=False)   # Запрашивать цену продажи?
    is_seller:          Optional[bool]  = Field(None, example=False)  # Является продавцом?
    show_description:   Optional[bool]  = Field(None, example=False) # Показывать описание?
    auto_fill_dates:    Optional[bool]  = Field(None, example=False)  # Автоматически проставлять даты?

    class Config:
        orm_mode = True



class UserSettingsRead(UserSettingsUpdate):
    id: int

    class Config:
        orm_mode = True
