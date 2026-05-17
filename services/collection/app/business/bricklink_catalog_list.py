"""
Массовая загрузка минифигурок с BrickLink catalogList (без cookies).

Страницы списка (catalogList.asp) открываются без сессии; отдельные карточки
catalogitem.page часто отдают General Error — для /update используем только список.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Optional
from urllib.parse import parse_qs, urlparse

import aiohttp
from lxml import html

from app.business.bricklink_client import build_headers

logger = logging.getLogger("BrickLinkCatalogList")

CATALOG_TREE_URL = "https://www.bricklink.com/catalogTree.asp?itemType=M"
CATALOG_LIST_URL = "https://www.bricklink.com/catalogList.asp"
REQUEST_DELAY = float(os.getenv("BRICKLINK_CATALOG_DELAY", "2.0"))

ROW_RE = re.compile(
    r'catalogitem\.page\?M=([a-z0-9]+)".*?<strong>([^<]+)</strong>',
    re.IGNORECASE | re.DOTALL,
)

_cat_cache: dict[str, str] = {}
_tree_cache: Optional[str] = None

# Проверенные catString (Minifigures → Licensed → …), чтобы не дергать дерево лишний раз
CAT_STRING_OVERRIDES: dict[str, str] = {
    "sw": "65",
}

MAX_CATALOG_PAGES = int(os.getenv("BRICKLINK_CATALOG_MAX_PAGES", "80"))


def _normalize_name(raw: str) -> str:
    import html as html_module

    return html_module.unescape(raw).strip()


def parse_catalog_list_page(html: str, article: str) -> list[tuple[str, str]]:
    """Пары (bricklink_id, name) с одной страницы списка."""
    article = article.lower()
    seen: set[str] = set()
    out: list[tuple[str, str]] = []

    for match in ROW_RE.finditer(html):
        item_id = match.group(1).lower()
        if not item_id.startswith(article):
            continue
        if item_id in seen:
            continue
        seen.add(item_id)
        name = _normalize_name(match.group(2))
        if name:
            out.append((item_id, name))

    return out


def _extract_cat_string(href: str) -> Optional[str]:
    if "catalogList.asp" not in href:
        return None
    parsed = urlparse(href)
    qs = parse_qs(parsed.query)
    cat = qs.get("catString") or qs.get("catstring")
    if not cat:
        return None
    return cat[0]


def _cat_candidates_from_tree(tree_html: str, theme_name: str) -> list[str]:
    """Все catString из дерева, подходящие под имя темы."""
    doc = html.fromstring(tree_html)
    theme_lower = theme_name.strip().lower()
    seen: set[str] = set()
    exact: list[str] = []
    partial: list[str] = []

    for node in doc.xpath("//a[contains(@href,'catalogList.asp')]"):
        href = node.get("href") or ""
        cat = _extract_cat_string(href)
        if not cat or cat in seen:
            continue
        label = " ".join(node.itertext()).strip()
        if not label or label == "{}":
            continue
        seen.add(cat)
        lbl_lower = label.lower()
        if lbl_lower == theme_lower:
            exact.append(cat)
        elif theme_lower in lbl_lower:
            partial.append(cat)

    if exact:
        # Предпочитаем короткий id (65 лучше 1166.65) — обычно полный раздел серии
        return sorted(exact, key=lambda c: (c.count("."), len(c)))
    return partial


async def _fetch_text(
    session: aiohttp.ClientSession,
    url: str,
    params: dict,
    *,
    retries: int = 3,
) -> str:
    for attempt in range(retries):
        if REQUEST_DELAY > 0:
            await asyncio.sleep(REQUEST_DELAY)
        async with session.get(
            url,
            params=params,
            headers=build_headers(),
            timeout=aiohttp.ClientTimeout(total=60),
        ) as resp:
            if resp.status == 429:
                wait = 5 * (attempt + 1)
                logger.warning("BrickLink 429, ждём %s сек", wait)
                await asyncio.sleep(wait)
                continue
            resp.raise_for_status()
            text = await resp.text()
            if "quota exceeded" in text.lower() or "error.page?code=429" in str(resp.url):
                wait = 10 * (attempt + 1)
                logger.warning("BrickLink quota, ждём %s сек", wait)
                await asyncio.sleep(wait)
                continue
            return text
    raise RuntimeError("BrickLink: превышен лимит запросов (429)")


async def resolve_cat_string(
    session: aiohttp.ClientSession,
    article: str,
    theme_name: str,
) -> Optional[str]:
    if article in _cat_cache:
        return _cat_cache[article]

    if article in CAT_STRING_OVERRIDES:
        cat = CAT_STRING_OVERRIDES[article]
        _cat_cache[article] = cat
        logger.info("[%s] BrickLink catString=%s (override)", article, cat)
        return cat

    global _tree_cache
    if _tree_cache is None:
        _tree_cache = await _fetch_text(session, CATALOG_TREE_URL, {})
    candidates = _cat_candidates_from_tree(_tree_cache, theme_name)
    best_cat: Optional[str] = None
    best_count = 0

    for cat in candidates[:4]:
        sample = await _fetch_text(
            session,
            CATALOG_LIST_URL,
            {
                "catType": "M",
                "catString": cat,
                "pageSize": 30,
                "pg": 1,
            },
        )
        items = parse_catalog_list_page(sample, article)
        if len(items) > best_count:
            best_count = len(items)
            best_cat = cat
        if best_count >= 5:
            break

    if best_cat:
        _cat_cache[article] = best_cat
        logger.info(
            "[%s] BrickLink catString=%s (тема «%s»), на 1-й стр.: %s шт.",
            article,
            best_cat,
            theme_name,
            best_count,
        )
        return best_cat

    logger.warning(
        "[%s] Не найдена категория BrickLink для «%s» (кандидатов: %s)",
        article,
        theme_name,
        len(candidates),
    )
    return None


async def fetch_minifigs_by_article(
    article: str,
    theme_name: str,
    *,
    page_size: int = 50,
    delay_sec: float = 0.5,
) -> list[tuple[str, str]]:
    """
    Все минифигурки серии по префиксу BrickLink (sw, hp, …) из catalogList.
    """
    article = article.strip().lower()
    collected: dict[str, str] = {}

    async with aiohttp.ClientSession() as session:
        cat = await resolve_cat_string(session, article, theme_name)
        if not cat:
            return []

        page = 1
        while page <= MAX_CATALOG_PAGES:
            before = len(collected)
            html_text = await _fetch_text(
                session,
                CATALOG_LIST_URL,
                {
                    "catType": "M",
                    "catString": cat,
                    "pageSize": page_size,
                    "pg": page,
                },
            )
            batch = parse_catalog_list_page(html_text, article)
            for item_id, name in batch:
                collected[item_id] = name

            added = len(collected) - before
            logger.info(
                "[%s] BrickLink catalogList стр.%s: +%s новых (на стр. %s, всего %s)",
                article,
                page,
                added,
                len(batch),
                len(collected),
            )

            if not batch or added == 0:
                break
            if len(batch) < page_size:
                break
            page += 1
            if delay_sec > 0 and REQUEST_DELAY <= 0:
                await asyncio.sleep(delay_sec)

    return sorted(collected.items())
