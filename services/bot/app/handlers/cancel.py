from aiogram import Router, types
from aiogram.exceptions import TelegramNetworkError
from aiogram.fsm.context import FSMContext

from app.core.access import get_main_keyboard
from app.services.menu import MAIN_MENU_HTML, send_main_menu
from app.utils.message import safe_edit_or_answer
from app.utils.telegram_network import safe_callback_answer

router = Router()


@router.callback_query(lambda cb: cb.data == "cancel")
async def cb_cancel(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await safe_callback_answer(call)
    kb = await get_main_keyboard(str(call.from_user.id))
    try:
        await safe_edit_or_answer(
            call.message,
            MAIN_MENU_HTML,
            parse_mode="HTML",
            reply_markup=kb,
        )
    except TelegramNetworkError:
        pass
    except Exception:
        try:
            await send_main_menu(call.message, str(call.from_user.id), text=MAIN_MENU_HTML)
        except TelegramNetworkError:
            pass
