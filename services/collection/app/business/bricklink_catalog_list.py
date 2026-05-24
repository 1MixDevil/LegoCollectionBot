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

# Имена из seed, по которым нельзя искать в дереве BrickLink (слишком общие)
GENERIC_THEME_NAMES = frozenset({
    "collectible minifigures",
    "town",
    "space",
    "4 juniors",
    "duplo",
    "educational & dacta",
    "holiday & event",
})

# Подсказки: article → фразы в названии категории BrickLink (ускоряют поиск)
ARTICLE_KEYWORD_HINTS: dict[str, list[str]] = {
    "sw": ["star wars"],
    "lor": ["lord of the rings", "hobbit", "lotr"],
    "hp": ["harry potter"],
    "sim": ["simpsons"],
    "njo": ["ninjago"],
    "jw": ["jurassic"],
    "mar": ["super mario"],
    "sh": ["super heroes", "dc comics", "marvel"],
    "dp": ["disney"],
    "dim": ["dimensions"],
    "min": ["minecraft"],
    "crs": ["cars"],
    "bob": ["spongebob"],
    "iaj": ["indiana jones"],
    "mon": ["monkey island", "pirates"],
    "mk": ["monkie kid"],
    "dun": ["dune"],
    "ani": ["animal crossing"],
    "gb": ["ideas", "cuusoo"],
    "idea": ["ideas", "cuusoo"],
}

MAX_CATALOG_PAGES = int(os.getenv("BRICKLINK_CATALOG_MAX_PAGES", "80"))
MAX_CAT_SCAN = int(os.getenv("BRICKLINK_CAT_SCAN_LIMIT", "80"))


def _theme_name_usable(theme_name: Optional[str]) -> bool:
    if not theme_name or not theme_name.strip():
        return False
    return theme_name.strip().lower() not in GENERIC_THEME_NAMES


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


def _all_categories_from_tree(tree_html: str) -> list[tuple[str, str]]:
    """Уникальные пары (catString, название категории)."""
    doc = html.fromstring(tree_html)
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for node in doc.xpath("//a[contains(@href,'catalogList.asp')]"):
        href = node.get("href") or ""
        cat = _extract_cat_string(href)
        if not cat or cat in seen:
            continue
        label = " ".join(node.itertext()).strip()
        if not label or label == "{}":
            continue
        seen.add(cat)
        out.append((cat, label))
    return out


def infer_pad_len(item_ids: list[str], article: str) -> int:
    article = article.lower()
    lengths: list[int] = []
    for item_id in item_ids:
        m = re.match(rf"{re.escape(article)}(\d+)([a-z]?)$", item_id.lower())
        if m:
            lengths.append(len(m.group(1)))
    return max(lengths) if lengths else 3


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


def _keyword_hints(article: str, theme_name: Optional[str] = None) -> list[str]:
    hints = list(ARTICLE_KEYWORD_HINTS.get(article.lower(), []))
    if theme_name and theme_name.strip():
        theme_lower = theme_name.strip().lower()
        if theme_lower not in GENERIC_THEME_NAMES and theme_lower not in hints:
            hints.append(theme_lower)
    return hints


def _categories_to_scan(
    all_cats: list[tuple[str, str]],
    article: str,
    theme_name: Optional[str],
) -> list[tuple[str, str]]:
    """Упорядоченный список категорий для проверки по префиксу артикула."""
    article = article.lower()
    hints = _keyword_hints(article, theme_name)

    if hints:
        filtered = [
            (cat, label)
            for cat, label in all_cats
            if any(h in label.lower() for h in hints)
        ]
    elif theme_name and theme_name.strip().lower() not in GENERIC_THEME_NAMES:
        filtered = [
            (cat, label)
            for cat, label in all_cats
            if theme_name.strip().lower() in label.lower()
        ]
    else:
        filtered = list(all_cats)

    return sorted(
        filtered,
        key=lambda pair: (pair[0].count("."), len(pair[0])),
    )


async def _resolve_cat_by_prefix_scan(
    session: aiohttp.ClientSession,
    article: str,
    theme_name: Optional[str] = None,
) -> tuple[Optional[str], Optional[str], int]:
    """
    Ищет категорию BrickLink, где на странице есть артикулы с префиксом article.
    Возвращает (catString, label, count_on_page).
    """
    global _tree_cache
    if _tree_cache is None:
        _tree_cache = await _fetch_text(session, CATALOG_TREE_URL, {})

    article = article.lower()
    all_cats = _all_categories_from_tree(_tree_cache)
    filtered = _categories_to_scan(all_cats, article, theme_name)

    best_cat: Optional[str] = None
    best_label: Optional[str] = None
    best_count = 0
    checks = 0

    for cat, label in filtered:
        if checks >= MAX_CAT_SCAN:
            break
        checks += 1
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
        count = len(items)
        if count > best_count:
            best_count = count
            best_cat = cat
            best_label = label
        if best_count >= 10:
            break

    return best_cat, best_label, best_count


async def _count_items_on_page(
    session: aiohttp.ClientSession,
    cat: str,
    article: str,
) -> int:
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
    return len(parse_catalog_list_page(sample, article))


async def resolve_cat_string(
    session: aiohttp.ClientSession,
    article: str,
    theme_name: Optional[str] = None,
    *,
    cached_cat: Optional[str] = None,
) -> tuple[Optional[str], Optional[str]]:
    """
    Находит catString только по BrickLink (дерево + скан префикса).
    Возвращает (catString, название категории).
    """
    article = article.lower()
    if article in _cat_cache:
        cat = _cat_cache[article]
        label = _label_for_cat(cat)
        return cat, label

    if cached_cat:
        count = await _count_items_on_page(session, cached_cat, article)
        if count >= 3:
            _cat_cache[article] = cached_cat
            label = _label_for_cat(cached_cat)
            logger.info(
                "[%s] BrickLink catString=%s из БД (%s на 1-й стр.)",
                article,
                cached_cat,
                count,
            )
            return cached_cat, label
        logger.warning(
            "[%s] кэш catString=%s устарел (%s шт.), ищем заново",
            article,
            cached_cat,
            count,
        )

    global _tree_cache
    if _tree_cache is None:
        _tree_cache = await _fetch_text(session, CATALOG_TREE_URL, {})

    best_cat: Optional[str] = None
    best_label: Optional[str] = None
    best_count = 0

    theme_ok = (
        theme_name
        and theme_name.strip()
        and theme_name.strip().lower() not in GENERIC_THEME_NAMES
    )
    if theme_ok:
        candidates = _cat_candidates_from_tree(_tree_cache, theme_name)
        for cat in candidates[:6]:
            count = await _count_items_on_page(session, cat, article)
            if count > best_count:
                best_count = count
                best_cat = cat
                best_label = _label_for_cat(cat)
            if best_count >= 10:
                break

    scan_cat, scan_label, scan_count = await _resolve_cat_by_prefix_scan(
        session, article, theme_name
    )
    if scan_cat and scan_count > best_count:
        best_cat = scan_cat
        best_label = scan_label
        best_count = scan_count

    if best_cat:
        _cat_cache[article] = best_cat
        logger.info(
            "[%s] BrickLink catString=%s («%s», %s на 1-й стр.)",
            article,
            best_cat,
            best_label or "?",
            best_count,
        )
        return best_cat, best_label

    logger.warning("[%s] Категория BrickLink не найдена", article)
    return None, None


def _label_for_cat(cat: str) -> Optional[str]:
    if not _tree_cache:
        return None
    for c, label in _all_categories_from_tree(_tree_cache):
        if c == cat:
            return label
    return None


async def discover_series_metadata(
    article: str,
    theme_name: Optional[str] = None,
) -> Optional[dict[str, object]]:
    """
    Метаданные серии для type_of_collect, если записи ещё нет в БД.
    """
    article = article.strip().lower()
    async with aiohttp.ClientSession() as session:
        cat, label = await resolve_cat_string(session, article, theme_name)
        if not cat:
            return None

        sample_html = await _fetch_text(
            session,
            CATALOG_LIST_URL,
            {
                "catType": "M",
                "catString": cat,
                "pageSize": 50,
                "pg": 1,
            },
        )
        items = parse_catalog_list_page(sample_html, article)
        if not items:
            return None

        ids = [item_id for item_id, _ in items]
        return {
            "name": label or article.upper(),
            "pad_len": infer_pad_len(ids, article),
            "cat_string": cat,
            "sample_count": len(items),
        }


async def fetch_minifigs_by_article(
    article: str,
    theme_name: Optional[str] = None,
    *,
    bricklink_cat: Optional[str] = None,
    page_size: int = 50,
    delay_sec: float = 0.5,
) -> tuple[list[tuple[str, str]], Optional[str], Optional[str]]:
    """
    Все минифигурки серии по префиксу BrickLink (sw, hp, sim, …) из catalogList.
    Возвращает (records, catString, category_label).
    """
    article = article.strip().lower()
    collected: dict[str, str] = {}
    resolved_cat: Optional[str] = None
    resolved_label: Optional[str] = None

    async with aiohttp.ClientSession() as session:
        cat, label = await resolve_cat_string(
            session,
            article,
            theme_name or None,
            cached_cat=bricklink_cat,
        )
        if not cat:
            return [], None, None
        resolved_cat = cat
        resolved_label = label

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

            # Не останавливаемся из‑за len(batch) < page_size: BrickLink иногда
            # отдаёт неполную первую страницу (hp: 46 из 50), дальше есть ещё.
            if not batch or added == 0:
                break
            page += 1
            if delay_sec > 0 and REQUEST_DELAY <= 0:
                await asyncio.sleep(delay_sec)

    return sorted(collected.items()), resolved_cat, resolved_label
