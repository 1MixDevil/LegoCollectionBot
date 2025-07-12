import os
import asyncio
import logging

from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

import httpx
from dotenv import load_dotenv

# Загрузка .env
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Токен и URL сервисов из .env ===
TOKEN     = os.getenv("TG_TOKEN")
AUTH_IP   = os.getenv("AUTHORIZATION_IP", "localhost")
AUTH_PORT = os.getenv("AUTHORIZATION_PORT", "8000")
COLL_IP   = os.getenv("COLLECTION_IP",    "localhost")
COLL_PORT = os.getenv("COLLECTION_PORT",  "8001")

AUTH_BASE = f"http://{AUTH_IP}:{AUTH_PORT}"
COLL_BASE = f"http://{COLL_IP}:{COLL_PORT}"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# === FSM состояния ===
class AddFigureState(StatesGroup):
    waiting_serial = State()

class UpdateFigures(StatesGroup):
    waiting_article = State()
# === Inline‑клавиатуры ===
main_kb = types.InlineKeyboardMarkup(inline_keyboard=[
    [types.InlineKeyboardButton(text="/add",           callback_data="add")],
    [types.InlineKeyboardButton(text="/delete",        callback_data="delete")],
    [types.InlineKeyboardButton(text="/my_collection", callback_data="my_collection")],
    [types.InlineKeyboardButton(text="/settings",      callback_data="settings")],
    [types.InlineKeyboardButton(text="/info",          callback_data="info")],
    [types.InlineKeyboardButton(text="/update",        callback_data="update")],
])

confirm_kb = types.InlineKeyboardMarkup(inline_keyboard=[
    [types.InlineKeyboardButton(text="Да, удалить", callback_data="confirm_yes")],
    [types.InlineKeyboardButton(text="Отмена",      callback_data="confirm_no")],
])

# === HTTP‑вызовы к API ===

async def create_user(telegram_id: str, username: str):
    url = f"{AUTH_BASE}/users/"
    payload = {"telegram_username": telegram_id, "username": username}
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                # Пользователь уже существует
                return None
            raise

async def add_figure_to_user(serial: str, user_id: str):
    url = f"{COLL_BASE}/figure/user/"
    payload = {
        "user_id":     user_id,
        "bricklink_id":   serial,
        "price_buy":   None,
        "price_sale":  None,
        "description": None,
        "buy_date":    None,
        "sale_date":   None,
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        return r.json()

async def list_user_figures(user_id: str):
    url = f"{COLL_BASE}/figure/user/{user_id}/"
    async with httpx.AsyncClient() as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.json()

async def update_figures_list(article: str):
    url = f"{COLL_BASE}/figure/update_figures/"
    params = {"article": article, "max_miss": 30}
    async with httpx.AsyncClient() as client:
        r = await client.put(url, params=params)
        r.raise_for_status()
        return r.text()

# === Handlers ===

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    tg_id = str(message.from_user.id)
    name  = message.from_user.first_name or "пользователь"
    try:
        created = await create_user(tg_id, name)
    except Exception:
        await message.answer("Ошибка при связывании с сервисом авторизации.")
        return

    if created:
        await message.answer(f"Привет, {name}! Ваш аккаунт создан.", reply_markup=main_kb)
    else:
        await message.answer(f"С возвращением, {name}!", reply_markup=main_kb)

@dp.callback_query(lambda cb: cb.data == "add")
async def cb_add(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Введите артикул (bricklink_id) фигурки:")
    await call.message.delete_reply_markup()
    await state.set_state(AddFigureState.waiting_serial)

@dp.message(AddFigureState.waiting_serial)
async def add_serial(message: types.Message, state: FSMContext):
    serial = message.text.strip()
    tg_id   = str(message.from_user.id)
    try:
        rec = await add_figure_to_user(serial, tg_id)
    except httpx.HTTPStatusError as e:
        await message.answer(f"Ошибка сервиса коллекции: {e.response.status_code}", reply_markup=main_kb)
    except Exception:
        await message.answer("Не удалось добавить фигурку.", reply_markup=main_kb)
    else:
        await message.answer(f"Фигурка {serial} добавлена в вашу коллекцию.", reply_markup=main_kb)
    finally:
        await state.clear()

@dp.callback_query(lambda cb: cb.data == "my_collection")
async def cb_my_collection(call: types.CallbackQuery):
    tg_id = str(call.from_user.id)
    try:
        records = await list_user_figures(tg_id)
    except Exception:
        await call.message.answer("Не удалось получить коллекцию.", reply_markup=main_kb)
        return

    if not records:
        await call.message.answer("Ваша коллекция пуста.", reply_markup=main_kb)
    else:
        text = "Ваша коллекция:\n" + "\n".join(f"- {r['bricklink_id']}" for r in records)
        await call.message.answer(text, reply_markup=main_kb)

@dp.callback_query(lambda cb: cb.data == "update")
async def cb_update(call: types.CallbackQuery, state: FSMContext):
    try:
        await call.message.answer("Введите артикул типа фигурки (sw, lor):")
        await call.message.delete_reply_markup()
        await state.set_state(UpdateFigures.waiting_article)
    except Exception:
        await call.message.answer("Произошла ошибка", reply_markup=main_kb)

@dp.message(UpdateFigures.waiting_article)
async def get_article(message: types.Message, state: FSMContext):
    article = message.text.strip()
    try:
        rec = await update_figures_list(article)
    except httpx.HTTPStatusError as e:
        await message.answer(f"Ошибка сервиса коллекции: {e.response.status_code}", reply_markup=main_kb)
    except Exception:
        await message.answer("Не удалось добавить фигурку.", reply_markup=main_kb)
    else:
        await message.answer(f"Фигурка {serial} добавлена в вашу коллекцию.", reply_markup=main_kb)
    finally:
        await state.clear()


# Заглушки для остальных
@dp.callback_query(lambda cb: cb.data in {"delete","settings","info"})
async def cb_placeholder(call: types.CallbackQuery):
    await call.message.answer("Этот функционал ещё в разработке…", reply_markup=main_kb)

# === Запуск ===
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
