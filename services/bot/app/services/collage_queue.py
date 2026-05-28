"""Глобальная очередь сборки коллажей (ограничение RAM на сервере)."""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiogram import types

logger = logging.getLogger(__name__)

COLLAGE_MAX_CONCURRENT = max(
    1, int(os.getenv("COLLAGE_MAX_CONCURRENT", "1"))
)

_sem = asyncio.Semaphore(COLLAGE_MAX_CONCURRENT)
_active = 0
_waiting = 0
_lock = asyncio.Lock()


@asynccontextmanager
async def collage_build_slot(message: types.Message | None = None):
    """
    Только N коллажей одновременно на весь бот.
    Остальные ждут с уведомлением в чат.
    """
    global _active, _waiting
    status = None
    wait_no = 0

    async with _lock:
        will_wait = _active >= COLLAGE_MAX_CONCURRENT
        if will_wait:
            _waiting += 1
            wait_no = _waiting

    if will_wait and message is not None:
        try:
            status = await message.answer(
                "⏳ <b>В очереди на сборку коллажа</b>\n"
                f"Сейчас занято слотов: {_active}/{COLLAGE_MAX_CONCURRENT}. "
                "Подождите…",
                parse_mode="HTML",
            )
        except Exception:
            logger.debug("queue notice failed", exc_info=True)

    await _sem.acquire()
    async with _lock:
        if will_wait:
            _waiting = max(0, _waiting - 1)
        _active += 1

    if status is not None:
        try:
            await status.delete()
        except Exception:
            pass

    logger.info(
        "collage slot acquired (active=%s max=%s waited=%s)",
        _active,
        COLLAGE_MAX_CONCURRENT,
        wait_no if will_wait else 0,
    )
    try:
        yield
    finally:
        async with _lock:
            _active = max(0, _active - 1)
        _sem.release()
        logger.info("collage slot released (active=%s)", _active)
