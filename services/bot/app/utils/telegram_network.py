"""Повторы и безопасные вызовы API Telegram при обрывах сети."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable
from typing import TypeVar

from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError

logger = logging.getLogger(__name__)

T = TypeVar("T")

TELEGRAM_RETRY_ATTEMPTS = int(os.getenv("TELEGRAM_RETRY_ATTEMPTS", "3"))
TELEGRAM_RETRY_DELAY = float(os.getenv("TELEGRAM_RETRY_DELAY", "2.0"))
TELEGRAM_DOCUMENT_TIMEOUT = float(os.getenv("TELEGRAM_DOCUMENT_TIMEOUT", "600"))


async def with_telegram_retry(
    factory: Callable[[], Awaitable[T]],
    *,
    attempts: int | None = None,
    base_delay: float | None = None,
    label: str = "telegram",
) -> T:
    tries = attempts if attempts is not None else TELEGRAM_RETRY_ATTEMPTS
    delay = base_delay if base_delay is not None else TELEGRAM_RETRY_DELAY
    last: Exception | None = None
    for n in range(tries):
        try:
            return await factory()
        except TelegramNetworkError as exc:
            last = exc
            if n < tries - 1:
                wait = delay * (n + 1)
                logger.warning(
                    "%s: сеть Telegram, повтор %s/%s через %.1f с (%s)",
                    label,
                    n + 2,
                    tries,
                    wait,
                    exc,
                )
                await asyncio.sleep(wait)
    assert last is not None
    raise last


def is_stale_callback_error(exc: BaseException) -> bool:
    if not isinstance(exc, TelegramBadRequest):
        return False
    msg = (getattr(exc, "message", None) or str(exc)).lower()
    return (
        "query is too old" in msg
        or "query id is invalid" in msg
        or "response timeout expired" in msg
    )


async def safe_callback_answer(
    call,
    text: str | None = None,
    *,
    show_alert: bool = False,
) -> bool:
    """Ответ на callback. False — устаревшая кнопка или сеть."""
    try:
        await with_telegram_retry(
            lambda: call.answer(text, show_alert=show_alert),
            label="callback.answer",
        )
        return True
    except TelegramNetworkError:
        logger.warning("callback.answer не доставлен (сеть)")
        return False
    except TelegramBadRequest as exc:
        if is_stale_callback_error(exc):
            logger.debug("stale callback ignored: %s", exc)
            return False
        raise


async def safe_message_answer(message, *args, **kwargs):
    return await with_telegram_retry(
        lambda: message.answer(*args, **kwargs),
        label="message.answer",
    )
