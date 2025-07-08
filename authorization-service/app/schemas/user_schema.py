from pydantic import BaseModel, Field

class UserBase(BaseModel):
    telegram_username: str = Field(..., example="@alice_in_telegram")

class UserCreate(UserBase):
    telegram_username: str = Field(..., min_length=6, example="secret123")

class UserRead(UserBase):
    id: int

    class Config:
        orm_mode = True
