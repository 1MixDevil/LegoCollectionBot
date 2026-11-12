"""Price Guide BrickLink со страницы BricksAPP.

Пока bricklink.com и api.bricklink.com отдают maintenance, каталог
всё ещё содержит блок pricesBL: продажи за 6 месяцев и текущие лоты, в долларах.

Минифигурка: /catalog/minifigures/{id}
Набор: /catalog/sets/{id}
Деталь: цена зависит от цвета, она на /catalog/parts/{id}/{color}
"""

from __future__ import annotations

import asyncio
import json
import logging
import re

from app.business.bricklink_ids import infer_item_type
from app.business.price_guide_models import ColorPrices, ConditionPrices, PriceGuideData

logger = logging.getLogger("BricksAppPrices")

MAX_PART_COLORS = 10

_SECTION = {
    "MINIFIG": "minifigures",
    "SET": "sets",
    "PART": "parts",
}
_COLOR_RE = re.compile(
    r'\{"id":(\d+),"name":"([^"]+)","nameRus":"([^"]+)"\}'
)
_OFFER_QTY_RE = re.compile(
    r'"color":\{"id":(\d+)[\s\S]{0,700}?"quantity":(\d+)'
)
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

_cookie: str | None = None


def bricksapp_catalog_url(
    item_id: str,
    item_type: str,
    color_id: str | None = None,
) -> str:
    section = _SECTION.get(item_type, "minifigures")
    url = f"https://bricksapp.ru/catalog/{section}/{item_id}"
    if color_id:
        url = f"{url}/{color_id}"
    return url


def _loose(html: str) -> str:
    return html.replace('\\"', '"')


def _is_modulex(name: str) -> bool:
    low = name.lower()
    return low.startswith("mx ") or "modulex" in low


def part_colors(html: str) -> list[tuple[str, str]]:
    """Уникальные цвета детали: (id, русское имя)."""
    seen: set[str] = set()
    colors: list[tuple[str, str]] = []
    for match in _COLOR_RE.finditer(_loose(html)):
        color_id, name, name_rus = match.groups()
        if color_id in seen:
            continue
        seen.add(color_id)
        colors.append((color_id, name_rus or name))
    return colors


def _color_stock(html: str) -> dict[str, int]:
    stock: dict[str, int] = {}
    for match in _OFFER_QTY_RE.finditer(_loose(html)):
        color_id, qty = match.group(1), int(match.group(2))
        stock[color_id] = stock.get(color_id, 0) + qty
    return stock


def select_part_colors(html: str, limit: int = MAX_PART_COLORS) -> list[tuple[str, str]]:
    """Все цвета, если их не больше limit, иначе limit самых ходовых."""
    colors = part_colors(html)
    plain = [item for item in colors if not _is_modulex(item[1])]
    pool = plain or colors
    if not pool:
        return []
    stock = _color_stock(html)
    ranked = sorted(pool, key=lambda item: stock.get(item[0], 0), reverse=True)
    if len(ranked) <= limit:
        return ranked
    if any(stock.get(item[0], 0) > 0 for item in ranked):
        return ranked[:limit]
    return pool[:limit]


def choose_part_color(html: str) -> tuple[str | None, str | None]:
    picked = select_part_colors(html, limit=1)
    return picked[0] if picked else (None, None)


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
    timeout = aiohttp.ClientTimeout(total=25)
    last_error: Exception | None = None
    for _attempt in range(2):
        headers = {"User-Agent": _UA, "Accept": "text/html", "Accept-Language": "ru"}
        if _cookie:
            headers["Cookie"] = _cookie
        try:
            async with session.get(url, headers=headers, timeout=timeout) as resp:
                text = await resp.text(errors="replace")
        except aiohttp.ClientError as exc:
            last_error = exc
            _cookie = None
            continue
        if "pricesBL" in text or "initialPriceGuide" in text or "colorProducts" in text:
            return text
        match = re.search(r"_v2=([^;'\"\s]+)", text)
        if not match:
            last_error = RuntimeError("BricksAPP не отдал страницу каталога")
            _cookie = None
            continue
        _cookie = "_v2=" + match.group(1)
        headers["Cookie"] = _cookie
        async with session.get(url, headers=headers, timeout=timeout) as resp:
            text = await resp.text(errors="replace")
        if "Проверка браузера" in text and "pricesBL" not in text:
            _cookie = None
            last_error = RuntimeError("BricksAPP не пропустил проверку")
            continue
        return text
    raise last_error or RuntimeError("BricksAPP не отдал страницу каталога")


def _sales(new: ConditionPrices, used: ConditionPrices) -> int:
    return (new.times_sold_6m or 0) + (used.times_sold_6m or 0)


async def _fetch_part_colors(session, bricklink_id: str, overview: str) -> list[ColorPrices]:
    picked = select_part_colors(overview)

    async def one(color_id: str, color_name: str) -> ColorPrices | None:
        html = await _get_page(
            session, bricksapp_catalog_url(bricklink_id, "PART", color_id)
        )
        parsed = parse_bricksapp_price_guide(html, bricklink_id)
        if parsed.error:
            return None
        return ColorPrices(
            color_id=color_id,
            color_name=color_name,
            new=parsed.new,
            used=parsed.used,
        )

    loaded = await asyncio.gather(
        *(one(color_id, color_name) for color_id, color_name in picked),
        return_exceptions=True,
    )
    colors: list[ColorPrices] = []
    for item in loaded:
        if isinstance(item, ColorPrices):
            colors.append(item)
        elif isinstance(item, Exception):
            logger.debug("part color price failed", exc_info=item)
    colors.sort(key=lambda color: _sales(color.new, color.used), reverse=True)
    return colors


async def fetch_price_guide_bricksapp(bricklink_id: str) -> PriceGuideData:
    import aiohttp

    bricklink_id = bricklink_id.strip().lower()
    item_type = infer_item_type(bricklink_id)
    async with aiohttp.ClientSession() as session:
        html = await _get_page(
            session, bricksapp_catalog_url(bricklink_id, item_type)
        )
        if item_type == "PART" and "pricesBL" not in html:
            colors = await _fetch_part_colors(session, bricklink_id, html)
            result = PriceGuideData(bricklink_id=bricklink_id, currency="USD")
            if not colors:
                result.error = "no_price_data"
                return result
            top = colors[0]
            result.new = top.new
            result.used = top.used
            result.color_id = top.color_id
            result.color_name = top.color_name
            result.colors = colors
            result.error = None
            return result
    return parse_bricksapp_price_guide(html, bricklink_id)
