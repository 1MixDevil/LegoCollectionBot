from pydantic import BaseModel, Field


class WatermarkTextRead(BaseModel):
    text: str = ""


class WatermarkTextUpdate(BaseModel):
    text: str = Field("", max_length=200, description="Текст водяного знака на коллажах")
