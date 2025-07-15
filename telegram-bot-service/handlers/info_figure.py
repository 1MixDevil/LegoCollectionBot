import httpx
from aiogram import Router, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile
from HttpRequests import add_figure_to_user, delete_figure_to_user
from inlineKeyBoards import main_kb, make_info_kb, make_suggestions_kb
from FMSState import InfoFigures
from config import COLL_BASE
from io import BytesIO

router = Router()

@router.callback_query(lambda cb: cb.data == "info")
async def cb_info(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer(
        "Введите серийный номер фигурки, о которой хотите получить информацию:"
    )
    await call.message.delete_reply_markup()
    await state.set_state(InfoFigures.waiting_serial)

@router.message(InfoFigures.waiting_serial)
async def get_info_figure(message: types.Message, state: FSMContext):
    serial = message.text.strip()
    user_id = str(message.from_user.id)
    await handle_serial(serial, message.bot, message.chat.id, user_id, state)

@router.callback_query(lambda cb: cb.data and cb.data.startswith("select_similar:"))
async def cb_info_select(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    _, serial = call.data.split(":", 1)
    await call.message.delete()
    user_id = str(call.from_user.id)
    await handle_serial(serial, call.bot, call.message.chat.id, user_id, state)

async def handle_serial(serial: str, bot: Bot, chat_id: int, user_id: str, state: FSMContext):
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{COLL_BASE}/figure/info/",
                params={"user_id": int(user_id), "bricklink_id": serial}
            )
            r.raise_for_status()
            info = r.json()
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
                await bot.send_message(chat_id, "Фигурка не найдена.", reply_markup=main_kb)
        else:
            await bot.send_message(
                chat_id,
                f"Ошибка сервиса: {e.response.status_code}",
                reply_markup=main_kb
            )
        await state.clear()
        return
    except Exception:
        await bot.send_message(chat_id, "Ошибка получения информации.", reply_markup=main_kb)
        await state.clear()
        return

    await display_info(bot, chat_id, info)
    await state.clear()

async def fetch_similar_serials(serial: str) -> list[str]:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{COLL_BASE}/figure/similar/",
            params={"name": serial, "limit": 5, "threshold": 0.3}
        )
        if r.status_code == 200:
            return r.json()
    return []

async def display_info(bot: Bot, chat_id: int, info: dict):
    user_rec = info.get("user_record") or {}
    text = (
        f"🔍 <b>{info['name']}</b> \n"
        f"• Артикул: <code>{info['bricklink_id']}</code> \n"
        f"• Цена покупки: {user_rec.get('price_buy') or '–'} \n"
        f"• Цена продажи: {user_rec.get('price_sale') or '–'} \n"
        f"• Описание: {user_rec.get('description') or '–'} \n"
        f"• Дата покупки: {user_rec.get('buy_date') or '–'} \n"
        f"• Дата продажи: {user_rec.get('sale_date') or '–'}"
    )
    kb = make_info_kb(info['bricklink_id'])
    url = f"https://img.bricklink.com/ItemImage/MN/0/{info['bricklink_id']}.png"
    await send_figure_image(bot, chat_id, url, text, kb)

async def send_figure_image(bot: Bot, chat_id: int, url: str, caption: str, reply_markup):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        async with httpx.AsyncClient(headers=headers) as client:
            r = await client.get(url)
            r.raise_for_status()
            data = r.content
    except httpx.HTTPStatusError:
        # Если нет картинки, отправляем текст без фото
        await bot.send_message(chat_id, caption, parse_mode="HTML", reply_markup=reply_markup)
        return

    bio = BytesIO(data)
    bio.name = url.split("/")[-1]
    bio.seek(0)
    file = BufferedInputFile(bio.read(), filename=bio.name)

    await bot.send_photo(
        chat_id=chat_id,
        photo=file,
        caption=caption,
        parse_mode="HTML",
        reply_markup=reply_markup
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
