from aiogram import Router, types
from aiogram.fsm.context import FSMContext

from app.core.access import get_main_keyboard
from app.utils.message import answer_callback

router = Router()


@router.callback_query(lambda cb: cb.data == "cancel")
async def cb_cancel(call: types.CallbackQuery, state: FSMContext):
    await state.clear()  # в т.ч. режим «Связаться с админом»
    kb = await get_main_keyboard(str(call.from_user.id))
    await answer_callback(call, "❌ Действие отменено.", reply_markup=kb)
