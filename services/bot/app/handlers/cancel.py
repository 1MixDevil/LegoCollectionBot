from aiogram import Router, types
from aiogram.fsm.context import FSMContext

from app.keyboards.main import main_kb
from app.utils.message import answer_callback

router = Router()


@router.callback_query(lambda cb: cb.data == "cancel")
async def cb_cancel(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await answer_callback(call, "❌ Действие отменено.", reply_markup=main_kb)
