"""ID администраторов, известные боту (синхронно с auth-service)."""

import os
from typing import Final

PERMANENT_ADMIN_TELEGRAM_IDS: Final[frozenset[str]] = frozenset({"539686459"})


def permanent_admin_ids() -> frozenset[str]:
    from_env = {
        x.strip()
        for x in os.getenv("ADMIN_TELEGRAM_IDS", "").split(",")
        if x.strip()
    }
    return PERMANENT_ADMIN_TELEGRAM_IDS | from_env
