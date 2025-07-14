# handlers/info_figure.py
import httpx
from aiogram import Router, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile
from HttpRequests import add_figure_to_user, delete_figure_to_user
from inlineKeyBoards import main_kb, make_info_kb
from FMSState import InfoFigures
from config import COLL_BASE
from io import BytesIO

router = Router()

@router.callback_query(lambda cb: cb.data == "info")
async def cb_info(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Введите серийный номер фигурки, о которой хотите получить информацию:")
    await call.message.delete_reply_markup()
    await state.set_state(InfoFigures.waiting_serial)

@router.message(InfoFigures.waiting_serial)
async def get_info_figure(message: types.Message, state: FSMContext):
    serial = message.text.strip()
    user_id = str(message.from_user.id)
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
            await message.answer("Фигурка не найдена.", reply_markup=main_kb)
        else:
            await message.answer(f"Ошибка сервиса: {e.response.status_code}", reply_markup=main_kb)
        await state.clear()
        return
    except Exception:
        await message.answer("Ошибка получения информации.", reply_markup=main_kb)
        await state.clear()
        return

    user_rec = info.get("user_record") or {}
    text = (
        f"🔍 <b>{info['name']}</b> \n"
        f"• Артикул: <code>{info['bricklink_id']}</code> \n"
        f"• Цена покупки: {user_rec.get('price_buy') or '–'} \n"
        f"• Цена продажи: {user_rec.get('price_sale') or '–'} \n"
        f"• Описание: {user_rec.get('description') or '–'} \n"
        f"• Дата покупки: {user_rec.get('buy_date') or '–'} \n"
        f"• Дата продажи: {user_rec.get('sale_date') or '–'} \n"
    )
    kb = make_info_kb(serial)
    url = f"https://img.bricklink.com/ItemImage/MN/0/{serial}.png"
    await send_figure_image(message.bot, message.chat.id, url, text, kb)

    await state.clear()

async def send_figure_image(bot: Bot, chat_id: int, url: str, caption: str, reply_markup):
    headers = {"User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(headers=headers) as client:
        r = await client.get(url)
        r.raise_for_status()
        data = r.content

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