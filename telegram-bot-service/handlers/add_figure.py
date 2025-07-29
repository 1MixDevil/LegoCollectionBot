from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from FMSState import AddFigureState, BulkAddState
from HttpRequests import get_user_settings, add_figure_to_user, add_figure_to_user_bulk
from datetime import date

from inlineKeyBoards import main_kb, nav_kb, add_choice_kb
import os
import re

router = Router()

MAX_SERIALS_PER_REQUEST = int(os.getenv("MAX_SERIALS_PER_REQUEST", 50))

# Шаг 1: пользователь нажал /add — предлагаем выбрать режим
@router.callback_query(lambda cb: cb.data == "add")
async def cb_add_choice(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.edit_text(
        "Выберите режим добавления:",
        reply_markup=add_choice_kb()
    )

# Ветка одиночного добавления
@router.callback_query(lambda cb: cb.data == "add_solo_figure")
async def cb_add_solo(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.edit_text(
        "Введите артикул (bricklink_id) фигурки:",
        reply_markup=nav_kb(back="add")
    )
    await state.set_state(AddFigureState.waiting_serial)

# Ветка bulk‑добавления
@router.callback_query(lambda cb: cb.data == "add_few_figure")
async def cb_add_few(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.edit_text(
        f"Введите несколько артикулов через запятую или ';' (максимум {MAX_SERIALS_PER_REQUEST}):",
        reply_markup=nav_kb(back="add")
    )
    await state.set_state(BulkAddState.waiting_serials)

# Обработка bulk‑ввода
@router.message(BulkAddState.waiting_serials)
async def add_many_serials(message: types.Message, state: FSMContext):
    text = message.text.strip()
    tg_id = str(message.from_user.id)

    # 1) разбираем артикулы
    serials = [s.strip() for s in re.split(r"[,; ]+", text) if s.strip()]
    if not serials:
        await message.answer("Пожалуйста, введите хотя бы один артикул.", reply_markup=nav_kb(back="add"))
        return

    if len(serials) > MAX_SERIALS_PER_REQUEST:
        await message.answer(
            f"❗️ Можно добавить не более {MAX_SERIALS_PER_REQUEST} артикула за раз.",
            reply_markup=nav_kb(back="add")
        )
        return

    # 2) получаем настройки пользователя
    try:
        settings = await get_user_settings(tg_id)
    except Exception:
        await message.answer("Ошибка получения настроек пользователя.", reply_markup=main_kb)
        await state.clear()
        return

    # 3) формируем payloads
    today = date.today().isoformat() if settings.get("auto_fill_dates") else None

    payloads = []
    for serial in serials:
        p = {
            "user_id": tg_id,
            "bricklink_id": serial,
            "price_buy": None,
            "price_sale": None,
            "description": None,
            "buy_date": today,
            "sale_date": today,
        }
        payloads.append(p)

    # 4) шлём bulk‑запрос
    try:
        created = await add_figure_to_user_bulk(payloads)
        await message.answer(
            f"✅ Успешно добавлено {len(created)} фигурок в коллекцию.",
            reply_markup=main_kb
        )
    except Exception as e:
        await message.answer(f"Ошибка при добавлении фигурок: {e}", reply_markup=main_kb)
    finally:
        await state.clear()

# Одиночное добавление (без изменений)
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
        await message.answer("Введите цену покупки:", reply_markup=nav_kb(back="back_to_serial"))
        await state.set_state(AddFigureState.request_price_buy)
    elif settings.get("request_price_sale"):
        await message.answer("Введите цену продажи:", reply_markup=nav_kb(back="back_to_serial"))
        await state.set_state(AddFigureState.request_price_sale)
    elif settings.get("show_description"):
        await message.answer("Введите описание фигурки:", reply_markup=nav_kb(back="back_to_serial"))
        await state.set_state(AddFigureState.show_description)
    else:
        await finish_add_figure(message, state)

@router.message(AddFigureState.request_price_buy)
async def handle_price_buy(message: types.Message, state: FSMContext):
    await state.update_data(price_buy=message.text.strip())
    data = await state.get_data()
    if data["settings"].get("request_price_sale"):
        await message.answer("Введите цену продажи:", reply_markup=nav_kb(back="back_to_serial"))
        await state.set_state(AddFigureState.request_price_sale)
    elif data["settings"].get("show_description"):
        await message.answer("Введите описание фигурки:", reply_markup=nav_kb(back="back_to_serial"))
        await state.set_state(AddFigureState.show_description)
    else:
        await finish_add_figure(message, state)

@router.message(AddFigureState.request_price_sale)
async def handle_price_sale(message: types.Message, state: FSMContext):
    await state.update_data(price_sale=message.text.strip())
    data = await state.get_data()
    if data["settings"].get("show_description"):
        await message.answer("Введите описание фигурки:", reply_markup=nav_kb(back="back_to_serial"))
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