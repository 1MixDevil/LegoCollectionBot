"""Название tier-list для коллажа и подписи Telegram."""

from __future__ import annotations

import os

from app.utils.serial_parse import parse_serial_list

TIERLIST_TITLE_MAX = int(os.getenv("TIERLIST_TITLE_MAX", "40"))


def looks_like_serial_list(text: str) -> bool:
    serials = parse_serial_list((text or "").strip())
    return bool(serials and len(serials) >= 2)


def normalize_tierlist_title(
    title: str | None,
    *,
    figure_count: int = 0,
) -> str:
    """
    Короткое имя для коллажа/подписи (≤ TIERLIST_TITLE_MAX).
    Список артикулов в поле «название» не используется как title.
    """
    raw = (title or "").strip()
    if looks_like_serial_list(raw):
        raw = ""
    if not raw:
        if figure_count > 0:
            raw = f"Tier-list ({figure_count})"
        else:
            raw = "Tier-list"
    if len(raw) > TIERLIST_TITLE_MAX:
        raw = raw[: TIERLIST_TITLE_MAX - 1].rstrip() + "…"
    return raw
