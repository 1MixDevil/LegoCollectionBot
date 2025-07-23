from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from FMSState import UpdateFigures
from HttpRequests import update_figures_list
from inlineKeyBoards import main_kb, nav_kb

router = Router()

@router.callback_query(lambda cb: cb.data == "update")
async def cb_update(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer(
        "Введите артикул типа фигурки (sw, lor):",
        reply_markup=nav_kb()
    )
    await call.message.delete_reply_markup()
    await state.set_state(UpdateFigures.waiting_article)

@router.message(UpdateFigures.waiting_article)
async def get_article(message: types.Message, state: FSMContext):
    article = message.text.strip()
    try:
        await update_figures_list(article=article)
        await message.answer(f"Обновление по «{article}» запущено.", reply_markup=main_kb)
    except Exception as e:
        await message.answer(f"Ошибка обновления: {e}", reply_markup=main_kb)
    finally:
        await state.clear()
