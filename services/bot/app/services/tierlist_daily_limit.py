"""Дневной лимит создания tier-list / коллажей на пользователя."""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta, timezone

import redis

from app.core.permissions import ROLE_ADMIN

logger = logging.getLogger(__name__)

TIERLIST_DAILY_LIMIT = int(os.getenv("TIERLIST_DAILY_LIMIT", "5"))
_REDIS_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
_KEY_PREFIX = "tierlist_daily"


def _redis() -> redis.Redis:
    return redis.from_url(_REDIS_URL, decode_responses=True)


def _day_key(telegram_id: str) -> str:
    day = date.today().isoformat()
    return f"{_KEY_PREFIX}:{telegram_id}:{day}"


def _seconds_until_utc_midnight() -> int:
    now = datetime.now(timezone.utc)
    tomorrow = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return max(60, int((tomorrow - now).total_seconds()))


def tierlist_limit_for_role(role: str) -> int | None:
    """None = без лимита (admin или TIERLIST_DAILY_LIMIT=0)."""
    if role == ROLE_ADMIN:
        return None
    if TIERLIST_DAILY_LIMIT <= 0:
        return None
    return TIERLIST_DAILY_LIMIT


def get_tierlist_usage(telegram_id: str, role: str) -> tuple[int, int | None]:
    """Сколько уже создано сегодня и лимит (None = без лимита)."""
    limit = tierlist_limit_for_role(role)
    if limit is None:
        return 0, None
    try:
        used = int(_redis().get(_day_key(telegram_id)) or 0)
    except redis.RedisError:
        logger.exception("tierlist limit: redis read failed")
        return 0, limit
    return used, limit


def try_consume_tierlist(telegram_id: str, role: str) -> tuple[bool, int, int | None]:
    """
    Резервирует один tier-list на сегодня.
    Возвращает (разрешено, использовано_после_успеха, лимит_или_None).
    """
    limit = tierlist_limit_for_role(role)
    if limit is None:
        return True, 0, None

    key = _day_key(telegram_id)
    try:
        client = _redis()
        new_count = int(client.incr(key))
        if new_count == 1:
            client.expire(key, _seconds_until_utc_midnight())
        if new_count > limit:
            client.decr(key)
            return False, limit, limit
        return True, new_count, limit
    except redis.RedisError:
        logger.exception("tierlist limit: redis unavailable, allowing request")
        return True, 0, limit


def format_limit_denied_message(used: int, limit: int) -> str:
    word = "коллаж" if limit == 1 else "коллажей"
    return (
        f"⛔ <b>Дневной лимит коллажей</b>\n\n"
        f"Сегодня можно создать не больше <b>{limit}</b> {word}.\n"
        f"Использовано: <b>{used}/{limit}</b>.\n\n"
        "Лимит обновится завтра."
    )


def format_limit_accept_hint(used: int, limit: int | None) -> str | None:
    if limit is None:
        return None
    left = max(0, limit - used)
    if left == 0:
        return None
    return f"ℹ️ Коллажей сегодня: <b>{used}/{limit}</b> (осталось {left})."
