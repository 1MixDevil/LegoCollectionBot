"""Синхронная сборка коллажа (Celery worker)."""

from __future__ import annotations

import asyncio
import logging
import os

from app.services.collage import StarWarsCollageGenerator
from app.services.collage_config import (
    COLLAGE_COLUMNS,
    COLLAGE_MIN_HEIGHT,
    CONCURRENT_BATCHES,
    PREFIX_URL,
    TMP_DIR,
    output_paths,
)
from app.services.tierlist_title import normalize_tierlist_title

logger = logging.getLogger(__name__)


def build_caption(
    caption_prefix: str,
    title: str,
    caption_extra: str,
    records: list[dict],
    owned_ids: frozenset[str] | None,
) -> str:
    from app.services.collage_config import owned_stats_caption

    short_title = normalize_tierlist_title(title, figure_count=len(records))
    if short_title:
        caption = f"{caption_prefix} «{short_title}» готов!"
    else:
        caption = f"{caption_prefix} готов!"
    if caption_extra:
        caption += f" ({caption_extra})"
    caption += owned_stats_caption(records, owned_ids)
    return caption.strip()


def sync_build_collage(
    records: list[dict],
    telegram_id: str,
    title: str,
    *,
    owned_ids: frozenset[str] | None = None,
) -> tuple[str, str] | None:
    collage_title = normalize_tierlist_title(title, figure_count=len(records))
    path, base_name = output_paths(telegram_id, collage_title)
    os.makedirs(TMP_DIR, exist_ok=True)
    placed = asyncio.run(
        StarWarsCollageGenerator.build_collage_to_file(
            records,
            path,
            id_key="bricklink_id",
            prefix_url=PREFIX_URL,
            min_height=COLLAGE_MIN_HEIGHT,
            columns=COLLAGE_COLUMNS,
            title=collage_title or None,
            max_connections=CONCURRENT_BATCHES,
            owned_ids=owned_ids,
        )
    )
    if placed <= 0:
        return None
    if not path.lower().endswith((".jpg", ".jpeg")):
        jpg = path.rsplit(".", 1)[0] + ".jpg"
        if os.path.isfile(jpg):
            return jpg, os.path.basename(jpg)
    return path, base_name
