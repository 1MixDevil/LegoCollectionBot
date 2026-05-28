"""Постановка коллажей в Celery (бот не собирает тяжёлые файлы сам)."""

from __future__ import annotations

import logging
from typing import Any

from aiogram import types
from aiogram.types import InlineKeyboardMarkup

from app.services.collage_enqueue import (
    enqueue_collage_job,
    estimate_queue_position,
    format_queue_message,
)
from app.services.collage_limits import (
    COLLAGE_BATCH_SIZE,
    should_send_in_batches,
)

logger = logging.getLogger(__name__)


def _parts_from_records(
    records: list[dict],
    title: str,
    caption_prefix: str,
    caption_extra: str,
    owned_ids: frozenset[str] | None,
) -> list[dict[str, Any]]:
    owned_list = sorted(owned_ids) if owned_ids else None
    if not should_send_in_batches(len(records)):
        return [
            {
                "records": records,
                "title": title,
                "caption_prefix": caption_prefix,
                "caption_extra": caption_extra,
                "owned_ids": owned_list,
            }
        ]

    total_batches = (len(records) + COLLAGE_BATCH_SIZE - 1) // COLLAGE_BATCH_SIZE
    parts: list[dict[str, Any]] = []
    for batch_no, start in enumerate(
        range(0, len(records), COLLAGE_BATCH_SIZE), start=1
    ):
        batch = records[start : start + COLLAGE_BATCH_SIZE]
        batch_title = f"{title} {batch_no}/{total_batches}".strip()
        parts.append(
            {
                "records": batch,
                "title": batch_title,
                "caption_prefix": caption_prefix,
                "caption_extra": caption_extra,
                "owned_ids": owned_list,
            }
        )
    return parts


async def generate_and_send_collage(
    records: list[dict],
    telegram_id: str,
    title: str,
    message: types.Message,
    caption_extra: str = "",
    *,
    caption_prefix: str = "Тир-лист",
    reply_markup: InlineKeyboardMarkup | None = None,
    owned_ids: frozenset[str] | None = None,
) -> bool:
    if not records:
        await message.answer(
            "Нет фигурок для коллажа.",
            reply_markup=reply_markup,
        )
        return False

    parts = _parts_from_records(
        records, title, caption_prefix, caption_extra, owned_ids
    )
    position = estimate_queue_position()
    task_id = enqueue_collage_job(
        chat_id=message.chat.id,
        telegram_id=telegram_id,
        parts=parts,
    )
    await message.answer(
        format_queue_message(task_id, position),
        parse_mode="HTML",
        reply_markup=reply_markup,
    )
    if len(parts) > 1:
        await message.answer(
            f"📦 Большой список: <b>{len(parts)}</b> файлов "
            f"(по {COLLAGE_BATCH_SIZE} фигурок).",
            parse_mode="HTML",
        )
    return True


async def send_collage_batches(
    message: types.Message,
    records: list[dict],
    *,
    title: str,
    telegram_id: str,
    caption_label: str = "",
    caption_prefix: str = "Коллаж",
    reply_markup: InlineKeyboardMarkup | None = None,
    owned_ids: frozenset[str] | None = None,
) -> None:
    await generate_and_send_collage(
        records,
        telegram_id,
        title,
        message,
        caption_label,
        caption_prefix=caption_prefix,
        reply_markup=reply_markup,
        owned_ids=owned_ids,
    )
