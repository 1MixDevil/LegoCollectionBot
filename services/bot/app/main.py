import asyncio
import logging

from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.api.auth import create_user
from app.core.config import TG_TOKEN
from app.handlers.add_figure import router as add_figure_router
from app.handlers.cancel import router as cancel_router
from app.handlers.create_tierlist import router as create_tierlist_router
from app.handlers.delete_figure import router as delete_figure_router
from app.handlers.info_figure import router as info_figure_router
from app.handlers.my_collection import router as my_collection_router
from app.handlers.settings import router as settings_router
from app.handlers.stubs import router as stubs_router
from app.handlers.update_figures import router as update_figures_router
from app.keyboards.main import main_kb, prompt_kb
from app.states.figures import AddFigureState
from app.utils.message import answer_callback

logger = logging.getLogger(__name__)


async def cmd_start(message: Message, state: FSMContext) -> None:
    tg_id = str(message.from_user.id)
    name = message.from_user.first_name or "пользователь"
    try:
        created = await create_user(tg_id, name)
    except Exception:
        logger.exception("Failed to register user")
        await message.answer("Ошибка при связывании с сервисом авторизации.")
        return

    if created:
        await message.answer(
            f"Привет, {name}! Ваш аккаунт создан.",
            reply_markup=main_kb,
        )
    else:
        await message.answer(
            f"С возвращением, {name}!",
            reply_markup=main_kb,
        )


async def cmd_back_to_serial(call: types.CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddFigureState.waiting_serial)
    await answer_callback(
        call,
        "Введите артикул (bricklink_id) фигурки:",
        reply_markup=prompt_kb(back="add"),
    )


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    if not TG_TOKEN:
        raise RuntimeError("TG_TOKEN is not set")

    bot = Bot(token=TG_TOKEN)
    dp = Dispatcher()

    dp.message.register(cmd_start, Command("start"))
    dp.callback_query.register(
        cmd_back_to_serial,
        lambda cb: cb.data == "back_to_serial",
    )

    dp.include_router(cancel_router)
    dp.include_router(stubs_router)
    dp.include_router(add_figure_router)
    dp.include_router(my_collection_router)
    dp.include_router(update_figures_router)
    dp.include_router(delete_figure_router)
    dp.include_router(info_figure_router)
    dp.include_router(create_tierlist_router)
    dp.include_router(settings_router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
