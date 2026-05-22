from aiogram import Router, types
from aiogram.fsm.context import FSMContext

from app.services.menu import MAIN_MENU_HTML, send_main_menu

router = Router()


@router.callback_query(lambda cb: cb.data == "cancel")
async def cb_cancel(call: types.CallbackQuery, state: FSMContext):
    await state.clear()  # в т.ч. режим «Связаться с админом»
    await call.answer()
    await send_main_menu(call.message, str(call.from_user.id), text=MAIN_MENU_HTML)
