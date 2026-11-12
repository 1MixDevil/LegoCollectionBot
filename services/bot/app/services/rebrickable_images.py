"""Картинка минифигурки: несколько источников, пока один не отдаст файл.

Порядок:
  1. JPEG с cdn.rebrickable.com по маппингу BL id (обычно живой с датацентра).
  2. bricker.info PNG — запасной каталог; закрывает BL-only id вроде bob009.
  3. Brickset large JPEG — файл есть, даже когда запись Rebrickable 404
     (bob016: в CSV ссылка есть, самого jpg на CDN нет).
  4. BrickEconomy `{id}_large.jpg` — общий шаблон по любому BL id. Закрывает
     свежие фигурки, которых нет ни у Rebrickable, ни у bricker, ни у Brickset
     (bob040, bob041). Нет файла — HTML 200, его отбрасываем по сигнатуре.
  5. img.bricklink.com PNG/JPG. С датацентров часто 200 + HTML maintenance —
     такое отбрасываем по сигнатуре, а не по статус-коду.

Наборы: JPEG Rebrickable sets/{id}.jpg, затем Brickset и BrickEconomy.
Детали: рендер Rebrickable parts/ldraw/0/{id}.png. Буква каталога P/S/M
берётся из номера, не зашивается как M.
"""

from __future__ import annotations

import csv
import gzip
import io
import logging
import os
import re
import time
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

CDN_BASE = os.getenv(
    "REBRICKABLE_CDN_BASE",
    "https://cdn.rebrickable.com/media/downloads",
).rstrip("/")
CACHE_DIR = Path(os.getenv("REBRICKABLE_CACHE_DIR", "/tmp/rebrickable_catalog"))
CACHE_TTL_SEC = int(os.getenv("REBRICKABLE_CACHE_TTL_SEC", str(12 * 3600)))

MINIFIGS_FILE = "minifigs.csv.gz"
MAPPINGS_FILE = "set_mappings.csv.gz"

_url_cache: dict[str, str] | None = None
_url_cache_loaded_at = 0.0


def _cache_path(name: str) -> Path:
    return CACHE_DIR / name


def _is_fresh(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size < 100:
        return False
    return (time.time() - path.stat().st_mtime) < CACHE_TTL_SEC


async def _download(client: httpx.AsyncClient, filename: str, dest: Path) -> None:
    url = f"{CDN_BASE}/{filename}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    async with client.stream("GET", url, timeout=120.0, follow_redirects=True) as resp:
        resp.raise_for_status()
        with open(tmp, "wb") as f:
            async for chunk in resp.aiter_bytes():
                f.write(chunk)
    tmp.replace(dest)
    logger.info("Rebrickable dump saved %s (%s bytes)", filename, dest.stat().st_size)


async def ensure_dumps(*, force: bool = False) -> tuple[Path, Path]:
    minifigs = _cache_path(MINIFIGS_FILE)
    mappings = _cache_path(MAPPINGS_FILE)
    need = force or not _is_fresh(minifigs) or not _is_fresh(mappings)
    if not need:
        return minifigs, mappings
    async with httpx.AsyncClient() as client:
        if force or not _is_fresh(minifigs):
            await _download(client, MINIFIGS_FILE, minifigs)
        if force or not _is_fresh(mappings):
            await _download(client, MAPPINGS_FILE, mappings)
    return minifigs, mappings


def _read_gzip_csv(path: Path) -> list[dict[str, str]]:
    raw = gzip.decompress(path.read_bytes())
    return list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))


def _build_url_map(minifigs_path: Path, mappings_path: Path) -> dict[str, str]:
    imgs = {
        row["fig_num"]: (row.get("img_url") or "").strip()
        for row in _read_gzip_csv(minifigs_path)
        if row.get("fig_num") and (row.get("img_url") or "").strip()
    }
    out: dict[str, str] = {}
    for row in _read_gzip_csv(mappings_path):
        if row.get("ext_system") != "BL":
            continue
        fig = (row.get("set_num") or "").strip()
        if not fig.startswith("fig-"):
            continue
        bl_id = (row.get("ext_id") or "").strip().lower()
        if not bl_id or not re.match(r"^[a-z]+\d", bl_id):
            continue
        img = imgs.get(fig)
        if not img or bl_id in out:
            continue
        out[bl_id] = img
    return out


async def get_bricklink_image_urls(*, force: bool = False) -> dict[str, str]:
    """bricklink_id (lower) → https://cdn.rebrickable.com/..."""
    global _url_cache, _url_cache_loaded_at
    now = time.time()
    if (
        not force
        and _url_cache is not None
        and (now - _url_cache_loaded_at) < CACHE_TTL_SEC
    ):
        return _url_cache
    minifigs, mappings = await ensure_dumps(force=force)
    _url_cache = _build_url_map(minifigs, mappings)
    _url_cache_loaded_at = now
    logger.info("Rebrickable image map: %s bricklink ids", len(_url_cache))
    return _url_cache


BRICKSET_LARGE = "https://images.brickset.com/minifigs/large/{item_id}.jpg"
BRICKER_PNG = "https://bricker.info/images/minifigs/{item_id}.png"
BRICKECONOMY_LARGE = (
    "https://www.brickeconomy.com/resources/images/minifigs/{item_id}_large.jpg"
)
REBRICKABLE_SET = "https://cdn.rebrickable.com/media/sets/{item_id}.jpg"
BRICKSET_SET = "https://images.brickset.com/sets/images/{item_id}.jpg"
BRICKECONOMY_SET = (
    "https://www.brickeconomy.com/resources/images/sets/{item_id}_large.jpg"
)
REBRICKABLE_PART = "https://cdn.rebrickable.com/media/parts/ldraw/0/{item_id}.png"
_MIN_IMAGE_BYTES = 200


def is_image_payload(content: bytes, content_type: str = "") -> bool:
    """Настоящий JPEG/PNG/GIF/WEBP, а не HTML maintenance и не пустышка."""
    if not content or len(content) < _MIN_IMAGE_BYTES:
        return False
    head = content.lstrip()[:20].lower()
    if head.startswith((b"<!doctype", b"<html", b"<?xml")) or head.startswith(b"<"):
        return False
    ctype = (content_type or "").lower()
    if "html" in ctype or "json" in ctype or "text/" in ctype:
        return False
    if content.startswith(b"\xff\xd8\xff"):
        return True
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    if content.startswith((b"GIF87a", b"GIF89a")):
        return True
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return True
    return False


def response_is_figure_image(status_code: int, content: bytes, content_type: str = "") -> bool:
    """200 и настоящий файл. 404 с PNG-заглушкой — не фото."""
    return status_code == 200 and is_image_payload(content, content_type)


def candidate_image_urls(
    bricklink_id: str,
    mapped: dict[str, str] | None = None,
    *,
    bricklink_prefix: str | None = None,
) -> list[str]:
    """Упорядоченный список URL. Первые — те, что живы, пока BrickLink CDN лежит."""
    from app.utils.bricklink_ids import infer_item_type, item_image_url

    bid = bricklink_id.strip().lower()
    urls: list[str] = []
    mapped_url = (mapped or {}).get(bid)
    if mapped_url:
        urls.append(mapped_url)
    item_type = infer_item_type(bid)
    if item_type == "MINIFIG":
        urls.append(BRICKER_PNG.format(item_id=bid))
        urls.append(BRICKSET_LARGE.format(item_id=bid))
        urls.append(BRICKECONOMY_LARGE.format(item_id=bid))
    elif item_type == "SET":
        urls.append(REBRICKABLE_SET.format(item_id=bid))
        urls.append(BRICKSET_SET.format(item_id=bid))
        urls.append(BRICKECONOMY_SET.format(item_id=bid))
    elif item_type == "PART":
        urls.append(REBRICKABLE_PART.format(item_id=bid))
    png = item_image_url(bid)
    urls.append(png)
    if png.endswith(".png"):
        urls.append(png[:-4] + ".jpg")
    if bricklink_prefix:
        prefix = bricklink_prefix.rstrip("/")
        urls.append(f"{prefix}/{bid}.png")
        urls.append(f"{prefix}/{bid}.jpg")
    seen: set[str] = set()
    out: list[str] = []
    for url in urls:
        if url and url not in seen:
            seen.add(url)
            out.append(url)
    return out


async def fetch_first_image(
    client: httpx.AsyncClient,
    bricklink_id: str,
    mapped: dict[str, str] | None = None,
    *,
    headers: dict[str, str] | None = None,
    bricklink_prefix: str | None = None,
) -> bytes | None:
    hdrs = headers or {"User-Agent": "Mozilla/5.0"}
    bid = bricklink_id.strip().lower()
    for index, url in enumerate(
        candidate_image_urls(bid, mapped, bricklink_prefix=bricklink_prefix)
    ):
        try:
            resp = await client.get(url, headers=hdrs, follow_redirects=True)
        except Exception:
            logger.debug("image candidate failed %s", url, exc_info=True)
            continue
        ctype = resp.headers.get("content-type") or ""
        if response_is_figure_image(resp.status_code, resp.content, ctype):
            if index:
                logger.info("photo %s via %s", bid, url)
            return resp.content
        logger.debug(
            "image candidate rejected %s status=%s ctype=%s",
            url,
            resp.status_code,
            ctype,
        )
    return None


async def download_minifig_image(
    client: httpx.AsyncClient,
    bricklink_id: str,
    *,
    mapped: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    bricklink_prefix: str | None = None,
) -> bytes | None:
    if mapped is None:
        try:
            mapped = await get_bricklink_image_urls()
        except Exception:
            logger.warning("Rebrickable image map unavailable", exc_info=True)
            mapped = {}
    return await fetch_first_image(
        client,
        bricklink_id,
        mapped,
        headers=headers,
        bricklink_prefix=bricklink_prefix,
    )
