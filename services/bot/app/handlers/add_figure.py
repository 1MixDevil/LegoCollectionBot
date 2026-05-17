import re

from datetime import date

from io import BytesIO



from aiogram import F, Router, types

from aiogram.fsm.context import FSMContext

from aiogram.utils.keyboard import InlineKeyboardBuilder

from httpx import HTTPStatusError



from app.api.auth import get_user_settings

from app.api.collection import (

    add_figure_to_user,

    add_figure_to_user_bulk,

    fetch_similar_serials,

)

from app.core.config import MAX_SERIALS_PER_REQUEST

from app.keyboards.main import add_choice_kb, main_kb, prompt_kb

from app.states.figures import AddFigureState, BulkAddState

from app.utils.message import answer_callback, safe_edit_or_answer



router = Router()



FIELD_NAMES_RU = {

    "price_buy": "Цена покупки",

    "price_sale": "Цена продажи",

    "bricklink_id": "Артикул",

    "description": "Описание",

    "buy_date": "Дата покупки",

    "sale_date": "Дата продажи",

}



ERROR_MSGS_RU = {

    "float_parsing": "должно быть числом",

    "int_parsing": "должно быть целым числом",

    "string_too_short": "слишком короткое значение",

    "string_too_long": "слишком длинное значение",

    "missing": "обязательное поле",

}





def _parse_optional_price(value) -> float | None:

    if value is None:

        return None

    if isinstance(value, (int, float)):

        return float(value)

    text = str(value).strip().replace(",", ".")

    if not text:

        return None

    return float(text)





def _parse_serials_from_text(text: str) -> list[str]:

    return [s.strip().lower() for s in re.split(r"[,;\s]+", text) if s.strip()]





def format_validation_errors(detail) -> str:

    if not isinstance(detail, list):

        return str(detail)



    messages = []

    for err in detail:

        field_path = [p for p in err.get("loc", []) if p != "body"]

        field_key = ".".join(map(str, field_path)) if field_path else "?"

        field_name_ru = FIELD_NAMES_RU.get(field_key, field_key)

        err_type = err.get("type", "")

        msg_ru = ERROR_MSGS_RU.get(err_type) or err.get("msg", "Ошибка")

        input_val = err.get("input")

        if input_val is not None:

            msg_ru += f' (введено: "{input_val}")'

        messages.append(f"- {field_name_ru}: {msg_ru}")



    return "\n".join(messages)





def _figure_not_found_message(serial: str, detail: str | None = None) -> str:

    base = f"Фигурка <code>{serial}</code> не найдена в каталоге."

    hint = (

        "\n\nСначала обновите каталог: /update → префикс серии "

        f"(например <code>{serial[:2]}</code>)."

    )

    if detail and "не найдена" in detail.lower():

        return f"❌ {detail}{hint}"

    return f"❌ {base}{hint}"





async def _advance_after_serial(message: types.Message, state: FSMContext) -> None:

    data = await state.get_data()

    settings = data["settings"]



    if settings.get("request_price_buy"):

        await message.answer(

            "Введите цену покупки (число) или нажмите «Пропустить»:",

            reply_markup=prompt_kb(back="back_to_serial", skip="skip_price_buy"),

        )

        await state.set_state(AddFigureState.request_price_buy)

    elif settings.get("request_price_sale"):

        await message.answer(

            "Введите цену продажи (число) или нажмите «Пропустить»:",

            reply_markup=prompt_kb(back="back_to_serial", skip="skip_price_sale"),

        )

        await state.set_state(AddFigureState.request_price_sale)

    elif settings.get("show_description"):

        await message.answer(

            "Введите описание фигурки или нажмите «Пропустить»:",

            reply_markup=prompt_kb(back="back_to_serial", skip="skip_description"),

        )

        await state.set_state(AddFigureState.show_description)

    else:

        await finish_add_figure(message, state)





async def _advance_after_price_buy(message: types.Message, state: FSMContext) -> None:

    data = await state.get_data()

    settings = data["settings"]



    if settings.get("request_price_sale"):

        await message.answer(

            "Введите цену продажи (число) или нажмите «Пропустить»:",

            reply_markup=prompt_kb(back="back_to_serial", skip="skip_price_sale"),

        )

        await state.set_state(AddFigureState.request_price_sale)

    elif settings.get("show_description"):

        await message.answer(

            "Введите описание фигурки или нажмите «Пропустить»:",

            reply_markup=prompt_kb(back="back_to_serial", skip="skip_description"),

        )

        await state.set_state(AddFigureState.show_description)

    else:

        await finish_add_figure(message, state)





async def _advance_after_price_sale(message: types.Message, state: FSMContext) -> None:

    data = await state.get_data()

    if data["settings"].get("show_description"):

        await message.answer(

            "Введите описание фигурки или нажмите «Пропустить»:",

            reply_markup=prompt_kb(back="back_to_serial", skip="skip_description"),

        )

        await state.set_state(AddFigureState.show_description)

    else:

        await finish_add_figure(message, state)





async def _process_bulk_serials(

    message: types.Message,

    state: FSMContext,

    serials: list[str],

) -> None:

    tg_id = str(message.from_user.id)



    if not serials:

        await message.answer(

            "Пожалуйста, введите хотя бы один артикул.",

            reply_markup=prompt_kb(back="add"),

        )

        return



    if len(serials) > MAX_SERIALS_PER_REQUEST:

        await message.answer(

            f"❗️ Можно добавить не более {MAX_SERIALS_PER_REQUEST} артикулов за раз.",

            reply_markup=prompt_kb(back="add"),

        )

        return



    try:

        settings = await get_user_settings(tg_id)

    except Exception:

        await message.answer(

            "Ошибка получения настроек пользователя.",

            reply_markup=main_kb,

        )

        await state.clear()

        return



    today = date.today().isoformat() if settings.get("auto_fill_dates") else None

    payloads = [

        {

            "bricklink_id": serial,

            "price_buy": None,

            "price_sale": None,

            "description": None,

            "buy_date": today,

            "sale_date": today,

        }

        for serial in serials

    ]



    try:

        result = await add_figure_to_user_bulk(tg_id, payloads)

        added_count = len(result.get("successes", []))

        failures = result.get("failures", [])

        lines = [f"✅ Добавлено в коллекцию: <b>{added_count}</b> из {len(serials)}."]

        if failures:

            missing = [

                f.get("payload", {}).get("bricklink_id", "?")

                for f in failures[:10]

            ]

            lines.append(

                "\n❌ Не найдены в каталоге: "

                + ", ".join(f"<code>{m}</code>" for m in missing)

            )

            if len(failures) > 10:

                lines.append(f"… и ещё {len(failures) - 10}")

            lines.append("\nОбновите каталог через /update.")

        await message.answer("\n".join(lines), parse_mode="HTML", reply_markup=main_kb)

    except HTTPStatusError as e:

        await message.answer(

            f"Ошибка при добавлении ({e.response.status_code}).",

            reply_markup=main_kb,

        )

    except Exception as e:

        await message.answer(f"Ошибка при добавлении: {e}", reply_markup=main_kb)

    finally:

        await state.clear()





@router.callback_query(F.data == "add")

async def cb_add_choice(call: types.CallbackQuery, state: FSMContext):

    await answer_callback(

        call,

        "Выберите режим добавления:",

        reply_markup=add_choice_kb(),

    )





@router.callback_query(F.data == "add_solo_figure")

async def cb_add_solo(call: types.CallbackQuery, state: FSMContext):

    await answer_callback(

        call,

        "Введите артикул (bricklink_id) фигурки:",

        reply_markup=prompt_kb(back="add"),

    )

    await state.set_state(AddFigureState.waiting_serial)





@router.callback_query(F.data == "add_few_figure")

async def cb_add_few(call: types.CallbackQuery, state: FSMContext):

    await answer_callback(

        call,

        f"Введите артикулы через запятую или «;», либо отправьте .txt файл "

        f"(максимум {MAX_SERIALS_PER_REQUEST}):",

        reply_markup=prompt_kb(back="add"),

    )

    await state.set_state(BulkAddState.waiting_serials)





@router.message(BulkAddState.waiting_serials, F.document)

async def add_many_from_file(message: types.Message, state: FSMContext):

    doc = message.document

    if not doc.file_name or not doc.file_name.lower().endswith(".txt"):

        await message.answer(

            "Отправьте текстовый файл .txt со списком артикулов (по одному в строке "

            "или через запятую).",

            reply_markup=prompt_kb(back="add"),

        )

        return



    buf = BytesIO()
    tg_file = await message.bot.get_file(doc.file_id)
    await message.bot.download_file(tg_file.file_path, buf)
    text = buf.getvalue().decode("utf-8", errors="ignore")

    serials = _parse_serials_from_text(text)

    await _process_bulk_serials(message, state, serials)





@router.message(BulkAddState.waiting_serials)

async def add_many_serials(message: types.Message, state: FSMContext):

    if not message.text:

        await message.answer(

            "Введите артикулы текстом или отправьте .txt файл.",

            reply_markup=prompt_kb(back="add"),

        )

        return

    serials = _parse_serials_from_text(message.text)

    await _process_bulk_serials(message, state, serials)





@router.message(AddFigureState.waiting_serial)

async def add_serial(message: types.Message, state: FSMContext):

    if not message.text:

        await message.answer(

            "Введите артикул текстом (например <code>sw0001a</code>).",

            parse_mode="HTML",

            reply_markup=prompt_kb(back="add"),

        )

        return



    serial = message.text.strip().lower()

    tg_id = str(message.from_user.id)

    try:

        settings = await get_user_settings(tg_id)

    except Exception:

        await message.answer(

            "Ошибка получения настроек пользователя.",

            reply_markup=main_kb,

        )

        await state.clear()

        return



    await state.update_data(serial=serial, user_id=tg_id, settings=settings)

    await _advance_after_serial(message, state)





@router.callback_query(F.data == "skip_price_buy")

async def cb_skip_price_buy(call: types.CallbackQuery, state: FSMContext):

    await call.answer()

    await _advance_after_price_buy(call.message, state)





@router.callback_query(F.data == "skip_price_sale")

async def cb_skip_price_sale(call: types.CallbackQuery, state: FSMContext):

    await call.answer()

    await _advance_after_price_sale(call.message, state)





@router.callback_query(F.data == "skip_description")

async def cb_skip_description(call: types.CallbackQuery, state: FSMContext):

    await call.answer()

    await finish_add_figure(call.message, state)





@router.message(AddFigureState.request_price_buy)

async def handle_price_buy(message: types.Message, state: FSMContext):

    if not message.text:

        await message.answer(

            "Введите число или нажмите «Пропустить».",

            reply_markup=prompt_kb(back="back_to_serial", skip="skip_price_buy"),

        )

        return

    try:

        price = _parse_optional_price(message.text.strip())

    except ValueError:

        await message.answer(

            "Некорректная цена. Введите число, например 1500 или 99.99",

            reply_markup=prompt_kb(back="back_to_serial", skip="skip_price_buy"),

        )

        return

    await state.update_data(price_buy=price)

    await _advance_after_price_buy(message, state)





@router.message(AddFigureState.request_price_sale)

async def handle_price_sale(message: types.Message, state: FSMContext):

    if not message.text:

        await message.answer(

            "Введите число или нажмите «Пропустить».",

            reply_markup=prompt_kb(back="back_to_serial", skip="skip_price_sale"),

        )

        return

    try:

        price = _parse_optional_price(message.text.strip())

    except ValueError:

        await message.answer(

            "Некорректная цена. Введите число.",

            reply_markup=prompt_kb(back="back_to_serial", skip="skip_price_sale"),

        )

        return

    await state.update_data(price_sale=price)

    await _advance_after_price_sale(message, state)





@router.message(AddFigureState.show_description)

async def handle_description(message: types.Message, state: FSMContext):

    if message.text:

        await state.update_data(description=message.text.strip())

    await finish_add_figure(message, state)





async def finish_add_figure(message: types.Message, state: FSMContext):

    state_data = await state.get_data()

    serial = state_data.get("serial")

    user_id = state_data.get("user_id") or str(message.chat.id)



    if not serial:

        await message.answer(

            "Сессия сброшена. Начните добавление заново: /add",

            reply_markup=main_kb,

        )

        await state.clear()

        return



    settings = state_data.get("settings") or {}

    buy_date = None

    sale_date = None

    if settings.get("auto_fill_dates"):

        if state_data.get("price_buy") is not None:

            buy_date = date.today().isoformat()

        if state_data.get("price_sale") is not None:

            sale_date = date.today().isoformat()



    keep_state = False

    try:

        price_buy = _parse_optional_price(state_data.get("price_buy"))

        price_sale = _parse_optional_price(state_data.get("price_sale"))

    except ValueError:

        await message.answer(

            "Некорректный формат цены. Начните заново: /add",

            reply_markup=main_kb,

        )

        await state.clear()

        return



    try:

        await add_figure_to_user(

            telegram_id=user_id,

            bricklink_id=serial,

            price_buy=price_buy,

            price_sale=price_sale,

            description=state_data.get("description"),

            buy_date=buy_date,

            sale_date=sale_date,

        )

        await message.answer(

            "✅ Фигурка успешно добавлена в вашу коллекцию.",

            reply_markup=main_kb,

        )



    except HTTPStatusError as e:

        status = e.response.status_code

        try:

            body = e.response.json()

        except Exception:

            body = {"detail": e.response.text}



        if status == 422:

            formatted = format_validation_errors(body.get("detail", []))

            await message.answer(

                f"Данные не прошли проверку:\n{formatted}",

                reply_markup=main_kb,

            )

        elif status == 404:

            detail = body.get("detail")

            if isinstance(detail, list):

                detail = detail[0].get("msg", "") if detail else ""

            suggestions = await fetch_similar_serials(serial, limit=3, threshold=0.1)

            if suggestions:

                builder = InlineKeyboardBuilder()

                for s in suggestions:

                    bid = s.get("bricklink_id", "")

                    name = s.get("name") or bid

                    sim = s.get("similarity", 0) * 100

                    btn_text = f"{name} — {bid} ({sim:.1f}%)"

                    builder.button(text=btn_text, callback_data=f"suggest_choice:{bid}")

                builder.button(text="Отмена", callback_data="suggest_cancel")

                builder.adjust(1)

                keep_state = True

                await message.answer(

                    _figure_not_found_message(serial, str(detail) if detail else None)

                    + "\n\nВозможно, вы имели в виду:",

                    parse_mode="HTML",

                    reply_markup=builder.as_markup(),

                )

            else:

                await message.answer(

                    _figure_not_found_message(serial, str(detail) if detail else None),

                    parse_mode="HTML",

                    reply_markup=main_kb,

                )

        else:

            await message.answer(

                f"Ошибка сервера ({status}). Попробуйте позже.",

                reply_markup=main_kb,

            )



    except Exception as e:

        await message.answer(

            f"Не удалось добавить фигурку. Попробуйте позже.\n({type(e).__name__})",

            reply_markup=main_kb,

        )



    finally:

        if not keep_state:

            await state.clear()





@router.callback_query(F.data.startswith("suggest_choice:"))

async def cb_suggest_choice(call: types.CallbackQuery, state: FSMContext):

    await call.answer()

    _, new_serial = call.data.split(":", 1)

    data = await state.get_data()

    if not data.get("user_id"):

        await state.update_data(user_id=str(call.from_user.id))

    try:

        settings = await get_user_settings(str(call.from_user.id))

        await state.update_data(settings=settings)

    except Exception:

        pass

    await state.update_data(serial=new_serial.lower())

    await safe_edit_or_answer(

        call.message,

        f"Добавляю <code>{new_serial}</code>…",

        parse_mode="HTML",

    )

    await finish_add_figure(call.message, state)





@router.callback_query(F.data == "suggest_cancel")

async def cb_suggest_cancel(call: types.CallbackQuery, state: FSMContext):

    await answer_callback(call, "Операция отменена.", reply_markup=main_kb)

    await state.clear()


