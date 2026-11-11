"""BrickLink id → URL картинки через CSV-дампы Rebrickable.

img.bricklink.com с датацентров часто отвечает 302 на maintenance HTML
(AWS WAF / recovery). CDN Rebrickable отдаёт реальные JPEG.
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


async def resolve_image_url(
    bricklink_id: str,
    *,
    prefix_url: str = "https://img.bricklink.com/ItemImage/MN/0",
) -> str:
    bid = bricklink_id.strip().lower()
    urls = await get_bricklink_image_urls()
    if bid in urls:
        return urls[bid]
    prefix = prefix_url.rstrip("/")
    return f"{prefix}/{bid}.png"
