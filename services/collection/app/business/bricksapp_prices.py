"""Price Guide BrickLink со страницы BricksAPP.

Пока bricklink.com и api.bricklink.com отдают maintenance, каталог
https://bricksapp.ru/catalog/minifigures/{id} всё ещё содержит блок pricesBL:
продажи за 6 месяцев и текущие лоты, в долларах.
"""

from __future__ import annotations

import json
import logging
import re

from app.business.price_guide_models import ConditionPrices, PriceGuideData

logger = logging.getLogger("BricksAppPrices")

BRICKSAPP_MINIFIG_URL = "https://bricksapp.ru/catalog/minifigures/{item_id}"
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

_cookie: str | None = None


def extract_prices_bl(html: str) -> dict | None:
    """Достать объект pricesBL из RSC-разметки страницы."""
    for marker in ('pricesBL\\":', '"pricesBL":'):
        start_at = html.find(marker)
        if start_at < 0:
            continue
        brace = html.find("{", start_at)
        if brace < 0:
            continue
        depth = 0
        for index in range(brace, len(html)):
            char = html[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    blob = html[brace : index + 1]
                    if marker.endswith('\\":'):
                        blob = blob.replace('\\"', '"')
                    try:
                        data = json.loads(blob)
                    except json.JSONDecodeError:
                        return None
                    return data if isinstance(data, dict) else None
    return None


def _positive(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    return number


def _positive_int(value) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    return number


def _fill(
    target: ConditionPrices,
    data: dict,
    prefix: str,
    *,
    sold: bool,
) -> bool:
    sales = _positive_int(data.get(f"{prefix}Sales"))
    qty = _positive_int(data.get(f"{prefix}Qty"))
    if sales is None and qty is None:
        return False
    if sold:
        target.times_sold_6m = sales
        target.total_qty_sold_6m = qty
        target.min_6m = _positive(data.get(f"{prefix}MinPrice"))
        target.avg_6m = _positive(data.get(f"{prefix}QtyAvgPrice"))
        target.qty_avg_6m = target.avg_6m
        target.max_6m = _positive(data.get(f"{prefix}MaxPrice"))
    else:
        target.total_lots = sales
        target.total_qty_for_sale = qty
        target.min_listed = _positive(data.get(f"{prefix}MinPrice"))
        target.avg_listed = _positive(data.get(f"{prefix}QtyAvgPrice"))
        target.max_listed = _positive(data.get(f"{prefix}MaxPrice"))
    return True


def parse_bricksapp_price_guide(html: str, bricklink_id: str) -> PriceGuideData:
    result = PriceGuideData(bricklink_id=bricklink_id.strip().lower(), currency="USD")
    if "Проверка браузера" in html and "pricesBL" not in html:
        result.error = "bricksapp_challenge"
        return result
    data = extract_prices_bl(html)
    if not data:
        result.error = "not_found"
        return result
    got = False
    got = _fill(result.used, data, "UsedLast6m", sold=True) or got
    got = _fill(result.used, data, "UsedCurrent", sold=False) or got
    got = _fill(result.new, data, "NewLast6m", sold=True) or got
    got = _fill(result.new, data, "NewCurrent", sold=False) or got
    result.error = None if got else "no_price_data"
    return result


async def _get_page(session, url: str) -> str:
    import aiohttp

    global _cookie
    headers = {"User-Agent": _UA, "Accept": "text/html"}
    if _cookie:
        headers["Cookie"] = _cookie
    timeout = aiohttp.ClientTimeout(total=25)
    async with session.get(url, headers=headers, timeout=timeout) as resp:
        text = await resp.text(errors="replace")
    if "pricesBL" in text:
        return text
    match = re.search(r"_v2=([^;'\"\s]+)", text)
    if not match:
        raise RuntimeError("BricksAPP не отдал страницу каталога")
    _cookie = "_v2=" + match.group(1)
    headers["Cookie"] = _cookie
    async with session.get(url, headers=headers, timeout=timeout) as resp:
        text = await resp.text(errors="replace")
    if "pricesBL" not in text:
        _cookie = None
    return text


async def fetch_price_guide_bricksapp(bricklink_id: str) -> PriceGuideData:
    import aiohttp

    bricklink_id = bricklink_id.strip().lower()
    url = BRICKSAPP_MINIFIG_URL.format(item_id=bricklink_id)
    async with aiohttp.ClientSession() as session:
        html = await _get_page(session, url)
    return parse_bricksapp_price_guide(html, bricklink_id)
