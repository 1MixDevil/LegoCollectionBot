"""Безопасная работа с сообщениями Telegram (текст / фото / документ)."""

from __future__ import annotations

from aiogram import types
from aiogram.exceptions import TelegramBadRequest


async def safe_edit_or_answer(
    message: types.Message,
    text: str,
    *,
    reply_markup=None,
    parse_mode: str | None = None,
) -> types.Message:
    """
    Редактирует сообщение, если в нём есть текст; иначе отправляет новое.
    Нужно для callback на фото/документах (tier-list, коллаж и т.д.).
    """
    if message.text:
        try:
            return await message.edit_text(
                text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
        except TelegramBadRequest:
            pass

    return await message.answer(
        text,
        reply_markup=reply_markup,
        parse_mode=parse_mode,
    )


async def answer_callback(
    call: types.CallbackQuery,
    text: str,
    *,
    reply_markup=None,
    parse_mode: str | None = None,
) -> types.Message:
    await call.answer()
    return await safe_edit_or_answer(
        call.message,
        text,
        reply_markup=reply_markup,
        parse_mode=parse_mode,
    )
