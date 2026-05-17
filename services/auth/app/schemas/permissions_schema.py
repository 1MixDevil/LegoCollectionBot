from typing import List, Optional
from pydantic import BaseModel, Field

# — Правило доступа —
class PermissionCreate(BaseModel):
    name: str = Field(..., example="read_items")

class PermissionRead(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True

class PermissionRename(BaseModel):
    name: str = Field(..., example="write_items")


# — Группа прав —
class PermissionGroupCreate(BaseModel):
    name: str = Field(..., example="admins")

class PermissionGroupRead(BaseModel):
    id: int
    name: str
    permissions: List[PermissionRead] = []

    class Config:
        orm_mode = True
