"""Главное меню бота."""

from __future__ import annotations

from aiogram.types import Message

from app.core.access import get_main_keyboard

MAIN_MENU_HTML = "📋 <b>Главное меню</b>"


async def send_main_menu(
    message: Message,
    telegram_id: str,
    *,
    text: str | None = None,
) -> None:
    kb = await get_main_keyboard(telegram_id)
    await message.answer(text or MAIN_MENU_HTML, parse_mode="HTML", reply_markup=kb)
