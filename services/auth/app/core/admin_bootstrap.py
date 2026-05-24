"""Постоянные администраторы (владельцы бота)."""

from __future__ import annotations

import os
from typing import Final

# Всегда получают роль admin при регистрации и при каждом входе
PERMANENT_ADMIN_TELEGRAM_IDS: Final[frozenset[str]] = frozenset({"539686459"})


def is_permanent_admin(telegram_username: str) -> bool:
    return telegram_username in PERMANENT_ADMIN_TELEGRAM_IDS


def bootstrap_admin_ids() -> frozenset[str]:
    from_env = {
        x.strip()
        for x in os.getenv("ADMIN_TELEGRAM_IDS", "").split(",")
        if x.strip()
    }
    return PERMANENT_ADMIN_TELEGRAM_IDS | from_env


def resolve_bootstrap_role(telegram_username: str, requested: str | None) -> str:
    if is_permanent_admin(telegram_username) or telegram_username in bootstrap_admin_ids():
        return "admin"
    if requested in {"admin", "member", "premium"}:
        return requested
    return "member"
