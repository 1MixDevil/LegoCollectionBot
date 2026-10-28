from pydantic import BaseModel, Field


class WatermarkTextRead(BaseModel):
    text: str = ""


class WatermarkTextUpdate(BaseModel):
    text: str = Field("", max_length=200, description="Текст водяного знака на коллажах")


class CollageLimitsRead(BaseModel):
    collage_batch_size: int = 40
    collage_force_batch_above: int = 40
    collage_as_document_above: int = 20
    tierlist_max_member: int = 80
    tierlist_max_premium: int = 150
    tierlist_max_admin: int = 500
    max_serials_per_request: int = 50


class CollageLimitsUpdate(BaseModel):
    collage_batch_size: int | None = Field(None, ge=1, le=500)
    collage_force_batch_above: int | None = Field(None, ge=1, le=2000)
    collage_as_document_above: int | None = Field(None, ge=1, le=2000)
    tierlist_max_member: int | None = Field(None, ge=1, le=5000)
    tierlist_max_premium: int | None = Field(None, ge=1, le=5000)
    tierlist_max_admin: int | None = Field(None, ge=1, le=10000)
    max_serials_per_request: int | None = Field(None, ge=1, le=2000)
