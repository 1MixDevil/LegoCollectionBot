import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.filters.command import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram import types

from config import TOKEN
from HttpRequests import create_user
from inlineKeyBoards import main_kb, nav_kb
from FMSState import AddFigureState

# импортируем роутеры из handlers/
from handlers.add_figure import router as add_figure_router
from handlers.my_collection import router as my_collection_router
from handlers.update_figures import router as update_figures_router
from handlers.delete_figure import router as delete_figure_router
from handlers.settings import router as settings_router
from handlers.info_figure import router as info_figure_router
from handlers.cancel import router as cancel_router
from handlers.create_tierlist import router as create_tierlist

from middlewares.FallbackMiddleware import FallbackMiddleware

# === Стартовый хэндлер ===
async def cmd_start(message: Message, state: FSMContext):
    tg_id = str(message.from_user.id)
    name = message.from_user.first_name or "пользователь"
    try:
        created = await create_user(tg_id, name)
    except Exception:
        await message.answer("Ошибка при связывании с сервисом авторизации.")
        return

    if created:
        await message.answer(f"Привет, {name}! Ваш аккаунт создан.", reply_markup=main_kb)
    else:
        await message.answer(f"С возвращением, {name}!", reply_markup=main_kb)

# === Хэндлер "Назад" для AddFigureState ===
async def cmd_back_to_serial(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddFigureState.waiting_serial)
    await call.message.edit_text(
        "Введите артикул (bricklink_id) фигурки:",
        reply_markup=nav_kb()
    )
    await call.answer()

async def main():
    logging.basicConfig(level=logging.INFO)
    bot = Bot(token=TOKEN)
    dp = Dispatcher()

    # регистрируем стартовый хэндлер
    dp.message.register(cmd_start, Command("start"))

    # регистрируем роутер для кнопки "Назад"
    dp.callback_query.register(
        cmd_back_to_serial,
        lambda cb: cb.data == "back_to_serial"
    )

    # регистрируем все роутеры‑модули
    dp.include_router(cancel_router)
    dp.include_router(add_figure_router)
    dp.include_router(my_collection_router)
    dp.include_router(update_figures_router)
    dp.include_router(delete_figure_router)
    dp.include_router(info_figure_router)
    dp.include_router(settings_router)
    dp.include_router(create_tierlist)


    dp.update.middleware(FallbackMiddleware())

    # запускаем поллинг
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())