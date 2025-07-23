import re
import httpx
from aiogram import Router, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile
from HttpRequests import add_figure_to_user, delete_figure_to_user
from inlineKeyBoards import main_kb, make_info_kb, make_suggestions_kb, nav_kb
from FMSState import InfoFigures
from config import COLL_BASE
from io import BytesIO
import os

# Максимальное количество артикулов за один запрос
MAX_SERIALS_PER_REQUEST = int(os.getenv("MAX_SERIALS_PER_REQUEST", 50))

router = Router()

@router.callback_query(lambda cb: cb.data == "info")
async def cb_info(call: types.CallbackQuery, state: FSMContext):
    # Запрос серийного номера (или нескольких через , или ;) и установка состояния ожидания
    await call.message.answer(
        "Введите серийные номера фигурок через запятую (,) или точку с запятой (;), или один номер:",
        reply_markup=nav_kb()
    )
    await state.set_state(InfoFigures.waiting_serial)
    await call.answer()

@router.message(InfoFigures.waiting_serial)
async def get_info_figure(message: types.Message, state: FSMContext):
    text = message.text.strip()
    user_id = str(message.from_user.id)
    # Разделяем по запятой или точке с запятой
    serials = [s.strip() for s in re.split(r"[,; ]", text) if s.strip()]
    # Проверяем лимит
    if len(serials) > MAX_SERIALS_PER_REQUEST:
        await message.answer(
            f"❗️ Вы можете запрашивать не более {MAX_SERIALS_PER_REQUEST} артикула за раз.",
            reply_markup=nav_kb()
        )
        return
    for serial in serials:
        await handle_serial(serial, message.bot, message.chat.id, user_id)
    # остаёмся в состоянии ожидания до отмены

@router.callback_query(lambda cb: cb.data and cb.data.startswith("select_similar:"))
async def cb_info_select(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    _, serial = call.data.split(":", 1)
    await call.message.delete()
    user_id = str(call.from_user.id)
    # Обрабатываем выбор похожего серийного номера
    await handle_serial(serial, call.bot, call.message.chat.id, user_id)

async def handle_serial(serial: str, bot: Bot, chat_id: int, user_id: str):
    print("START")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{COLL_BASE}/figure/info/",
                params={"user_id": int(user_id), "bricklink_id": serial}
            )
            response.raise_for_status()
            info = response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            suggestions = await fetch_similar_serials(serial)
            if suggestions:
                kb = make_suggestions_kb(suggestions)
                await bot.send_message(
                    chat_id,
                    "Фигурка не найдена. Возможно, вы имели в виду:",
                    reply_markup=kb
                )
            else:
                await bot.send_message(
                    chat_id,
                    f"Фигурка {serial} не найдена.",
                    reply_markup=nav_kb()
                )
        else:
            await bot.send_message(
                chat_id,
                f"Ошибка сервиса для {serial}: {e.response.status_code}",
                reply_markup=nav_kb()
            )
        return
    except Exception:
        await bot.send_message(
            chat_id,
            f"Ошибка получения информации для {serial}.",
            reply_markup=nav_kb()
        )
        return

    # Показываем информацию
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

    # Отправляем фото, если доступно, иначе только текст
    try:
        async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"}) as client:
            img_resp = await client.get(image_url)
            img_resp.raise_for_status()
            buf = BytesIO(img_resp.content)
            buf.name = image_url.rsplit('/', 1)[-1]
            buf.seek(0)
            file = BufferedInputFile(buf.read(), filename=buf.name)
        await bot.send_photo(
            chat_id=chat_id,
            photo=file,
            caption=caption,
            parse_mode="HTML",
            reply_markup=kb
        )
    except httpx.HTTPStatusError:
        await bot.send_message(
            chat_id,
            caption,
            parse_mode="HTML",
            reply_markup=kb
        )

@router.callback_query(lambda cb: cb.data and cb.data.startswith("info_action:"))
async def cb_info_actions(call: types.CallbackQuery):
    await call.answer()
    _, action, serial = call.data.split(":")
    user_id = str(call.from_user.id)

    if action == "wishlist":
        await call.answer("Добавлено в список желаемого!", show_alert=True)
    elif action == "add":
        await add_figure_to_user(bricklink_id=serial, user_id=user_id)
        await call.answer("Фигурка добавлена!", show_alert=True)
    elif action == "delete":
        await delete_figure_to_user(serial, user_id)
        await call.answer("Фигурка удалена!", show_alert=True)
    else:
        await call.answer()

async def fetch_similar_serials(serial: str) -> list[str]:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{COLL_BASE}/figure/similar/",
            params={"name": serial, "limit": 5, "threshold": 0.3}
        )
        if r.status_code == 200:
            return r.json()
    return []