# handlers/add_figure.py
from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from FMSState import AddFigureState
from HttpRequests import get_user_settings, add_figure_to_user
from inlineKeyBoards import main_kb, nav_kb

router = Router()

@router.callback_query(lambda cb: cb.data == "add")
async def cb_add(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Введите артикул (bricklink_id) фигурки:")
    await call.message.delete_reply_markup()
    await state.set_state(AddFigureState.waiting_serial)

@router.message(AddFigureState.waiting_serial)
async def add_serial(message: types.Message, state: FSMContext):
    serial = message.text.strip()
    tg_id = str(message.from_user.id)

    try:
        settings = await get_user_settings(tg_id)
    except Exception:
        await message.answer("Ошибка получения настроек пользователя.", reply_markup=main_kb)
        await state.clear()
        return

    await state.update_data(serial=serial, user_id=tg_id, settings=settings)

    if settings.get("request_price_buy"):
        await message.answer("Введите цену покупки:")
        await state.set_state(AddFigureState.request_price_buy)
    elif settings.get("request_price_sale"):
        await message.answer("Введите цену продажи:")
        await state.set_state(AddFigureState.request_price_sale)
    elif settings.get("show_description"):
        await message.answer("Введите описание фигурки:")
        await state.set_state(AddFigureState.show_description)
    else:
        await finish_add_figure(message, state)

@router.message(AddFigureState.request_price_buy)
async def handle_price_buy(message: types.Message, state: FSMContext):
    await state.update_data(price_buy=message.text.strip())
    data = await state.get_data()
    if data["settings"].get("request_price_sale"):
        await message.answer("Введите цену продажи:")
        await state.set_state(AddFigureState.request_price_sale)
    elif data["settings"].get("show_description"):
        await message.answer("Введите описание фигурки:")
        await state.set_state(AddFigureState.show_description)
    else:
        await finish_add_figure(message, state)

@router.message(AddFigureState.request_price_sale)
async def handle_price_sale(message: types.Message, state: FSMContext):
    await state.update_data(price_sale=message.text.strip())
    data = await state.get_data()
    if data["settings"].get("show_description"):
        await message.answer("Введите описание фигурки:")
        await state.set_state(AddFigureState.show_description)
    else:
        await finish_add_figure(message, state)

@router.message(AddFigureState.show_description)
async def handle_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    await finish_add_figure(message, state)

async def finish_add_figure(message: types.Message, state: FSMContext):
    data = await state.get_data()
    payload = {
        "user_id": data["user_id"],
        "bricklink_id": data["serial"],
        "price_buy": data.get("price_buy"),
        "price_sale": data.get("price_sale"),
        "description": data.get("description"),
        "buy_date": None,
        "sale_date": None
    }

    if data["settings"].get("auto_fill_dates"):
        from datetime import date
        if payload["price_buy"] is not None:
            payload["buy_date"] = date.today().isoformat()
        if payload["price_sale"] is not None:
            payload["sale_date"] = date.today().isoformat()

    try:
        await add_figure_to_user(**payload)
        await message.answer("Фигурка успешно добавлена в вашу коллекцию.", reply_markup=main_kb)
    except Exception as e:
        await message.answer(f"Ошибка при добавлении фигурки: {e}", reply_markup=main_kb)
    finally:
        await state.clear()