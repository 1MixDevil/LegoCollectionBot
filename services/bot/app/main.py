import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BotCommand, Message

from app.api.auth import create_user
from app.content.bot_profile import BOT_DESCRIPTION, BOT_SHORT_DESCRIPTION
from app.content.guide import USER_GUIDE_HTML
from app.core.config import TG_TOKEN
from app.core.access import get_main_keyboard
from app.handlers.add_figure import router as add_figure_router
from app.handlers.cancel import router as cancel_router
from app.handlers.create_tierlist import router as create_tierlist_router
from app.handlers.delete_figure import router as delete_figure_router
from app.handlers.info_figure import router as info_figure_router
from app.handlers.photo_search import router as photo_search_router
from app.handlers.my_collection import router as my_collection_router
from app.handlers.settings import router as settings_router
from app.handlers.stubs import router as stubs_router
from app.handlers.update_figures import router as update_figures_router
from app.handlers.admin_panel import router as admin_panel_router
from app.handlers.help import router as help_router
from app.handlers.wishlist import router as wishlist_router
from app.keyboards.main import prompt_kb
from app.services.menu import send_main_menu
from app.states.figures import AddFigureState
from app.utils.message import answer_callback

logger = logging.getLogger(__name__)


async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    tg_id = str(message.from_user.id)
    name = message.from_user.first_name or "пользователь"
    try:
        created = await create_user(tg_id, name)
    except Exception:
        logger.exception("Failed to register user")
        await message.answer("Ошибка при связывании с сервисом авторизации.")
        return

    if created:
        await message.answer(f"Привет, {name}! Ваш аккаунт создан.")
        kb = await get_main_keyboard(tg_id)
        try:
            await message.answer(USER_GUIDE_HTML, parse_mode="HTML", reply_markup=kb)
        except Exception:
            logger.exception("Failed to send guide HTML, fallback to plain text")
            await message.answer(
                USER_GUIDE_HTML.replace("<b>", "").replace("</b>", ""),
                reply_markup=kb,
            )
        return

    await send_main_menu(message, tg_id)


async def cmd_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await send_main_menu(message, str(message.from_user.id))


async def cmd_back_to_serial(call: types.CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddFigureState.waiting_serial)
    await answer_callback(
        call,
        "Введите артикул BrickLink (например <code>sw0001a</code>):",
        parse_mode="HTML",
        reply_markup=prompt_kb(back="add"),
    )


async def setup_bot_profile(bot: Bot) -> None:
    try:
        await bot.set_my_commands(
            [
                BotCommand(command="start", description="Запуск и регистрация"),
                BotCommand(command="menu", description="Главное меню"),
            ]
        )
        await bot.set_my_short_description(BOT_SHORT_DESCRIPTION)
        await bot.set_my_description(BOT_DESCRIPTION)
    except Exception:
        logger.exception("Failed to set bot profile (BotFather may override)")


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logger.info("Bot process start pid=%s", os.getpid())

    if not TG_TOKEN:
        raise RuntimeError("TG_TOKEN is not set")

    bot = Bot(token=TG_TOKEN)
    await setup_bot_profile(bot)
    dp = Dispatcher()

    dp.message.register(cmd_start, Command("start"))
    dp.message.register(cmd_menu, Command("menu"))
    dp.callback_query.register(
        cmd_back_to_serial,
        lambda cb: cb.data == "back_to_serial",
    )

    dp.include_router(cancel_router)
    dp.include_router(admin_panel_router)
    dp.include_router(my_collection_router)
    dp.include_router(add_figure_router)
    dp.include_router(photo_search_router)
    dp.include_router(help_router)
    dp.include_router(wishlist_router)
    dp.include_router(stubs_router)
    dp.include_router(update_figures_router)
    dp.include_router(delete_figure_router)
    dp.include_router(info_figure_router)
    dp.include_router(create_tierlist_router)
    dp.include_router(settings_router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
