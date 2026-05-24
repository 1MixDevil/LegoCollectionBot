from typing import List, Optional
from datetime import date
from pydantic import BaseModel, Field


# — CollectType —

class CollectTypeCreate(BaseModel):
    name: str = Field(..., example="Vintage")

class CollectTypeRead(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


# — Figure —

class FigureBase(BaseModel):
    name: str = Field(..., example="Lego X-Wing")
    bricklink_id: str = Field(..., example="75102")
    type_collected_id: int = Field(..., example=1)

class FigureCreate(FigureBase):
    pass

class FigureUpdate(BaseModel):
    name: Optional[str]
    bricklink_id: Optional[str]
    type_collected_id: Optional[int]

class FigureRead(FigureBase):
    id: int
    type_collected: CollectTypeRead

    class Config:
        orm_mode = True

# Детальная информация о связи «Figure ↔ User»

class FigureToUserRead(BaseModel):
    id: int
    bricklink_id: str
    name: str
    price_buy: Optional[float]
    price_sale: Optional[float]
    description: Optional[str]
    buy_date: Optional[date]
    sale_date: Optional[date]

    class Config:
        orm_mode = True

class BulkAddResponse(BaseModel):
    added: list[FigureToUserRead] = Field(..., description="Список успешно добавленных записей")
    failed: list[str] = Field(..., description="Список артикулов, которые не удалось добавить")


# Детальный вывод одной Figure
class FigureDetail(FigureRead):
    owners_count: int = Field(..., example=5)
    owned_by: List[FigureToUserRead] = []

    class Config:
        orm_mode = True


# — FigureToUser —

class FigureToUserCreate(BaseModel):
    user_id: int
    bricklink_id: str
    price_buy: Optional[float] = None
    price_sale: Optional[float] = None
    description: Optional[str] = None
    buy_date: Optional[date] = None
    sale_date: Optional[date] = None

class FigureToUserUpdate(BaseModel):
    price_buy: Optional[float]
    price_sale: Optional[float]
    description: Optional[str]
    buy_date: Optional[date]
    sale_date: Optional[date]

class FigureToUserReadFull(FigureToUserRead):
    figure: FigureRead

    class Config:
        orm_mode = True

class FigureInfo(BaseModel):
    # Основные поля фигурки
    id: int
    name: str
    bricklink_id: str
    type_collected_id: int

    user_record: Optional[FigureToUserRead] = None

    class Config:
        orm_mode = True

class SimilarFigure(BaseModel):
    id: int
    name: str
    bricklink_id: str
    similarity: float

    class Config:
        orm_mode = True


class MarketConditionPrices(BaseModel):
    avg_price_6m: Optional[float] = None
    min_price_6m: Optional[float] = None
    max_price_6m: Optional[float] = None
    times_sold_6m: Optional[int] = None
    total_qty_sold_6m: Optional[int] = None
    total_lots: Optional[int] = None
    total_qty_for_sale: Optional[int] = None
    avg_price_listed: Optional[float] = None


class FigureMarketPrices(BaseModel):
    bricklink_id: str
    currency: str = "USD"
    source_currency: Optional[str] = None
    exchange_rate: Optional[float] = None
    exchange_rate_date: Optional[str] = None
    exchange_rate_source: Optional[str] = None
    error: Optional[str] = None
    new: MarketConditionPrices = MarketConditionPrices()
    used: MarketConditionPrices = MarketConditionPrices()
    price_guide_url: Optional[str] = None


class FigureBrief(BaseModel):
    """Краткая карточка фигурки для поиска / тир-листа."""

    bricklink_id: str
    name: str

    class Config:
        orm_mode = True

class BulkAddError(BaseModel):
    index: int
    payload: dict
    error: str

class BulkAddResponse(BaseModel):
    successes: List[FigureToUserRead] = Field(
        ..., description="Список успешно добавленных записей"
    )
    failures: List[BulkAddError] = Field(
        ..., description="Список не добавленных записей с описанием ошибок"
    )
