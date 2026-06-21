from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class WishlistItemCreate(BaseModel):
    user_id: int
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    price_estimate: Optional[float] = None
    product_url: Optional[str] = Field(None, max_length=500)
    bricklink_id: Optional[str] = Field(None, max_length=64)


class WishlistItemUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    price_estimate: Optional[float] = None
    product_url: Optional[str] = Field(None, max_length=500)
    bricklink_id: Optional[str] = Field(None, max_length=64)


class WishlistItemRead(BaseModel):
    id: int
    user_id: int
    title: str
    description: Optional[str] = None
    price_estimate: Optional[float] = None
    product_url: Optional[str] = None
    bricklink_id: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        orm_mode = True
