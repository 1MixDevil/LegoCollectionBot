"""
Каталог минифигурок с BrickLink-артикулами через CSV Rebrickable.

BrickLink catalogList сейчас отдаёт AWS WAF challenge (HTTP 202) с датацентров.
Официальный Store API не умеет листинг по префиксу.

Rebrickable ежедневно публикует дампы:
  - minifigs.csv.gz — fig-XXXXX + имя
  - set_mappings.csv.gz — fig-XXXXX ↔ BL/BS/BO (ext_id = sw0001a и т.п.)

Это стабильный источник для /update без cookies и без обхода WAF.
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
from typing import Optional

import httpx

from app.business.bricklink_catalog_list import ARTICLE_KEYWORD_HINTS, infer_pad_len

logger = logging.getLogger("RebrickableCatalogDump")

CDN_BASE = os.getenv(
    "REBRICKABLE_CDN_BASE",
    "https://cdn.rebrickable.com/media/downloads",
).rstrip("/")
CACHE_DIR = Path(os.getenv("REBRICKABLE_CACHE_DIR", "/tmp/rebrickable_catalog"))
CACHE_TTL_SEC = int(os.getenv("REBRICKABLE_CACHE_TTL_SEC", str(12 * 3600)))

MINIFIGS_FILE = "minifigs.csv.gz"
MAPPINGS_FILE = "set_mappings.csv.gz"


def _series_display_name(article: str) -> str:
    hints = ARTICLE_KEYWORD_HINTS.get(article.lower()) or []
    if hints:
        return hints[0].title()
    return article.upper()


def _cache_path(name: str) -> Path:
    return CACHE_DIR / name


def _is_fresh(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size < 100:
        return False
    age = time.time() - path.stat().st_mtime
    return age < CACHE_TTL_SEC


async def _download(client: httpx.AsyncClient, filename: str, dest: Path) -> None:
    url = f"{CDN_BASE}/{filename}"
    logger.info("Скачиваю %s → %s", url, dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    async with client.stream("GET", url, timeout=120.0, follow_redirects=True) as resp:
        resp.raise_for_status()
        with open(tmp, "wb") as f:
            async for chunk in resp.aiter_bytes():
                f.write(chunk)
    tmp.replace(dest)
    logger.info("Готово %s (%s байт)", filename, dest.stat().st_size)


async def ensure_dumps(*, force: bool = False) -> tuple[Path, Path]:
    """Гарантирует свежие gzip-дампы на диске."""
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


def load_bricklink_minifigs() -> dict[str, str]:
    """
    bricklink_id → name (официальные LEGO-минифигурки с маппингом BL).
    При дубликатах BL id оставляем первое имя.
    """
    minifigs_path = _cache_path(MINIFIGS_FILE)
    mappings_path = _cache_path(MAPPINGS_FILE)
    if not minifigs_path.is_file() or not mappings_path.is_file():
        raise FileNotFoundError(
            "Нет кэша Rebrickable CSV — сначала вызовите ensure_dumps()"
        )

    names = {
        row["fig_num"]: (row.get("name") or "").strip()
        for row in _read_gzip_csv(minifigs_path)
        if row.get("fig_num")
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
        if bl_id in out:
            continue
        name = names.get(fig) or bl_id
        out[bl_id] = name

    logger.info("Rebrickable dump: %s минифигурок с BrickLink id", len(out))
    return out


async def fetch_minifigs_by_prefix(article: str) -> list[tuple[str, str]]:
    """Пары (bricklink_id, name) с префиксом article (sw, hp, njo, …)."""
    article = article.strip().lower()
    await ensure_dumps()
    catalog = load_bricklink_minifigs()
    records = sorted(
        (bid, name) for bid, name in catalog.items() if bid.startswith(article)
    )
    logger.info("[%s] Rebrickable dump: %s шт.", article, len(records))
    return records


async def discover_series_from_dump(article: str) -> Optional[dict[str, object]]:
    """Метаданные серии без запросов к BrickLink."""
    article = article.strip().lower()
    records = await fetch_minifigs_by_prefix(article)
    if not records:
        return None
    ids = [rid for rid, _ in records]
    return {
        "name": _series_display_name(article),
        "pad_len": infer_pad_len(ids, article),
        "cat_string": None,
        "sample_count": len(records),
        "source": "rebrickable_dump",
    }
