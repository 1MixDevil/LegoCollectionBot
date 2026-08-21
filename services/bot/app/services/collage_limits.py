"""Лимиты размера tier-list / коллажа по роли (env + настройки из auth)."""

from __future__ import annotations

import logging
import os
import time

from app.core.permissions import ROLE_ADMIN, ROLE_PREMIUM, normalize_role

logger = logging.getLogger(__name__)

# Дефолты из окружения (если в админке ничего не задано)
_ENV_DEFAULTS: dict[str, int] = {
    "collage_force_batch_above": int(os.getenv("COLLAGE_FORCE_BATCH_ABOVE", "40")),
    "collage_batch_size": int(
        os.getenv("COLLAGE_BATCH_SIZE", os.getenv("BATCH_SIZE", "40"))
    ),
    "tierlist_max_member": int(os.getenv("TIERLIST_MAX_FIGURES_MEMBER", "80")),
    "tierlist_max_premium": int(os.getenv("TIERLIST_MAX_FIGURES_PREMIUM", "150")),
    "tierlist_max_admin": int(os.getenv("TIERLIST_MAX_FIGURES_ADMIN", "500")),
    "max_serials_per_request": int(os.getenv("MAX_SERIALS_PER_REQUEST", "50")),
}

LIMIT_KEYS = tuple(_ENV_DEFAULTS.keys())

LIMIT_LABELS: dict[str, str] = {
    "collage_batch_size": "Размер батча коллажа",
    "collage_force_batch_above": "Дробить коллаж, если больше",
    "tierlist_max_member": "Макс. фигурок (member)",
    "tierlist_max_premium": "Макс. фигурок (premium)",
    "tierlist_max_admin": "Макс. фигурок (admin)",
    "max_serials_per_request": "Макс. артикулов за ввод",
}

_cache: dict[str, int] | None = None
_cache_at: float = 0.0
_CACHE_TTL = 15.0


def _defaults() -> dict[str, int]:
    return dict(_ENV_DEFAULTS)


def _fetch_overrides() -> dict[str, int]:
    try:
        from app.api.auth import get_collage_limits_sync

        raw = get_collage_limits_sync()
    except Exception:
        logger.debug("collage limits fetch failed", exc_info=True)
        return {}
    out: dict[str, int] = {}
    for key in LIMIT_KEYS:
        if key not in raw:
            continue
        try:
            out[key] = max(1, int(raw[key]))
        except (TypeError, ValueError):
            continue
    return out


def get_limits(*, force_refresh: bool = False) -> dict[str, int]:
    global _cache, _cache_at
    now = time.monotonic()
    if (
        not force_refresh
        and _cache is not None
        and (now - _cache_at) < _CACHE_TTL
    ):
        return dict(_cache)
    merged = _defaults()
    merged.update(_fetch_overrides())
    _cache = dict(merged)
    _cache_at = now
    return merged


def invalidate_limits_cache() -> None:
    global _cache, _cache_at
    _cache = None
    _cache_at = 0.0


# Обратная совместимость: константы = дефолты env (для импортов/сообщений об ошибках)
COLLAGE_FORCE_BATCH_ABOVE = _ENV_DEFAULTS["collage_force_batch_above"]
COLLAGE_BATCH_SIZE = _ENV_DEFAULTS["collage_batch_size"]
TIERLIST_MAX_MEMBER = _ENV_DEFAULTS["tierlist_max_member"]
TIERLIST_MAX_PREMIUM = _ENV_DEFAULTS["tierlist_max_premium"]
TIERLIST_MAX_ADMIN = _ENV_DEFAULTS["tierlist_max_admin"]


def collage_batch_size() -> int:
    return get_limits()["collage_batch_size"]


def collage_force_batch_above() -> int:
    return get_limits()["collage_force_batch_above"]


def max_serials_per_request() -> int:
    return get_limits()["max_serials_per_request"]


def tierlist_max_figures(role: str | None) -> int:
    role = normalize_role(role)
    limits = get_limits()
    if role == ROLE_ADMIN:
        return limits["tierlist_max_admin"]
    if role == ROLE_PREMIUM:
        return limits["tierlist_max_premium"]
    return limits["tierlist_max_member"]


def should_send_in_batches(total: int) -> bool:
    return total > collage_force_batch_above()


def cap_tierlist_records(records: list[dict], role: str | None) -> tuple[list[dict], int]:
    """Обрезает список до лимита роли. Возвращает (список, сколько отброшено)."""
    limit = tierlist_max_figures(role)
    if len(records) <= limit:
        return records, 0
    return records[:limit], len(records) - limit
