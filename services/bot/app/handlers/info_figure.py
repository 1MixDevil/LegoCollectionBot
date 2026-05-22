import re

from aiogram import Bot, Router, types
from aiogram.fsm.context import FSMContext
from httpx import HTTPStatusError

from app.api.collection import (
    add_figure_to_user,
    delete_figure_from_user,
    fetch_similar_serials,
)
from app.core.config import MAX_SERIALS_PER_REQUEST
from app.keyboards.main import main_kb, make_suggestions_kb, nav_kb
from app.services.figure_display import send_figure_card
from app.states.figures import InfoFigures

router = Router()


@router.callback_query(lambda cb: cb.data == "info")
async def cb_info(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer(
        "Введите серийные номера фигурок через запятую (,) или точку с запятой (;), или один номер:",
        reply_markup=nav_kb(),
    )
    await state.set_state(InfoFigures.waiting_serial)
    await call.answer()


@router.message(InfoFigures.waiting_serial)
async def get_info_figure(message: types.Message, state: FSMContext):
    text = message.text.strip()
    telegram_id = str(message.from_user.id)
    serials = [s.strip() for s in re.split(r"[,; ]", text) if s.strip()]

    if len(serials) > MAX_SERIALS_PER_REQUEST:
        await message.answer(
            f"❗️ Вы можете запрашивать не более {MAX_SERIALS_PER_REQUEST} артикула за раз.",
            reply_markup=nav_kb(),
        )
        return

    for serial in serials:
        await handle_serial(serial, message.bot, message.chat.id, telegram_id)


@router.callback_query(lambda cb: cb.data and cb.data.startswith("select_similar:"))
async def cb_info_select(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    _, serial = call.data.split(":", 1)
    await call.message.delete()
    telegram_id = str(call.from_user.id)
    await handle_serial(serial, call.bot, call.message.chat.id, telegram_id)


async def handle_serial(serial: str, bot: Bot, chat_id: int, telegram_id: str):
    serial = serial.strip().lower()
    try:
        in_catalog = await send_figure_card(bot, chat_id, telegram_id, serial)
    except HTTPStatusError as error:
        await bot.send_message(
            chat_id,
            f"Ошибка сервиса для {serial}: {error.response.status_code}",
            reply_markup=nav_kb(),
        )
        return
    except Exception:
        await bot.send_message(
            chat_id,
            f"Ошибка получения информации для {serial}.",
            reply_markup=nav_kb(),
        )
        return

    if not in_catalog:
        suggestions = await fetch_similar_serials(serial)
        if suggestions:
            kb = make_suggestions_kb(suggestions)
            await bot.send_message(
                chat_id,
                "Похожие варианты в каталоге бота:",
                reply_markup=kb,
            )


@router.callback_query(lambda cb: cb.data and cb.data.startswith("info_action:"))
async def cb_info_actions(call: types.CallbackQuery):
    parts = call.data.split(":")
    if len(parts) < 3:
        await call.answer("Функционал пока не реализован.", show_alert=True)
        return
    _, action, serial = parts[0], parts[1], parts[2]
    telegram_id = str(call.from_user.id)

    if action in ("buy", "sell"):
        await call.answer("Функционал пока не реализован.", show_alert=True)
    elif action == "wishlist":
        await call.answer("Функционал пока не реализован.", show_alert=True)
    elif action == "add":
        try:
            await add_figure_to_user(telegram_id=telegram_id, bricklink_id=serial)
            await call.answer("Фигурка добавлена!", show_alert=True)
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                await call.answer(
                    "Фигурка не найдена в каталоге. «🔄 Обновить каталог» или «❓ Помощь».",
                    show_alert=True,
                )
            else:
                await call.answer("Ошибка добавления.", show_alert=True)
    elif action == "delete":
        try:
            await delete_figure_from_user(telegram_id, serial)
            await call.answer("Фигурка удалена!", show_alert=True)
        except HTTPStatusError:
            await call.answer("Не удалось удалить.", show_alert=True)
    else:
        await call.answer("Функционал пока не реализован.", show_alert=True)
