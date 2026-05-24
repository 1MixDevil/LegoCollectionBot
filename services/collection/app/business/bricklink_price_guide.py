"""
Цены BrickLink с catalogPG.asp (Price Guide).

Без cookies обычно открывается; при блокировке — BRICKLINK_COOKIES в .env.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

import aiohttp
from lxml import html

from app.business.bricklink_client import build_headers

logger = logging.getLogger("BrickLinkPriceGuide")

PRICE_GUIDE_URL = "https://www.bricklink.com/catalogPG.asp"
REQUEST_DELAY = float(__import__("os").getenv("BRICKLINK_PRICE_DELAY", "1.0"))

_cache: dict[str, "PriceGuideData"] = {}


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


def _parse_money(text: str) -> Optional[float]:
    text = text.replace(",", "").strip()
    try:
        return float(text)
    except ValueError:
        return None


def parse_price_guide_html(html_text: str, bricklink_id: str) -> PriceGuideData:
    result = PriceGuideData(bricklink_id=bricklink_id.lower())
    try:
        plain = re.sub(r"\s+", " ", html.fromstring(html_text).text_content())
    except Exception as exc:
        result.error = f"parse error: {exc}"
        return result

    if "page not found" in plain.lower() or "no item" in plain.lower():
        result.error = "not_found"
        return result

    six_month = re.findall(
        r"Times Sold:\s*(\d+)\s*Total Qty:\s*(\d+)\s*"
        r"Min Price:\s*[A-Z]{2,3}\s*([\d.]+)\s*"
        r"Avg Price:\s*[A-Z]{2,3}\s*([\d.]+)\s*"
        r"Qty Avg Price:\s*[A-Z]{2,3}\s*([\d.]+)\s*"
        r"Max Price:\s*[A-Z]{2,3}\s*([\d.]+)",
        plain,
    )
    for_sale = re.findall(
        r"Total Lots:\s*(\d+)\s*Total Qty:\s*(\d+)\s*"
        r"Min Price:\s*[A-Z]{2,3}\s*([\d.]+)\s*"
        r"Avg Price:\s*[A-Z]{2,3}\s*([\d.]+)\s*"
        r"Qty Avg Price:\s*[A-Z]{2,3}\s*([\d.]+)\s*"
        r"Max Price:\s*[A-Z]{2,3}\s*([\d.]+)",
        plain,
    )

    if not six_month and not for_sale:
        result.error = "no_price_data"
        return result

    def fill_6m(target: ConditionPrices, block: tuple) -> None:
        target.times_sold_6m = int(block[0])
        target.total_qty_sold_6m = int(block[1])
        target.min_6m = _parse_money(block[2])
        target.avg_6m = _parse_money(block[3])
        target.qty_avg_6m = _parse_money(block[4])
        target.max_6m = _parse_money(block[5])

    def fill_sale(target: ConditionPrices, block: tuple) -> None:
        target.total_lots = int(block[0])
        target.total_qty_for_sale = int(block[1])
        target.min_listed = _parse_money(block[2])
        target.avg_listed = _parse_money(block[3])
        target.max_listed = _parse_money(block[5])

    if len(six_month) >= 1:
        fill_6m(result.new, six_month[0])
        result.currency = _detect_currency(plain) or result.currency
    if len(six_month) >= 2:
        fill_6m(result.used, six_month[1])

    if len(for_sale) >= 1:
        fill_sale(result.new, for_sale[0])
    if len(for_sale) >= 2:
        fill_sale(result.used, for_sale[1])

    if six_month or for_sale:
        result.error = None

    return result


def _detect_currency(plain: str) -> str:
    for code in ("RUB", "EUR", "GBP", "USD", "PLN", "UAH"):
        if code in plain:
            return code
    return "USD"


async def fetch_price_guide(
    session: aiohttp.ClientSession,
    bricklink_id: str,
) -> PriceGuideData:
    bricklink_id = bricklink_id.strip().lower()
    if bricklink_id in _cache:
        return _cache[bricklink_id]

    if REQUEST_DELAY > 0:
        await asyncio.sleep(REQUEST_DELAY)

    try:
        async with session.get(
            PRICE_GUIDE_URL,
            params={"M": bricklink_id},
            headers=build_headers(),
            timeout=aiohttp.ClientTimeout(total=45),
        ) as resp:
            resp.raise_for_status()
            text = await resp.text()
    except Exception as exc:
        logger.warning("price guide fetch %s: %s", bricklink_id, exc)
        data = PriceGuideData(bricklink_id=bricklink_id, error=str(exc))
        return data

    data = parse_price_guide_html(text, bricklink_id)
    if not data.error:
        _cache[bricklink_id] = data
    return data


async def get_market_prices(bricklink_id: str) -> PriceGuideData:
    async with aiohttp.ClientSession() as session:
        return await fetch_price_guide(session, bricklink_id)


def price_guide_to_dict(data: PriceGuideData) -> dict:
    def cond_dict(c: ConditionPrices) -> dict:
        return {
            "avg_price_6m": c.avg_6m,
            "min_price_6m": c.min_6m,
            "max_price_6m": c.max_6m,
            "qty_avg_price_6m": c.qty_avg_6m,
            "times_sold_6m": c.times_sold_6m,
            "total_qty_sold_6m": c.total_qty_sold_6m,
            "total_lots": c.total_lots,
            "total_qty_for_sale": c.total_qty_for_sale,
            "avg_price_listed": c.avg_listed,
            "min_price_listed": c.min_listed,
            "max_price_listed": c.max_listed,
        }

    return {
        "bricklink_id": data.bricklink_id,
        "currency": data.currency,
        "error": data.error,
        "new": cond_dict(data.new),
        "used": cond_dict(data.used),
    }
