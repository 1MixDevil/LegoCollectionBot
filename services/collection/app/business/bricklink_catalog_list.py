"""
Массовая загрузка минифигурок с BrickLink.

Универсальный путь: скан префикса через img.bricklink.com (CDN) — работает для
любого article (poc, lor, sw…) без ручных подсказок.

catalogList — ускорение при BRICKLINK_COOKIES; ARTICLE_KEYWORD_HINTS — опционально.
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

from app.business.bricklink_client import build_headers, load_bricklink_cookies

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

# Опционально: ускоряют поиск catString при наличии cookies (не обязательны)
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
    "poc": ["pirates of the caribbean"],
    "mk": ["monkie kid"],
    "dun": ["dune"],
    "ani": ["animal crossing"],
    "gb": ["ideas", "cuusoo"],
    "idea": ["ideas", "cuusoo"],
}

MAX_CATALOG_PAGES = int(os.getenv("BRICKLINK_CATALOG_MAX_PAGES", "80"))
MAX_CAT_SCAN = int(os.getenv("BRICKLINK_CAT_SCAN_LIMIT", "80"))
CDN_GAP = int(os.getenv("BRICKLINK_CDN_GAP", "12"))
CDN_MAX_NUM = int(os.getenv("BRICKLINK_CDN_MAX_NUM", "150"))
CDN_BATCH = int(os.getenv("BRICKLINK_CDN_BATCH", "10"))
CDN_CONCURRENCY = int(os.getenv("BRICKLINK_CDN_CONCURRENCY", "8"))


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
    cookies = load_bricklink_cookies()
    for attempt in range(retries):
        if REQUEST_DELAY > 0:
            await asyncio.sleep(REQUEST_DELAY)
        async with session.get(
            url,
            params=params,
            headers=build_headers(),
            cookies=cookies or None,
            timeout=aiohttp.ClientTimeout(total=60),
        ) as resp:
            if resp.status == 429:
                wait = 5 * (attempt + 1)
                logger.warning("BrickLink 429, ждём %s сек", wait)
                await asyncio.sleep(wait)
                continue
            text = await resp.text()
            if resp.status in (202, 403) or len(text) < 500:
                wait = 5 * (attempt + 1)
                logger.warning(
                    "BrickLink catalogList blocked/empty (HTTP %s, %s bytes), retry %s",
                    resp.status,
                    len(text),
                    attempt + 1,
                )
                if attempt < retries - 1:
                    await asyncio.sleep(wait)
                    continue
                return ""
            if "quota exceeded" in text.lower() or "error.page?code=429" in str(resp.url):
                wait = 10 * (attempt + 1)
                logger.warning("BrickLink quota, ждём %s сек", wait)
                await asyncio.sleep(wait)
                continue
            resp.raise_for_status()
            return text
    raise RuntimeError("BrickLink: превышен лимит запросов (429)")


def _keyword_hints(article: str, theme_name: Optional[str] = None) -> list[str]:
    hints = list(ARTICLE_KEYWORD_HINTS.get(article.lower(), []))
    if theme_name and theme_name.strip():
        theme_lower = theme_name.strip().lower()
        if theme_lower not in GENERIC_THEME_NAMES and theme_lower not in hints:
            hints.append(theme_lower)
    return hints


def _resolve_cat_from_hints(tree_html: str, article: str) -> tuple[Optional[str], Optional[str]]:
    """Категория из дерева BrickLink по опциональным подсказкам."""
    article = article.lower()
    hints = ARTICLE_KEYWORD_HINTS.get(article, [])
    if not hints:
        return None, None

    matches = [
        (cat, label)
        for cat, label in _all_categories_from_tree(tree_html)
        if any(h in label.lower() for h in hints)
    ]
    if not matches:
        return None, None

    def rank(pair: tuple[str, str]) -> tuple[int, int]:
        label_lower = pair[1].lower()
        best = max((len(h) for h in hints if h in label_lower), default=0)
        return (best, -len(pair[0]))

    matches.sort(key=rank, reverse=True)
    return matches[0]


CDN_MIN_BYTES = 800


async def _cdn_minifig_exists(session: aiohttp.ClientSession, item_id: str) -> bool:
    url = f"https://img.bricklink.com/ItemImage/MN/0/{item_id.lower()}.png"
    try:
        async with session.get(
            url,
            headers=build_headers(),
            timeout=aiohttp.ClientTimeout(total=20),
        ) as resp:
            if resp.status != 200:
                return False
            data = await resp.read()
            return len(data) >= CDN_MIN_BYTES
    except Exception:
        return False


async def _scan_minifigs_via_cdn(
    session: aiohttp.ClientSession,
    article: str,
    *,
    pad_len: int = 3,
    max_num: int = CDN_MAX_NUM,
) -> list[str]:
    """Линейный скан (legacy). Предпочтительнее _discover_minifigs_via_cdn_smart."""
    article = article.lower()
    found: list[str] = []
    for num in range(1, max_num + 1):
        item_id = f"{article}{num:0{pad_len}d}"
        if await _cdn_minifig_exists(session, item_id):
            found.append(item_id)
    return found


def _sort_item_ids(ids: list[str]) -> list[str]:
    def key(iid: str) -> tuple[str, int, str]:
        m = re.search(r"(\d+)", iid)
        return (iid[: m.start()] if m else iid, int(m.group(1)) if m else 0, iid)

    return sorted(ids, key=key)


async def _discover_minifigs_via_cdn_smart(
    session: aiohttp.ClientSession,
    article: str,
) -> tuple[list[str], int]:
    """
    Универсальный поиск серии: префикс + номер на CDN BrickLink.
    Останавливается после CDN_GAP пустых номеров подряд.
    """
    article = article.lower()
    sem = asyncio.Semaphore(max(1, CDN_CONCURRENCY))

    async def exists(num: int, pad_len: int) -> Optional[str]:
        item_id = f"{article}{num:0{pad_len}d}"
        async with sem:
            if await _cdn_minifig_exists(session, item_id):
                return item_id
        return None

    for pad_len in (3, 4, 2):
        found: list[str] = []
        misses = 0
        num = 1
        while num <= CDN_MAX_NUM:
            batch = range(num, min(num + CDN_BATCH, CDN_MAX_NUM + 1))
            results = await asyncio.gather(*(exists(n, pad_len) for n in batch))
            batch_found = [r for r in results if r]
            if batch_found:
                found.extend(batch_found)
                misses = 0
            elif found:
                misses += len(batch)
                if misses >= CDN_GAP:
                    break
            num += CDN_BATCH
        if found:
            return _sort_item_ids(found), pad_len
    return [], 3


def _series_label_from_api(sample_id: str) -> Optional[str]:
    try:
        from app.business.bricklink_api import (
            BrickLinkItemNotFound,
            api_credentials_configured,
            get_catalog_item,
            get_category_name,
        )

        if not api_credentials_configured():
            return None
        item = get_catalog_item(sample_id)
        cat_id = item.extra.get("category_id")
        if cat_id:
            return get_category_name(int(cat_id))
    except BrickLinkItemNotFound:
        pass
    except Exception:
        logger.debug("series label from API failed for %s", sample_id, exc_info=True)
    return None


async def _resolve_series_label(
    session: aiohttp.ClientSession,
    article: str,
    sample_id: str,
    theme_name: Optional[str],
) -> str:
    if theme_name and _theme_name_usable(theme_name):
        return theme_name.strip()

    label = _series_label_from_api(sample_id)
    if label:
        return label

    if load_bricklink_cookies():
        cat, hint_label = await _try_resolve_cat_optional(session, article, theme_name)
        if hint_label:
            return hint_label

    return article.upper()


async def _try_resolve_cat_optional(
    session: aiohttp.ClientSession,
    article: str,
    theme_name: Optional[str] = None,
    *,
    cached_cat: Optional[str] = None,
) -> tuple[Optional[str], Optional[str]]:
    """catString через catalogList — только если есть cookies (ускорение, не обязательно)."""
    if not load_bricklink_cookies():
        return None, None
    return await resolve_cat_string(
        session,
        article,
        theme_name,
        cached_cat=cached_cat,
        catalog_only=True,
    )


def _resolve_item_name(item_id: str) -> str:
    try:
        from app.business.bricklink_api import (
            BrickLinkItemNotFound,
            api_credentials_configured,
            get_catalog_item,
        )

        if api_credentials_configured():
            item = get_catalog_item(item_id)
            return item.name or item_id
    except BrickLinkItemNotFound:
        pass
    except Exception:
        logger.debug("API name lookup failed for %s", item_id, exc_info=True)
    return item_id


async def _fetch_minifigs_via_cdn_scan(
    session: aiohttp.ClientSession,
    article: str,
    pad_len: int = 3,
) -> list[tuple[str, str]]:
    ids, _ = await _discover_minifigs_via_cdn_smart(session, article)
    return [(iid, _resolve_item_name(iid)) for iid in ids]


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
    catalog_only: bool = False,
) -> tuple[Optional[str], Optional[str]]:
    """
    catString для catalogList (нужны cookies). Для новых серий не обязателен —
    основной путь: CDN-скан по префиксу.
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

    hint_cat, hint_label = _resolve_cat_from_hints(_tree_cache, article)
    if hint_cat:
        count = await _count_items_on_page(session, hint_cat, article)
        if count >= 1:
            _cat_cache[article] = hint_cat
            logger.info(
                "[%s] BrickLink catString=%s («%s», %s на 1-й стр.)",
                article,
                hint_cat,
                hint_label or "?",
                count,
            )
            return hint_cat, hint_label
        cdn_ids = await _scan_minifigs_via_cdn(session, article, max_num=12)
        if cdn_ids:
            _cat_cache[article] = hint_cat
            logger.info(
                "[%s] CDN fallback: catString=%s («%s», %s минифигурок)",
                article,
                hint_cat,
                hint_label or "?",
                len(cdn_ids),
            )
            return hint_cat, hint_label

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

    if catalog_only:
        return None, None

    cdn_ids, _ = await _discover_minifigs_via_cdn_smart(session, article)
    if cdn_ids:
        logger.info(
            "[%s] catalogList недоступен, серия подтверждена CDN (%s шт.)",
            article,
            len(cdn_ids),
        )
        return None, None

    logger.warning("[%s] Серия не найдена (ни catalogList, ни CDN)", article)
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
    Метаданные серии для type_of_collect.
    Универсально: любой префикс BrickLink через CDN, без ручных подсказок.
    """
    article = article.strip().lower()
    async with aiohttp.ClientSession() as session:
        ids, pad_len = await _discover_minifigs_via_cdn_smart(session, article)
        if not ids:
            logger.warning("[%s] CDN: ни одной минифигурки с таким префиксом", article)
            return None

        label = await _resolve_series_label(session, article, ids[0], theme_name)
        cat, _ = await _try_resolve_cat_optional(session, article, theme_name)

        logger.info(
            "[%s] серия найдена: %s шт., pad=%s, name=%r",
            article,
            len(ids),
            pad_len,
            label,
        )
        return {
            "name": label,
            "pad_len": pad_len,
            "cat_string": cat,
            "sample_count": len(ids),
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
        ids, pad_len = await _discover_minifigs_via_cdn_smart(session, article)
        if not ids:
            return [], None, None

        for item_id in ids:
            collected[item_id] = _resolve_item_name(item_id)

        cat, label = await _try_resolve_cat_optional(
            session,
            article,
            theme_name or None,
            cached_cat=bricklink_cat,
        )
        resolved_cat = cat
        resolved_label = label

        if cat and load_bricklink_cookies():
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
                if not html_text:
                    break
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
                page += 1
                if delay_sec > 0 and REQUEST_DELAY <= 0:
                    await asyncio.sleep(delay_sec)
        else:
            logger.info(
                "[%s] загрузка через CDN: %s шт. (pad=%s)",
                article,
                len(collected),
                pad_len,
            )

    return sorted(collected.items()), resolved_cat, resolved_label
