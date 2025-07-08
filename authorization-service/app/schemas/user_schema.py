from pydantic import BaseModel, Field

class UserBase(BaseModel):
    username: str = Field(..., example="alice")
    telegram_username: str = Field(..., example="@alice_in_telegram")

class UserCreate(UserBase):
    password: str = Field(..., min_length=6, example="secret123")

class UserRead(UserBase):
    id: int

    class Config:
        orm_mode = True
