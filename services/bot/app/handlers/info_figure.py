import re
from io import BytesIO

import httpx
from aiogram import Bot, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile
from httpx import HTTPStatusError

from app.api.collection import (
    add_figure_to_user,
    delete_figure_from_user,
    fetch_similar_serials,
    get_figure_info,
)
from app.core.config import MAX_SERIALS_PER_REQUEST
from app.keyboards.main import main_kb, make_info_kb, make_suggestions_kb, nav_kb
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
    try:
        info = await get_figure_info(telegram_id, serial)
    except HTTPStatusError as error:
        if error.response.status_code == 404:
            suggestions = await fetch_similar_serials(serial)
            if suggestions:
                kb = make_suggestions_kb(suggestions)
                await bot.send_message(
                    chat_id,
                    "Фигурка не найдена. Возможно, вы имели в виду:",
                    reply_markup=kb,
                )
            else:
                await bot.send_message(
                    chat_id,
                    f"Фигурка {serial} не найдена.",
                    reply_markup=nav_kb(),
                )
        else:
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

    user_rec = info.get("user_record") or {}
    caption = (
        f"🔍 <b>{info['name']}</b>\n"
        f"• Артикул: <code>{info['bricklink_id']}</code>\n"
        f"• Цена покупки: {user_rec.get('price_buy') or '–'}\n"
        f"• Цена продажи: {user_rec.get('price_sale') or '–'}\n"
        f"• Описание: {user_rec.get('description') or '–'}\n"
        f"• Дата покупки: {user_rec.get('buy_date') or '–'}\n"
        f"• Дата продажи: {user_rec.get('sale_date') or '–'}"
    )
    kb = make_info_kb(serial)
    image_url = f"https://img.bricklink.com/ItemImage/MN/0/{serial}.png"

    try:
        async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"}) as client:
            img_resp = await client.get(image_url)
            img_resp.raise_for_status()
            file = BufferedInputFile(img_resp.content, filename=f"{serial}.png")
        await bot.send_photo(
            chat_id=chat_id,
            photo=file,
            caption=caption,
            parse_mode="HTML",
            reply_markup=kb,
        )
    except httpx.HTTPStatusError:
        await bot.send_message(
            chat_id,
            caption,
            parse_mode="HTML",
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
                    "Фигурка не найдена в каталоге. Сначала /update.",
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
