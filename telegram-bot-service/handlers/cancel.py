# handlers/cancel.py
from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from inlineKeyBoards import main_kb

router = Router()

@router.callback_query(lambda cb: cb.data == "cancel")
async def cb_cancel(call: types.CallbackQuery, state: FSMContext):
    # 1) Сбрасываем FSM
    await state.clear()
    # 2) Обновляем текст/клавиатуру
    try:
        await call.message.edit_text(
            "❌ Действие отменено.",
            reply_markup=main_kb
        )
    except:
        await call.message.answer(
            "❌ Действие отменено.",
            reply_markup=main_kb
        )
    # 3) Убираем «крутилку»
    await call.answer()
