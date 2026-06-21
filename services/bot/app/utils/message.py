"""Безопасная работа с сообщениями Telegram (текст / фото / документ)."""

from __future__ import annotations

from aiogram import types
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError

from app.utils.telegram_network import safe_callback_answer, with_telegram_retry


async def safe_edit_or_answer(
    message: types.Message,
    text: str,
    *,
    reply_markup=None,
    parse_mode: str | None = None,
    disable_web_page_preview: bool = False,
) -> types.Message:
    """
    Редактирует сообщение, если в нём есть текст; иначе отправляет новое.
    Нужно для callback на фото/документах (tier-list, коллаж и т.д.).
    """
    preview_kw = (
        {"disable_web_page_preview": True} if disable_web_page_preview else {}
    )
    if message.text:
        try:
            return await message.edit_text(
                text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                **preview_kw,
            )
        except (TelegramBadRequest, TelegramNetworkError):
            pass

    try:
        return await with_telegram_retry(
            lambda: message.answer(
                text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                **preview_kw,
            ),
            label="message.answer",
        )
    except TelegramNetworkError:
        raise


async def answer_callback(
    call: types.CallbackQuery,
    text: str,
    *,
    reply_markup=None,
    parse_mode: str | None = None,
) -> types.Message:
    await safe_callback_answer(call)
    return await safe_edit_or_answer(
        call.message,
        text,
        reply_markup=reply_markup,
        parse_mode=parse_mode,
    )
