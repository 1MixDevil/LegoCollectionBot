"""Лимиты размера tier-list / коллажа по роли."""

from __future__ import annotations

import os

from app.core.permissions import ROLE_ADMIN, ROLE_PREMIUM, normalize_role

COLLAGE_FORCE_BATCH_ABOVE = int(os.getenv("COLLAGE_FORCE_BATCH_ABOVE", "40"))
COLLAGE_BATCH_SIZE = int(
    os.getenv("COLLAGE_BATCH_SIZE", os.getenv("BATCH_SIZE", "40"))
)

TIERLIST_MAX_MEMBER = int(os.getenv("TIERLIST_MAX_FIGURES_MEMBER", "80"))
TIERLIST_MAX_PREMIUM = int(os.getenv("TIERLIST_MAX_FIGURES_PREMIUM", "150"))
TIERLIST_MAX_ADMIN = int(os.getenv("TIERLIST_MAX_FIGURES_ADMIN", "500"))


def tierlist_max_figures(role: str | None) -> int:
    role = normalize_role(role)
    if role == ROLE_ADMIN:
        return TIERLIST_MAX_ADMIN
    if role == ROLE_PREMIUM:
        return TIERLIST_MAX_PREMIUM
    return TIERLIST_MAX_MEMBER


def should_send_in_batches(total: int) -> bool:
    return total > COLLAGE_FORCE_BATCH_ABOVE


def cap_tierlist_records(records: list[dict], role: str | None) -> tuple[list[dict], int]:
    """Обрезает список до лимита роли. Возвращает (список, сколько отброшено)."""
    limit = tierlist_max_figures(role)
    if len(records) <= limit:
        return records, 0
    return records[:limit], len(records) - limit
