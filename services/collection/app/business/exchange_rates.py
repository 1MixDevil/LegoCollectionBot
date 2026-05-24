"""
Курсы валют ЦБ РФ для отображения цен BrickLink в рублях.

BrickLink без входа отдаёт EUR/USD по региону; прямой запрос RUB через URL не работает.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from typing import Optional

import aiohttp

from app.schemas.figure_schema import FigureMarketPrices, MarketConditionPrices

logger = logging.getLogger("ExchangeRates")

CBR_DAILY_URL = os.getenv(
    "CBR_RATES_URL",
    "https://www.cbr-xml-daily.ru/daily_json.js",
)
CACHE_TTL_SEC = int(os.getenv("CBR_RATES_CACHE_TTL", str(4 * 3600)))

_rates_cache: dict[str, float] = {}
_rate_date: Optional[str] = None
_fetched_at: float = 0.0


def display_currency() -> Optional[str]:
    """RUB по умолчанию; NATIVE / OFF — валюта BrickLink как есть."""
    raw = os.getenv("DISPLAY_CURRENCY", "RUB").strip().upper()
    if raw in ("", "NATIVE", "ORIGINAL", "OFF", "NONE"):
        return None
    return raw


async def _fetch_cbr_rates() -> tuple[dict[str, float], str]:
    global _rates_cache, _rate_date, _fetched_at

    now = time.monotonic()
    if _rates_cache and (now - _fetched_at) < CACHE_TTL_SEC:
        return _rates_cache, _rate_date or ""

    async with aiohttp.ClientSession() as session:
        async with session.get(
            CBR_DAILY_URL,
            timeout=aiohttp.ClientTimeout(total=20),
        ) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)

    valutes = data.get("Valute") or {}
    rates: dict[str, float] = {"RUB": 1.0}
    for code, item in valutes.items():
        nominal = float(item.get("Nominal") or 1)
        value = float(item.get("Value") or 0)
        if nominal > 0 and value > 0:
            rates[code.upper()] = value / nominal

    rate_date = (data.get("Date") or "")[:10]
    _rates_cache = rates
    _rate_date = rate_date
    _fetched_at = now
    logger.info("CBR rates loaded, date=%s, codes=%d", rate_date, len(rates))
    return rates, rate_date


async def rub_per_unit(char_code: str) -> tuple[float, str]:
    """Сколько рублей за 1 единицу валюты (EUR, USD, …)."""
    code = char_code.upper()
    if code == "RUB":
        return 1.0, _rate_date or ""

    rates, rate_date = await _fetch_cbr_rates()
    if code not in rates:
        raise KeyError(f"CBR: нет курса для {code}")
    return rates[code], rate_date


async def convert_to_currency(
    amount: Optional[float],
    from_code: str,
    to_code: str,
) -> Optional[float]:
    if amount is None:
        return None
    src = from_code.upper()
    dst = to_code.upper()
    if src == dst:
        return round(float(amount), 2)

    src_rub, _ = await rub_per_unit(src)
    if dst == "RUB":
        return round(float(amount) * src_rub, 2)

    dst_rub, _ = await rub_per_unit(dst)
    return round(float(amount) * src_rub / dst_rub, 2)


def _convert_condition(
    cond: MarketConditionPrices,
    rate: float,
) -> MarketConditionPrices:
    def cv(v: Optional[float]) -> Optional[float]:
        if v is None:
            return None
        return round(v * rate, 2)

    return MarketConditionPrices(
        avg_price_6m=cv(cond.avg_price_6m),
        min_price_6m=cv(cond.min_price_6m),
        max_price_6m=cv(cond.max_price_6m),
        times_sold_6m=cond.times_sold_6m,
        total_qty_sold_6m=cond.total_qty_sold_6m,
        total_lots=cond.total_lots,
        total_qty_for_sale=cond.total_qty_for_sale,
        avg_price_listed=cv(cond.avg_price_listed),
    )


async def apply_display_currency(
    market: FigureMarketPrices,
) -> FigureMarketPrices:
    target = display_currency()
    if not target or market.error:
        return market

    source = (market.currency or "USD").upper()
    if source == target:
        return market

    try:
        src_rub, rate_date = await rub_per_unit(source)
        if target == "RUB":
            rate = src_rub
        else:
            dst_rub, _ = await rub_per_unit(target)
            rate = src_rub / dst_rub
    except Exception as exc:
        logger.warning("currency convert %s→%s: %s", source, target, exc)
        return market

    market.source_currency = source
    market.currency = target
    market.exchange_rate = round(rate, 4)
    market.exchange_rate_date = rate_date
    market.exchange_rate_source = "cbr"
    market.new = _convert_condition(market.new, rate)
    market.used = _convert_condition(market.used, rate)
    return market
