# handlers/delete_figure.py
from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from FMSState import DeleteFigures
from HttpRequests import delete_figure_to_user
from inlineKeyBoards import main_kb

router = Router()

@router.callback_query(lambda cb: cb.data == "delete")
async def cb_delete(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Введите артикул типа фигурки (sw, lor):")
    await call.message.delete_reply_markup()
    await state.set_state(DeleteFigures.waiting_serial)

@router.message(DeleteFigures.waiting_serial)
async def get_delete_figure(message: types.Message, state: FSMContext):
    serial = message.text.strip()
    user_id = str(message.from_user.id)
    try:
        await delete_figure_to_user(serial, user_id)
        await message.answer(f"Фигурка {serial} удалена из вашей коллекции.", reply_markup=main_kb)
    except Exception as e:
        await message.answer(f"Ошибка удаления: {e}", reply_markup=main_kb)
    finally:
        await state.clear()