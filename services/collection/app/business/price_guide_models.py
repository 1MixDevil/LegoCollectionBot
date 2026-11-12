"""Общие структуры Price Guide, без клиентов BrickLink и BricksAPP."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ConditionPrices:
    # Last 6 months sales
    avg_6m: Optional[float] = None
    min_6m: Optional[float] = None
    max_6m: Optional[float] = None
    qty_avg_6m: Optional[float] = None
    times_sold_6m: Optional[int] = None
    total_qty_sold_6m: Optional[int] = None
    # Current items for sale (lots on BrickLink)
    total_lots: Optional[int] = None
    total_qty_for_sale: Optional[int] = None
    avg_listed: Optional[float] = None
    min_listed: Optional[float] = None
    max_listed: Optional[float] = None


@dataclass
class PriceGuideData:
    bricklink_id: str
    currency: str = "USD"
    new: ConditionPrices = field(default_factory=ConditionPrices)
    used: ConditionPrices = field(default_factory=ConditionPrices)
    error: Optional[str] = None
