"""Общие настройки коллажа (бот + Celery worker)."""

from __future__ import annotations

import os
import re
import uuid

TMP_DIR = os.getenv("TMP_DIR", "/tmp")
MAX_FILE_BYTES = int(os.getenv("COLLAGE_MAX_FILE_BYTES", str(45 * 1024 * 1024)))
PREFIX_URL = os.getenv(
    "COLL_PREFIX_URL", "https://img.bricklink.com/ItemImage/MN/0"
)
COLLAGE_COLUMNS = int(os.getenv("COLL_COLUMNS", "5"))
COLLAGE_MIN_HEIGHT = int(os.getenv("COLL_MIN_HEIGHT", "800"))
COLLAGE_IMAGE_FORMAT = os.getenv("COLLAGE_IMAGE_FORMAT", "jpeg").lower()
CONCURRENT_BATCHES = max(1, int(os.getenv("CONCURRENT_BATCHES", "4")))


def output_paths(telegram_id: str, title: str) -> tuple[str, str]:
    safe_title = re.sub(r'[<>:"/\\|?*]', "_", title or "")[:80]
    base_name = f"collage_{telegram_id}"
    if safe_title:
        base_name += f"_{safe_title}"
    base_name = re.sub(r"\s+", "_", base_name)[:160]
    ext = ".jpg" if COLLAGE_IMAGE_FORMAT == "jpeg" else ".png"
    base_name = f"{base_name}_{uuid.uuid4().hex[:8]}{ext}"
    return os.path.join(TMP_DIR, base_name), base_name


def owned_stats_caption(
    records: list[dict],
    owned_ids: frozenset[str] | None,
) -> str:
    if owned_ids is None:
        return ""
    total = len(records)
    if total == 0:
        return ""
    owned_count = sum(
        1
        for r in records
        if (r.get("bricklink_id") or "").lower() in owned_ids
    )
    not_owned = total - owned_count
    return (
        f"\n\n❌ <b>В коллекции:</b> {owned_count} · "
        f"<b>нет в коллекции:</b> {not_owned} (всего {total})"
    )
