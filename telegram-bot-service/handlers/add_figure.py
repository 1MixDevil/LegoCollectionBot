from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from FMSState import AddFigureState, BulkAddState
from HttpRequests import get_user_settings, add_figure_to_user, add_figure_to_user_bulk, fetch_similar_serials
from datetime import date
from httpx import HTTPStatusError

from aiogram.utils.keyboard import InlineKeyboardBuilder
from inlineKeyBoards import main_kb, nav_kb, add_choice_kb
import os
import re

router = Router()

MAX_SERIALS_PER_REQUEST = int(os.getenv("MAX_SERIALS_PER_REQUEST", 50))

# Сопоставление полей API и русских названий
FIELD_NAMES_RU = {
    "price_buy": "Цена покупки",
    "price_sale": "Цена продажи",
    "bricklink_id": "Артикул",
    "description": "Описание",
    "buy_date": "Дата покупки",
    "sale_date": "Дата продажи",
}

# Перевод популярных ошибок Pydantic/FastAPI на русский
ERROR_MSGS_RU = {
    "float_parsing": "должно быть числом",
    "int_parsing": "должно быть целым числом",
    "string_too_short": "слишком короткое значение",
    "string_too_long": "слишком длинное значение",
    "missing": "обязательное поле",
}
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


def format_validation_errors(detail):
    """Преобразует detail FastAPI/Pydantic в читаемый список на русском."""
    if not isinstance(detail, list):
        return str(detail)

    messages = []
    for err in detail:
        # Определяем поле (пропускаем "body")
        field_path = [p for p in err.get("loc", []) if p != "body"]
        field_key = ".".join(map(str, field_path)) if field_path else "?"

        # Русское имя поля (если есть в словаре)
        field_name_ru = FIELD_NAMES_RU.get(field_key, field_key)

        # Сообщение
        err_type = err.get("type", "")
        msg_ru = ERROR_MSGS_RU.get(err_type)
        if not msg_ru:
            # fallback — если не нашли перевод по type
            msg_ru = err.get("msg", "Ошибка")

        # Введённое значение
        input_val = err.get("input")
        if input_val is not None:
            msg_ru += f' (введено: "{input_val}")'

        messages.append(f"- {field_name_ru}: {msg_ru}")

    return "\n".join(messages)

async def finish_add_figure(message: types.Message, state: FSMContext):
    blank = True
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

    except HTTPStatusError as e:
        status = e.response.status_code
        try:
            data = e.response.json()
        except Exception:
            data = {"detail": e.response.text}

        if status == 422:
            formatted = format_validation_errors(data.get("detail", []))
            await message.answer(
                f"Данные не прошли валидацию:\n{formatted}",
                reply_markup=main_kb
            )
        elif status == 404:
            suggestions = await fetch_similar_serials(payload["bricklink_id"], limit=3, threshold=0.1)
            if not suggestions:
                await message.answer("Фигурка не найдена, похожих вариантов не обнаружено.", reply_markup=main_kb)
            else:
                builder = InlineKeyboardBuilder()
                for s in suggestions:
                    bid = s.get("bricklink_id", "")
                    name = s.get("name") or bid
                    sim = s.get("similarity", 0) * 100
                    btn_text = f"{name} — {bid} ({sim:.1f}%)"
                    # callback_data: советую использовать короткий id или bricklink_id,
                    # но следи, чтобы callback_data < 64 байт
                    builder.button(text=btn_text, callback_data=f"suggest_choice:{bid}")

                builder.button(text="Отмена", callback_data="suggest_cancel")
                builder.adjust(1)   # 1 кнопка в строке
                kb = builder.as_markup()
                blank = False
                await message.answer(
                    "Фигурка не найдена.\nВозможно, вы имели в виду — выберите вариант:",
                    reply_markup=kb
                )
        else:
            await message.answer(f"Ошибка сервера ({status}): {data}", reply_markup=main_kb)

    except Exception as e:
        await message.answer(f"Неизвестная ошибка: {e}", reply_markup=main_kb)

    finally:
        if blank:
            await state.clear()

@router.callback_query(lambda cb: cb.data and cb.data.startswith("suggest_choice:"))
async def cb_suggest_choice(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    _, new_serial = call.data.split(":", 1)
    await state.update_data(serial=new_serial)
    
    # Получаем user_id из call.from_user.id и кладём в состояние
    user_id = str(call.from_user.id)

    try:
        await call.message.edit_text(f"Попробую добавить фигурку с артикулом `{new_serial}`...", parse_mode="Markdown")
    except Exception:
        pass

    await finish_add_figure(call.message, state)

@router.callback_query(lambda cb: cb.data == "suggest_cancel")
async def cb_suggest_cancel(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    try:
        await call.message.edit_text("Операция отменена.", reply_markup=main_kb)
    except Exception:
        await call.message.answer("Операция отменена.", reply_markup=main_kb)
    await state.clear()
