"""
Клиент BrickLink: cookies из .env + разбор catalogitem.page.

Без сессии BrickLink (BLNEWSESSIONID, aws-waf-token) отдаёт «General Error» даже при HTTP 200.
Скопируйте cookies из браузера после входа на bricklink.com → DevTools → Application → Cookies.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import unquote

from lxml import html

logger = logging.getLogger("BrickLinkClient")

V2_URL = "https://www.bricklink.com/v2/catalog/catalogitem.page?M={item_id}"
LEGACY_URL = "https://www.bricklink.com/catalogItem.asp?M={item_id}"


@dataclass
class CatalogItemData:
    bricklink_id: str
    name: str
    item_type: Optional[str] = None
    year_released: Optional[str] = None
    weight: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class PageFetchResult:
    ok: bool
    http_status: int
    reason: str
    hint: str = ""
    item: Optional[CatalogItemData] = None
    url_used: str = ""


def _parse_cookie_string(raw: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for part in raw.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, value = part.split("=", 1)
        cookies[name.strip()] = value.strip()
    return cookies


def load_bricklink_cookies() -> dict[str, str]:
    """
    BRICKLINK_COOKIES — строка document.cookie:
      BLNEWSESSIONID=...; BLHASTOKEN=1; aws-waf-token=...
    или JSON: {"BLNEWSESSIONID": "...", ...}
    """
    raw = os.getenv("BRICKLINK_COOKIES", "").strip()
    if not raw:
        return {}

    if raw.startswith("{"):
        try:
            data = json.loads(raw)
            return {str(k): str(v) for k, v in data.items()}
        except json.JSONDecodeError:
            logger.warning("BRICKLINK_COOKIES: невалидный JSON, пробуем как строку")

    return _parse_cookie_string(raw)


def build_headers() -> dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.bricklink.com/catalog.asp",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Upgrade-Insecure-Requests": "1",
    }


def parse_catalog_html(text: str, item_id: str) -> PageFetchResult:
    lowered = text.lower()
    item_id_lower = item_id.lower()

    if "page not found" in lowered or "no item(s) were found" in lowered:
        return PageFetchResult(
            False, 200, "not_found", "Такого Item No нет в каталоге", url_used=""
        )
    if "general error" in lowered or "oops, sorry" in lowered:
        return PageFetchResult(
            False,
            200,
            "blocked_or_error",
            "Нужны cookies BrickLink (BRICKLINK_COOKIES в .env)",
            url_used="",
        )

    tree = html.fromstring(text)
    extra: dict[str, Any] = {}

    # 1) meta description: ItemName: Battle Droid..., ItemType: Minifigure
    meta_desc = tree.xpath("//meta[@name='description']/@content")
    name: Optional[str] = None
    item_type: Optional[str] = None
    if meta_desc:
        desc = unquote(meta_desc[0])
        m_name = re.search(r"ItemName:\s*(.*?),\s*ItemType:", desc, re.I)
        m_type = re.search(r"ItemType:\s*([^,]+)", desc, re.I)
        if m_name:
            name = m_name.group(1).strip()
        if m_type:
            item_type = m_type.group(1).strip()

    # 2) <title>Battle Droid ... : Minifigure sw0001a | BrickLink</title>
    titles = tree.xpath("//title/text()")
    if titles and not name:
        title = titles[0].strip()
        m = re.match(
            r"^(.+?)\s*:\s*(Minifigure|Part|Set)\s+([a-z0-9]+)\s*\|\s*BrickLink",
            title,
            re.I,
        )
        if m:
            name = m.group(1).strip()
            item_type = item_type or m.group(2).strip()
            if m.group(3).lower() != item_id_lower:
                logger.debug("title id %s != requested %s", m.group(3), item_id)

    # 3) h1 на v2-странице
    for xpath in (
        "//h1[@id='item-name-title']/text()",
        "//h1[contains(@class,'item-name')]/text()",
        "//main//h1/text()",
        "//h1/text()",
    ):
        nodes = tree.xpath(xpath)
        if nodes:
            candidate = " ".join(n.strip() for n in nodes if n.strip())
            if candidate and "bricklink" not in candidate.lower():
                name = name or candidate
                break

    # 4) JSON в script (Next.js / встроенные данные)
    for script_text in tree.xpath("//script/text()"):
        if "ItemName" not in script_text and "itemName" not in script_text:
            continue
        for pattern in (
            r'"ItemName"\s*:\s*"([^"]+)"',
            r'"itemName"\s*:\s*"([^"]+)"',
            r'"name"\s*:\s*"([^"]{3,120})"',
        ):
            m = re.search(pattern, script_text)
            if m and not name:
                name = m.group(1).encode().decode("unicode_escape")
                break

    # Доп. поля из текста страницы
    year_m = re.search(r"Year Released\s*:?\s*(\d{4})", text, re.I)
    weight_m = re.search(r"Weight\s*:?\s*([\d.]+)\s*g", text, re.I)
    year = year_m.group(1) if year_m else None
    weight = weight_m.group(1) if weight_m else None

    if year:
        extra["year_released"] = year
    if weight:
        extra["weight_g"] = weight

    if not name:
        snippet = " ".join(text[:500].split())[:150]
        return PageFetchResult(
            False,
            200,
            "no_itemname",
            f"Страница открылась, но имя не найдено. Фрагмент: {snippet}…",
            url_used="",
        )

    item = CatalogItemData(
        bricklink_id=item_id_lower,
        name=name,
        item_type=item_type,
        year_released=year,
        weight=weight,
        extra=extra,
    )
    return PageFetchResult(
        True, 200, "found", "", item=item, url_used=""
    )


def cookies_configured() -> bool:
    cookies = load_bricklink_cookies()
    has_session = bool(cookies.get("BLNEWSESSIONID") or cookies.get("BLHASTOKEN"))
    if cookies and not has_session:
        logger.warning(
            "BRICKLINK_COOKIES заданы, но нет BLNEWSESSIONID/BLHASTOKEN — "
            "возможна блокировка"
        )
    return bool(cookies)
