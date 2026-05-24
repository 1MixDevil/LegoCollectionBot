from aiogram import Router, types
from aiogram.exceptions import TelegramNetworkError
from aiogram.fsm.context import FSMContext

from app.services.menu import MAIN_MENU_HTML, send_main_menu
from app.utils.telegram_network import safe_callback_answer

router = Router()


@router.callback_query(lambda cb: cb.data == "cancel")
async def cb_cancel(call: types.CallbackQuery, state: FSMContext):
    await state.clear()  # в т.ч. режим «Связаться с админом»
    await safe_callback_answer(call)
    try:
        await send_main_menu(call.message, str(call.from_user.id), text=MAIN_MENU_HTML)
    except TelegramNetworkError:
        pass  # состояние уже сброшено; пользователь может нажать /menu
