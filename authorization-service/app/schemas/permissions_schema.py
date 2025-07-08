from pydantic import BaseModel, Field

class PermissionCreate(BaseModel):
    name: str = Field(..., example="read_items")

class PermissionRead(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True
