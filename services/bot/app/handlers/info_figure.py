from aiogram import Bot, F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from httpx import HTTPStatusError

from app.api.collection import (
    add_figure_to_user,
    delete_figure_from_user,
    fetch_similar_serials,
    list_user_figures,
    search_figures_by_keyword,
    update_all_user_figure_records,
    update_user_figure_record,
)
from app.core.access import ensure_access
from app.core.config import MAX_SERIALS_PER_REQUEST
from app.keyboards.main import make_suggestions_kb, nav_kb, prompt_kb
from app.keyboards.nav_labels import MAIN_MENU_LABEL
from app.services.figure_display import (
    refresh_figure_card_message,
    send_figure_card,
    send_figure_card_with_loading,
)
from app.states.figures import InfoFigures
from app.utils.serial_parse import parse_serial_list

router = Router()

FIGURE_CARD_PROMPT = (
    "ℹ️ <b>Карточка фигурки</b>\n\n"
    "Введите <b>артикул BrickLink</b> (например <code>sw0001a</code>) "
    "или <b>название</b> — фото, цены и ваши записи в коллекции.\n\n"
    "<i>Несколько артикулов — через пробел или запятую: "
    "<code>sw0001a sw0002</code>.\n"
    "По фото — раздел «🔎 Поиск по фото».</i>"
)


def _keyword_picker_kb(rows: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for row in rows[:8]:
        bid = row["bricklink_id"]
        name = (row.get("name") or bid)[:40]
        builder.button(text=f"{bid} — {name}", callback_data=f"info_pick:{bid}")
    builder.adjust(1)
    return builder.as_markup()


def _record_label(idx: int, rec: dict) -> str:
    pb = rec.get("price_buy")
    ps = rec.get("price_sale")
    desc = (rec.get("description") or "").strip()
    label = f"#{idx}"
    if pb is not None:
        label += f" · покупка {pb}"
    if ps is not None:
        label += f" · продажа {ps}"
    if desc:
        short = desc[:12] + "…" if len(desc) > 12 else desc
        label += f" · {short}"
    return label[:48]


def _edit_field_kb(
    rec_id: int | None,
    serial: str,
    *,
    all_records: bool = False,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for field, label in (
        ("price_buy", "💵 Цена покупки"),
        ("price_sale", "💰 Цена продажи"),
        ("description", "📝 Описание"),
    ):
        if all_records:
            cb = f"info_edit_all_field:{field}:{serial}"
        else:
            cb = f"info_edit_field:{field}:{rec_id}:{serial}"
        builder.button(text=label, callback_data=cb)
    builder.button(text=MAIN_MENU_LABEL, callback_data="cancel")
    builder.adjust(1)
    return builder.as_markup()


def _pick_record_kb(records: list[dict], serial: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if len(records) > 1:
        builder.button(
            text=f"✏️ Все {len(records)} записи разом",
            callback_data=f"info_edit_all:{serial}",
        )
    for idx, rec in enumerate(records, start=1):
        rec_id = rec.get("id")
        if rec_id is None:
            continue
        builder.button(
            text=_record_label(idx, rec),
            callback_data=f"info_edit_pick:{rec_id}:{serial}",
        )
    builder.button(text=MAIN_MENU_LABEL, callback_data="cancel")
    builder.adjust(1)
    return builder.as_markup()


async def _start_figure_card(message: types.Message, state: FSMContext) -> None:
    await state.set_state(InfoFigures.waiting_serial)
    await message.answer(
        FIGURE_CARD_PROMPT,
        parse_mode="HTML",
        reply_markup=prompt_kb(),
    )


async def _records_for_serial(telegram_id: str, serial: str) -> list[dict]:
    records = await list_user_figures(telegram_id)
    return [
        r
        for r in records
        if (r.get("bricklink_id") or "").lower() == serial.lower()
    ]


@router.callback_query(F.data == "figure_card")
async def cb_figure_card(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await ensure_access(call, "figure_card"):
        return
    await call.answer()
    await state.clear()
    await _start_figure_card(call.message, state)


@router.callback_query(F.data == "info")
async def cb_info_legacy(call: types.CallbackQuery, state: FSMContext) -> None:
    await cb_figure_card(call, state)


@router.message(InfoFigures.waiting_serial)
async def get_info_figure(message: types.Message, state: FSMContext) -> None:
    text = message.text.strip()
    telegram_id = str(message.from_user.id)
    serials = parse_serial_list(text)

    if serials is not None:
        if len(serials) > MAX_SERIALS_PER_REQUEST:
            await message.answer(
                f"❗️ Не более {MAX_SERIALS_PER_REQUEST} артикулов за раз.",
                reply_markup=nav_kb(),
            )
            return
        await state.clear()
        for serial in serials:
            await handle_serial(serial, message.bot, message.chat.id, telegram_id)
        return

    await state.clear()

    try:
        found = await search_figures_by_keyword(text, limit=10)
    except HTTPStatusError:
        await message.answer(
            "Ошибка поиска в каталоге. Попробуйте артикул BrickLink.",
            reply_markup=nav_kb(),
        )
        return
    except Exception:
        await message.answer(
            "Не удалось выполнить поиск. Введите артикул, например <code>sw0001a</code>.",
            parse_mode="HTML",
            reply_markup=nav_kb(),
        )
        return

    if len(found) == 1:
        await handle_serial(
            found[0]["bricklink_id"],
            message.bot,
            message.chat.id,
            telegram_id,
        )
        return

    if len(found) > 1:
        await message.answer(
            f"По запросу «<i>{text}</i>» найдено <b>{len(found)}</b> вариантов. Выберите:",
            parse_mode="HTML",
            reply_markup=_keyword_picker_kb(found),
        )
        return

    await handle_serial(text.lower(), message.bot, message.chat.id, telegram_id)


@router.callback_query(lambda cb: cb.data and cb.data.startswith("info_pick:"))
async def cb_info_pick(call: types.CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    serial = call.data.split(":", 1)[1].lower()
    await state.clear()
    await handle_serial(serial, call.bot, call.message.chat.id, str(call.from_user.id))


@router.callback_query(lambda cb: cb.data and cb.data.startswith("select_similar:"))
async def cb_info_select(call: types.CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    _, serial = call.data.split(":", 1)
    try:
        await call.message.delete()
    except Exception:
        pass
    await state.clear()
    await handle_serial(serial, call.bot, call.message.chat.id, str(call.from_user.id))


async def handle_serial(
    serial: str,
    bot: Bot,
    chat_id: int,
    telegram_id: str,
    reply_markup=None,
):
    serial = serial.strip().lower()
    try:
        in_catalog = await send_figure_card(
            bot,
            chat_id,
            telegram_id,
            serial,
            reply_markup=reply_markup,
        )
    except HTTPStatusError as error:
        await bot.send_message(
            chat_id,
            f"Ошибка сервиса для {serial}: {error.response.status_code}",
            reply_markup=nav_kb(),
        )
        return
    except Exception:
        await bot.send_message(
            chat_id,
            f"Ошибка получения информации для {serial}.",
            reply_markup=nav_kb(),
        )
        return

    if not in_catalog:
        suggestions = await fetch_similar_serials(serial)
        if suggestions:
            kb = make_suggestions_kb(suggestions)
            await bot.send_message(
                chat_id,
                "Похожие варианты в каталоге бота:",
                reply_markup=kb,
            )


@router.callback_query(lambda cb: cb.data and cb.data.startswith("info_action:"))
async def cb_info_actions(call: types.CallbackQuery, state: FSMContext):
    parts = call.data.split(":")
    if len(parts) < 3:
        await call.answer("Некорректные данные.")
        return
    _, action, serial = parts[0], parts[1], parts[2]
    telegram_id = str(call.from_user.id)

    if action == "edit":
        await call.answer()
        try:
            matches = await _records_for_serial(telegram_id, serial)
        except Exception:
            await call.answer("Не удалось загрузить записи коллекции.")
            return
        if not matches:
            await call.answer("В коллекции нет записей для этой фигурки.")
            return
        await state.set_state(InfoFigures.waiting_edit_pick)
        if len(matches) == 1:
            rec_id = int(matches[0]["id"])
            await call.message.answer(
                f"Что изменить для <code>{serial}</code>?",
                parse_mode="HTML",
                reply_markup=_edit_field_kb(rec_id, serial),
            )
            return
        await call.message.answer(
            f"У вас <b>{len(matches)}</b> записей для <code>{serial}</code>.\n"
            "Можно изменить все сразу или выбрать одну:",
            parse_mode="HTML",
            reply_markup=_pick_record_kb(matches, serial),
        )
    elif action == "add":
        try:
            await add_figure_to_user(telegram_id=telegram_id, bricklink_id=serial)
            await call.answer("✅ Добавлено в коллекцию")
            await refresh_figure_card_message(call.message, telegram_id, serial)
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                await call.answer(
                    "Нет в каталоге. «❓ Помощь» → администратор.",
                    show_alert=True,
                )
            else:
                await call.answer("Ошибка добавления.")
    elif action == "delete":
        try:
            await delete_figure_from_user(telegram_id, serial)
            await call.answer("✅ Одна запись удалена")
            await refresh_figure_card_message(call.message, telegram_id, serial)
        except HTTPStatusError:
            await call.answer("Не удалось удалить.")
    else:
        await call.answer("Действие недоступно.")


@router.callback_query(lambda cb: cb.data and cb.data.startswith("info_edit_all:"))
async def cb_info_edit_all(call: types.CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    serial = call.data.split(":", 1)[1]
    await state.set_state(InfoFigures.waiting_edit_pick)
    await call.message.answer(
        f"Что изменить для <b>всех</b> записей <code>{serial}</code>?",
        parse_mode="HTML",
        reply_markup=_edit_field_kb(None, serial, all_records=True),
    )


@router.callback_query(lambda cb: cb.data and cb.data.startswith("info_edit_pick:"))
async def cb_info_edit_pick(call: types.CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    parts = call.data.split(":")
    if len(parts) != 3:
        return
    _, rec_id_raw, serial = parts
    if not rec_id_raw.isdigit():
        return
    await state.set_state(InfoFigures.waiting_edit_pick)
    await call.message.answer(
        f"Что изменить для записи #{rec_id_raw} (<code>{serial}</code>)?",
        parse_mode="HTML",
        reply_markup=_edit_field_kb(int(rec_id_raw), serial),
    )


@router.callback_query(
    lambda cb: cb.data
    and cb.data.startswith("info_edit_all_field:")
)
async def cb_info_edit_field_all(call: types.CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    parts = call.data.split(":", 2)
    if len(parts) != 3:
        await call.answer("Некорректные данные.", show_alert=True)
        return
    _, field, serial = parts
    if field not in {"price_buy", "price_sale", "description"}:
        await call.answer("Некорректные данные.", show_alert=True)
        return
    await state.update_data(
        info_edit_rec_id=None,
        info_edit_field=field,
        info_edit_serial=serial,
        info_edit_all=True,
    )
    await state.set_state(InfoFigures.waiting_edit_value)
    await _send_edit_prompt(call.message, field, all_records=True)


@router.callback_query(lambda cb: cb.data and cb.data.startswith("info_edit_field:"))
async def cb_info_edit_field(call: types.CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    parts = call.data.split(":", 3)
    if len(parts) != 4:
        await call.answer("Некорректные данные.")
        return
    _, field, rec_id_raw, serial = parts
    if field not in {"price_buy", "price_sale", "description"} or not rec_id_raw.isdigit():
        await call.answer("Некорректные данные.")
        return
    rec_id = int(rec_id_raw)
    await state.update_data(
        info_edit_rec_id=rec_id,
        info_edit_field=field,
        info_edit_serial=serial,
        info_edit_all=False,
    )
    await state.set_state(InfoFigures.waiting_edit_value)
    await _send_edit_prompt(call.message, field)


async def _send_edit_prompt(
    message: types.Message,
    field: str,
    *,
    all_records: bool = False,
) -> None:
    scope = " для всех записей" if all_records else ""
    prompts = {
        "price_buy": f"Введите новую цену покупки{scope} (число). Очистить: <code>-</code>",
        "price_sale": f"Введите новую цену продажи{scope} (число). Очистить: <code>-</code>",
        "description": f"Введите новое описание{scope}. Очистить: <code>-</code>",
    }
    await message.answer(
        prompts[field],
        parse_mode="HTML",
        reply_markup=nav_kb(),
    )


@router.message(InfoFigures.waiting_edit_value)
async def on_info_edit_value(message: types.Message, state: FSMContext) -> None:
    data = await state.get_data()
    rec_id = data.get("info_edit_rec_id")
    field = data.get("info_edit_field")
    serial = data.get("info_edit_serial")
    edit_all = bool(data.get("info_edit_all"))
    if not serial or field not in {"price_buy", "price_sale", "description"}:
        await state.clear()
        await message.answer(
            "Сессия редактирования устарела. Откройте карточку заново.",
            reply_markup=nav_kb(),
        )
        return
    if not edit_all and not rec_id:
        await state.clear()
        await message.answer(
            "Сессия редактирования устарела. Откройте карточку заново.",
            reply_markup=nav_kb(),
        )
        return

    raw = (message.text or "").strip()
    payload: dict[str, float | str | None] = {}
    if field in {"price_buy", "price_sale"}:
        if raw != "-":
            try:
                payload[field] = float(raw.replace(",", "."))
            except ValueError:
                await message.answer(
                    "Нужно число, например <code>1234.56</code>.",
                    parse_mode="HTML",
                )
                return
        else:
            payload[field] = None
    else:
        payload[field] = None if raw == "-" else raw[:500]

    telegram_id = str(message.from_user.id)
    try:
        if edit_all:
            count = await update_all_user_figure_records(
                telegram_id, serial, **payload
            )
            if count == 0:
                await message.answer(
                    "Записи не найдены.",
                    reply_markup=nav_kb(),
                )
                await state.clear()
                return
            await message.answer(
                f"✅ Обновлено записей: <b>{count}</b>. Обновляю карточку…",
                parse_mode="HTML",
            )
        else:
            await update_user_figure_record(int(rec_id), **payload)
            await message.answer("✅ Изменения сохранены. Обновляю карточку…")
    except HTTPStatusError as e:
        detail = "Не удалось сохранить изменения."
        if e.response.status_code == 422:
            try:
                body = e.response.json()
                if isinstance(body.get("detail"), list) and body["detail"]:
                    detail += f"\n{body['detail'][0].get('msg', '')}"
                elif isinstance(body.get("detail"), str):
                    detail += f"\n{body['detail']}"
            except Exception:
                pass
        await message.answer(detail, reply_markup=nav_kb())
        return
    except Exception:
        await message.answer(
            "Ошибка сохранения. Попробуйте ещё раз.",
            reply_markup=nav_kb(),
        )
        return

    await state.clear()
    await send_figure_card_with_loading(
        message.bot,
        message.chat.id,
        telegram_id,
        serial,
    )
