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
    update_user_figure_record,
)
from app.core.access import ensure_access, get_main_keyboard
from app.core.config import MAX_SERIALS_PER_REQUEST
from app.keyboards.main import make_suggestions_kb, nav_kb, prompt_kb
from app.services.figure_display import send_figure_card
from app.states.figures import InfoFigures
from app.utils.serial_parse import parse_serial_list

router = Router()

FIGURE_CARD_PROMPT = (
    "ℹ️ <b>Карточка фигурки</b>\n\n"
    "Введите артикул BrickLink (например <code>sw0001a</code>) "
    "или название целиком — фото, цены и записи в коллекции.\n\n"
    "<i>Несколько артикулов — только через запятую: "
    "<code>sw0001a, sw0002</code>. По фото — просто пришлите снимок в чат.</i>"
)


def _keyword_picker_kb(rows: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for row in rows[:8]:
        bid = row["bricklink_id"]
        name = (row.get("name") or bid)[:40]
        builder.button(text=f"{bid} — {name}", callback_data=f"info_pick:{bid}")
    builder.adjust(1)
    return builder.as_markup()


async def _start_figure_card(message: types.Message, state: FSMContext) -> None:
    await state.set_state(InfoFigures.waiting_serial)
    await message.answer(
        FIGURE_CARD_PROMPT,
        parse_mode="HTML",
        reply_markup=prompt_kb(),
    )


def _edit_field_kb(rec_id: int, serial: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="💵 Цена покупки",
        callback_data=f"info_edit_field:price_buy:{rec_id}:{serial}",
    )
    builder.button(
        text="💰 Цена продажи",
        callback_data=f"info_edit_field:price_sale:{rec_id}:{serial}",
    )
    builder.button(
        text="📝 Описание",
        callback_data=f"info_edit_field:description:{rec_id}:{serial}",
    )
    builder.button(text="❌ Отмена", callback_data="cancel")
    builder.adjust(1)
    return builder.as_markup()


def _pick_record_kb(records: list[dict], serial: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for idx, rec in enumerate(records, start=1):
        rec_id = rec.get("id")
        if rec_id is None:
            continue
        pb = rec.get("price_buy")
        ps = rec.get("price_sale")
        desc = (rec.get("description") or "").strip()
        label = f"#{idx}"
        if pb is not None:
            label += f" · buy {pb}"
        if ps is not None:
            label += f" · sell {ps}"
        if desc:
            label += " · note"
        builder.button(
            text=label[:48],
            callback_data=f"info_edit_pick:{rec_id}:{serial}",
        )
    builder.button(text="❌ Отмена", callback_data="cancel")
    builder.adjust(1)
    return builder.as_markup()


@router.callback_query(F.data == "figure_card")
async def cb_figure_card(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await ensure_access(call, "figure_card"):
        return
    await call.answer()
    await state.clear()
    await _start_figure_card(call.message, state)


@router.callback_query(F.data == "info")
async def cb_info_legacy(call: types.CallbackQuery, state: FSMContext) -> None:
    """Старый callback — то же, что «Карточка фигурки»."""
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
        main_kb = await get_main_keyboard(telegram_id)
        for serial in serials:
            await handle_serial(
                serial, message.bot, message.chat.id, telegram_id, main_kb
            )
        return

    await state.clear()
    main_kb = await get_main_keyboard(telegram_id)

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
            main_kb,
        )
        return

    if len(found) > 1:
        await message.answer(
            f"По запросу «<i>{text}</i>» найдено <b>{len(found)}</b> вариантов. Выберите:",
            parse_mode="HTML",
            reply_markup=_keyword_picker_kb(found),
        )
        return

    await handle_serial(text.lower(), message.bot, message.chat.id, telegram_id, main_kb)


@router.callback_query(lambda cb: cb.data and cb.data.startswith("info_pick:"))
async def cb_info_pick(call: types.CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    serial = call.data.split(":", 1)[1].lower()
    await state.clear()
    telegram_id = str(call.from_user.id)
    main_kb = await get_main_keyboard(telegram_id)
    await handle_serial(serial, call.bot, call.message.chat.id, telegram_id, main_kb)


@router.callback_query(lambda cb: cb.data and cb.data.startswith("select_similar:"))
async def cb_info_select(call: types.CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    _, serial = call.data.split(":", 1)
    await call.message.delete()
    telegram_id = str(call.from_user.id)
    main_kb = await get_main_keyboard(telegram_id)
    await handle_serial(serial, call.bot, call.message.chat.id, telegram_id, main_kb)


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
        await call.answer("Функционал пока не реализован.", show_alert=True)
        return
    _, action, serial = parts[0], parts[1], parts[2]
    telegram_id = str(call.from_user.id)

    if action in ("buy", "sell"):
        await call.answer("Функционал пока не реализован.", show_alert=True)
    elif action == "wishlist":
        await call.answer("Функционал пока не реализован.", show_alert=True)
    elif action == "edit":
        try:
            records = await list_user_figures(telegram_id)
        except Exception:
            await call.answer("Не удалось загрузить записи коллекции.", show_alert=True)
            return
        matches = [
            r
            for r in records
            if (r.get("bricklink_id") or "").lower() == serial.lower()
        ]
        if not matches:
            await call.answer("В коллекции нет записей для этой фигурки.", show_alert=True)
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
            f"Найдено {len(matches)} записей для <code>{serial}</code>. Выберите запись:",
            parse_mode="HTML",
            reply_markup=_pick_record_kb(matches, serial),
        )
    elif action == "add":
        try:
            await add_figure_to_user(telegram_id=telegram_id, bricklink_id=serial)
            await call.answer("Фигурка добавлена!", show_alert=True)
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                await call.answer(
                    "Фигурка не найдена в каталоге. «🔄 Обновить каталог» или «❓ Помощь».",
                    show_alert=True,
                )
            else:
                await call.answer("Ошибка добавления.", show_alert=True)
    elif action == "delete":
        try:
            await delete_figure_from_user(telegram_id, serial)
            await call.answer("Фигурка удалена!", show_alert=True)
        except HTTPStatusError:
            await call.answer("Не удалось удалить.", show_alert=True)
    else:
        await call.answer("Функционал пока не реализован.", show_alert=True)


@router.callback_query(lambda cb: cb.data and cb.data.startswith("info_edit_pick:"))
async def cb_info_edit_pick(call: types.CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    parts = call.data.split(":")
    if len(parts) != 3:
        return
    _, rec_id_raw, serial = parts
    if not rec_id_raw.isdigit():
        return
    await state.set_state(InfoFigures.waiting_edit_value)
    await call.message.answer(
        f"Что изменить для <code>{serial}</code>?",
        parse_mode="HTML",
        reply_markup=_edit_field_kb(int(rec_id_raw), serial),
    )


@router.callback_query(lambda cb: cb.data and cb.data.startswith("info_edit_field:"))
async def cb_info_edit_field(call: types.CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    parts = call.data.split(":")
    if len(parts) != 5:
        await call.answer("Некорректные данные.", show_alert=True)
        return
    _, _, field, rec_id_raw, serial = parts
    if field not in {"price_buy", "price_sale", "description"} or not rec_id_raw.isdigit():
        await call.answer("Некорректные данные.", show_alert=True)
        return
    rec_id = int(rec_id_raw)
    await state.update_data(info_edit_rec_id=rec_id, info_edit_field=field, info_edit_serial=serial)
    await state.set_state(InfoFigures.waiting_edit_value)
    prompts = {
        "price_buy": "Введите новую цену покупки (число). Для очистки: <code>-</code>",
        "price_sale": "Введите новую цену продажи (число). Для очистки: <code>-</code>",
        "description": "Введите новое описание. Для очистки: <code>-</code>",
    }
    await call.message.answer(prompts[field], parse_mode="HTML", reply_markup=nav_kb())


@router.message(InfoFigures.waiting_edit_value)
async def on_info_edit_value(message: types.Message, state: FSMContext) -> None:
    data = await state.get_data()
    rec_id = data.get("info_edit_rec_id")
    field = data.get("info_edit_field")
    serial = data.get("info_edit_serial")
    if not rec_id or field not in {"price_buy", "price_sale", "description"}:
        await state.clear()
        await message.answer("Сессия редактирования устарела. Откройте карточку заново.")
        return

    raw = (message.text or "").strip()
    payload: dict[str, float | str | None] = {}
    if field in {"price_buy", "price_sale"}:
        if raw != "-":
            try:
                payload[field] = float(raw.replace(",", "."))
            except ValueError:
                await message.answer("Нужно число, например <code>1234.56</code>.", parse_mode="HTML")
                return
        else:
            payload[field] = None
    else:
        payload[field] = None if raw == "-" else raw[:500]

    try:
        await update_user_figure_record(int(rec_id), **payload)
    except HTTPStatusError:
        await message.answer("Не удалось сохранить изменения.")
        return
    except Exception:
        await message.answer("Ошибка сохранения. Попробуйте ещё раз.")
        return

    await state.clear()
    telegram_id = str(message.from_user.id)
    main_kb = await get_main_keyboard(telegram_id)
    await message.answer("✅ Изменения сохранены. Обновляю карточку…")
    await handle_serial(serial, message.bot, message.chat.id, telegram_id, main_kb)
