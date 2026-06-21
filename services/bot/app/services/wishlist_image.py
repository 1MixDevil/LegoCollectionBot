"""Картинка для желания: каталог бота → Brave site:bricklink.com → img.bricklink.com."""

from __future__ import annotations

import logging
import re

import httpx

from app.api.collection import search_figures_by_keyword

logger = logging.getLogger(__name__)

NOISE_WORDS = frozenset({"lego", "лego", "набор", "фигурка", "минифигурка"})
MINIFIG_REF_RE = re.compile(r"catalogitem\.page\?M=([a-z0-9]+)", re.I)
SET_REF_RE = re.compile(r"catalogitem\.page\?S=(\d+(?:-\d+)?)", re.I)
MIN_IMAGE_BYTES = 800
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}


async def _fetch_bytes(client: httpx.AsyncClient, url: str) -> bytes | None:
    try:
        resp = await client.get(url, headers=HEADERS, follow_redirects=True)
        if resp.status_code != 200:
            return None
        data = resp.content
        if len(data) < MIN_IMAGE_BYTES:
            return None
        ctype = (resp.headers.get("content-type") or "").lower()
        if ctype and "image" not in ctype and not url.lower().endswith(
            (".png", ".jpg", ".jpeg", ".webp")
        ):
            return None
        return data
    except Exception:
        logger.debug("fetch image failed %s", url, exc_info=True)
        return None


def _search_words(title: str) -> str:
    words = [w for w in title.split() if w.strip() and w.lower() not in NOISE_WORDS]
    return " ".join(words) if words else title


async def _fetch_minifig_image(client: httpx.AsyncClient, catalog_id: str) -> bytes | None:
    url = f"https://img.bricklink.com/ItemImage/MN/0/{catalog_id.lower()}.png"
    return await _fetch_bytes(client, url)


async def _fetch_set_image(client: httpx.AsyncClient, set_num: str) -> bytes | None:
    base = set_num.split("-")[0]
    url = f"https://img.bricklink.com/ItemImage/SN/0/{base}-1.png"
    return await _fetch_bytes(client, url)


async def _catalog_bricklink_id(title: str) -> str | None:
    query = _search_words(title)
    try:
        for q in (query, title):
            rows = await search_figures_by_keyword(q, limit=1)
            if rows:
                bid = (rows[0].get("bricklink_id") or "").strip().lower()
                if bid:
                    logger.info("wishlist image: catalog hit %s for %r", bid, title)
                    return bid
    except Exception:
        logger.warning("catalog search failed for %r", title, exc_info=True)
    return None


def _refs_from_search_html(html: str) -> list[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    refs: list[tuple[str, str]] = []
    for match in MINIFIG_REF_RE.finditer(html):
        ref = ("minifig", match.group(1).lower())
        if ref not in seen:
            seen.add(ref)
            refs.append(ref)
    for match in SET_REF_RE.finditer(html):
        base = match.group(1).split("-")[0]
        ref = ("set", base)
        if ref not in seen:
            seen.add(ref)
            refs.append(ref)
    return refs


async def _web_search_refs(client: httpx.AsyncClient, title: str) -> list[tuple[str, str]]:
    query = f"site:bricklink.com {title.strip()}"
    try:
        resp = await client.get(
            "https://search.brave.com/search",
            params={"q": query},
            headers=HEADERS,
            follow_redirects=True,
            timeout=20.0,
        )
        resp.raise_for_status()
        refs = _refs_from_search_html(resp.text)
        if refs:
            logger.info("wishlist image: web search %r -> %s", title, refs[0])
        else:
            logger.info("wishlist image: web search %r -> no refs", title)
        return refs
    except Exception:
        logger.warning("web search failed for %r", title, exc_info=True)
        return []


async def _try_ref(
    client: httpx.AsyncClient, kind: str, catalog_id: str
) -> tuple[bytes | None, str]:
    if kind == "minifig":
        data = await _fetch_minifig_image(client, catalog_id)
        if data:
            return data, f"{catalog_id}.png"
    else:
        data = await _fetch_set_image(client, catalog_id)
        if data:
            return data, f"set_{catalog_id}.png"
    return None, "wishlist.jpg"


async def fetch_wishlist_image(item: dict) -> tuple[bytes | None, str]:
    title = (item.get("title") or "").strip()
    bricklink_id = (item.get("bricklink_id") or "").strip().lower()

    async with httpx.AsyncClient(timeout=20.0) as client:
        if bricklink_id:
            data = await _fetch_minifig_image(client, bricklink_id)
            if data:
                return data, f"{bricklink_id}.png"

        if title:
            catalog_id = await _catalog_bricklink_id(title)
            if catalog_id:
                data = await _fetch_minifig_image(client, catalog_id)
                if data:
                    return data, f"{catalog_id}.png"

            for kind, cid in await _web_search_refs(client, title):
                data, filename = await _try_ref(client, kind, cid)
                if data:
                    return data, filename

    logger.info("wishlist image: nothing found for %r", title or bricklink_id)
    return None, "wishlist.jpg"
