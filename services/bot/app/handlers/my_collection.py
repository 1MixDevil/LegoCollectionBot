"""Моя коллекция: сводка, список с поиском, экспорт."""

from __future__ import annotations

import logging
import os
from io import BytesIO

import pandas as pd
from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile

from app.api.collection import clear_user_collection, list_user_figures
from app.core.access import ensure_access, get_main_keyboard
from app.keyboards.collection import (
    collection_browse_kb,
    collection_confirm_clear_kb,
    collection_figure_kb,
    collection_menu_kb,
    collection_page_picker_kb,
)
from app.keyboards.main import prompt_kb
from app.services.collection_stats import (
    PICK_PAGE_SIZE,
    build_collection_summary,
    filter_unique_figures,
    format_browse_header,
    unique_figure_entries,
)
from app.services.collage import StarWarsCollageGenerator
from app.services.collage_delivery import send_collage_batches
from app.services.collage_limits import COLLAGE_BATCH_SIZE, should_send_in_batches
from app.services.figure_display import send_figure_card_with_loading
from app.states.figures import CollectionState
from app.utils.message import safe_edit_or_answer

logger = logging.getLogger(__name__)
router = Router()

PICK_PAGE_SIZE = int(os.getenv("COLLECTION_PICK_PAGE_SIZE", str(PICK_PAGE_SIZE)))


def _with_counts(records: list[dict]) -> list[dict]:
    counts: dict[str, int] = {}
    first: dict[str, dict] = {}
    ordered: list[str] = []
    for rec in records:
        bid = (rec.get("bricklink_id") or "").strip().lower()
        if not bid:
            continue
        counts[bid] = counts.get(bid, 0) + 1
        if bid not in first:
            first[bid] = dict(rec)
            ordered.append(bid)
    out: list[dict] = []
    for bid in ordered:
        item = first[bid]
        item["count"] = counts[bid]
        if counts[bid] > 1:
            item["repeat_count"] = counts[bid]
        out.append(item)
    return out


async def _main_kb(user_id: int):
    return await get_main_keyboard(str(user_id))


async def _load_records(telegram_id: str) -> list[dict]:
    raw = await list_user_figures(telegram_id)
    return [
        r if isinstance(r, dict) else (r.dict() if hasattr(r, "dict") else dict(r))
        for r in raw
    ]


async def _enter_collection_search_mode(state: FSMContext) -> None:
    """После входа в коллекцию текст в чате = поиск."""
    await state.set_state(CollectionState.browsing)
    await state.update_data(coll_query="", coll_page=0)


async def _show_collection_home(
    target: types.Message,
    telegram_id: str,
    state: FSMContext,
    *,
    edit: bool = False,
) -> None:
    records = await _load_records(telegram_id)
    text = build_collection_summary(records)
    kb = collection_menu_kb() if records else await _main_kb(int(telegram_id))

    if records:
        await _enter_collection_search_mode(state)
    else:
        await state.clear()

    if edit and target.text:
        await safe_edit_or_answer(target, text, parse_mode="HTML", reply_markup=kb)
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=kb)


def _browse_pages(entries: list[dict]) -> int:
    if not entries:
        return 1
    return max(1, (len(entries) + PICK_PAGE_SIZE - 1) // PICK_PAGE_SIZE)


async def _show_browse(
    target: types.Message,
    state: FSMContext,
    telegram_id: str,
    *,
    query: str | None,
    page: int,
    edit: bool = False,
) -> None:
    records = await _load_records(telegram_id)
    q = (query or "").strip()
    if q:
        entries = filter_unique_figures(records, q)
    else:
        entries = unique_figure_entries(records)

    pages = _browse_pages(entries)
    page = max(0, min(page, pages - 1))

    await state.set_state(CollectionState.browsing)
    await state.update_data(
        coll_query=q,
        coll_page=page,
        coll_pages=pages,
        coll_ids=[e["bricklink_id"] for e in entries],
    )

    text = format_browse_header(
        query=q or None,
        total=len(entries),
        page=page,
        pages=pages,
    )
    kb = collection_browse_kb(entries, page, page_size=PICK_PAGE_SIZE)

    if edit and target.text:
        await safe_edit_or_answer(target, text, parse_mode="HTML", reply_markup=kb)
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data == "my_collection")
async def cb_my_collection(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await ensure_access(call, "my_collection"):
        return
    await call.answer()
    await _show_collection_home(
        call.message,
        str(call.from_user.id),
        state,
        edit=bool(call.message.text),
    )


@router.callback_query(F.data.startswith("collection_browse:"))
async def cb_collection_browse(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await ensure_access(call, "my_collection"):
        return
    part = call.data.split(":", 1)[1]
    page = int(part)
    await call.answer()
    records = await _load_records(str(call.from_user.id))
    if not records:
        await call.message.answer(
            "Коллекция пуста.",
            reply_markup=await _main_kb(call.from_user.id),
        )
        return
    data = await state.get_data()
    query = data.get("coll_query", "")
    await _show_browse(
        call.message,
        state,
        str(call.from_user.id),
        query=query,
        page=page,
        edit=bool(call.message.text),
    )


@router.callback_query(F.data == "collection_pages")
async def cb_collection_pages(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await ensure_access(call, "my_collection"):
        return
    await call.answer()
    data = await state.get_data()
    pages = int(data.get("coll_pages") or 1)
    current = int(data.get("coll_page", 0))
    if pages <= 1:
        return
    text = f"📄 <b>Страница {current + 1}</b> из {pages}\n\nВыберите номер:"
    await safe_edit_or_answer(
        call.message,
        text,
        parse_mode="HTML",
        reply_markup=collection_page_picker_kb(current, pages),
    )


@router.callback_query(F.data == "collection_browse_resume")
async def cb_collection_browse_resume(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await ensure_access(call, "my_collection"):
        return
    await call.answer()
    data = await state.get_data()
    await _show_browse(
        call.message,
        state,
        str(call.from_user.id),
        query=data.get("coll_query", ""),
        page=int(data.get("coll_page", 0)),
        edit=bool(call.message.text),
    )


@router.callback_query(F.data.startswith("collection_list:"))
async def cb_collection_list_legacy(call: types.CallbackQuery, state: FSMContext) -> None:
    """Старые кнопки «collection_list:N» → новый список."""
    if not await ensure_access(call, "my_collection"):
        return
    part = call.data.split(":", 1)[1]
    await call.answer()
    await _show_browse(
        call.message,
        state,
        str(call.from_user.id),
        query="",
        page=int(part),
        edit=bool(call.message.text),
    )


@router.callback_query(F.data == "collection_find")
async def cb_collection_find(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await ensure_access(call, "my_collection"):
        return
    await call.answer()
    await _enter_collection_search_mode(state)
    await call.message.answer(
        "🔍 Введите в чат артикул или слова из названия "
        "(например <code>sw0001</code> или <code>Clone</code>).",
        parse_mode="HTML",
        reply_markup=prompt_kb(back="my_collection"),
    )


@router.message(CollectionState.waiting_list_query, F.text)
async def on_collection_list_query(message: types.Message, state: FSMContext) -> None:
    """Совместимость со старым шагом «Поиск в списке»."""
    await state.set_state(CollectionState.browsing)
    await on_collection_browse_text(message, state)


@router.message(CollectionState.browsing, F.text)
async def on_collection_browse_text(message: types.Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    if not raw or raw.startswith("/"):
        return
    text = raw.lower()

    records = await _load_records(str(message.from_user.id))
    entries = filter_unique_figures(records, text)
    ids = {e["bricklink_id"] for e in entries}

    if text in ids or len(entries) == 1:
        bid = text if text in ids else entries[0]["bricklink_id"]
        await state.set_state(CollectionState.browsing)
        await send_figure_card_with_loading(
            message.bot,
            message.chat.id,
            str(message.from_user.id),
            bid,
            reply_markup=collection_figure_kb(bid),
        )
        return

    await _show_browse(
        message,
        state,
        str(message.from_user.id),
        query=text,
        page=0,
    )


@router.callback_query(F.data.startswith("coll_pick:"))
async def cb_coll_pick(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await ensure_access(call, "my_collection"):
        return
    bid = call.data.split(":", 1)[1].lower()
    await call.answer()
    await state.set_state(CollectionState.browsing)
    await send_figure_card_with_loading(
        call.bot,
        call.message.chat.id,
        str(call.from_user.id),
        bid,
        reply_markup=collection_figure_kb(bid),
    )


@router.callback_query(F.data == "collection_search")
async def cb_collection_search_legacy(call: types.CallbackQuery, state: FSMContext) -> None:
    await cb_collection_find(call, state)


@router.callback_query(F.data == "collection_info")
async def cb_collection_info_legacy(call: types.CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.answer(
        "Карточка фигурки — «ℹ️ Карточка фигурки» в главном меню (/menu).",
        show_alert=True,
    )


@router.callback_query(F.data == "collection_remove")
async def cb_collection_remove_legacy(call: types.CallbackQuery) -> None:
    await call.answer(
        "Удаление — откройте фигурку из списка, на карточке «Удалить из коллекции».",
        show_alert=True,
    )


@router.callback_query(F.data == "collection_clear_confirm")
async def cb_collection_clear_confirm(call: types.CallbackQuery) -> None:
    if not await ensure_access(call, "my_collection"):
        return
    await call.answer()
    records = await _load_records(str(call.from_user.id))
    if not records:
        await call.message.answer("Коллекция уже пуста.", reply_markup=await _main_kb(call.from_user.id))
        return
    await call.message.answer(
        f"⚠️ Удалить <b>все {len(records)}</b> записей из коллекции?\n"
        "Сами фигурки в общем каталоге останутся.",
        parse_mode="HTML",
        reply_markup=collection_confirm_clear_kb(len(records)),
    )


@router.callback_query(F.data == "collection_clear_yes")
async def cb_collection_clear_yes(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await ensure_access(call, "my_collection"):
        return
    await state.clear()
    await call.answer("Коллекция очищена")
    await clear_user_collection(str(call.from_user.id))
    await call.message.answer(
        "🗑 Коллекция полностью очищена.",
        reply_markup=await _main_kb(call.from_user.id),
    )


@router.callback_query(F.data == "collection_clear")
async def cb_collection_clear_legacy(call: types.CallbackQuery) -> None:
    await cb_collection_clear_confirm(call)


@router.callback_query(F.data == "collection_tierlist")
async def cb_collection_tierlist(call: types.CallbackQuery) -> None:
    if not await ensure_access(call, "my_collection"):
        return
    await call.answer("Собираю коллаж…")
    user_id = str(call.from_user.id)
    records = await _load_records(user_id)

    if not records:
        return await call.message.answer(
            "Ваша коллекция пуста.",
            reply_markup=await _main_kb(call.from_user.id),
        )

    df = StarWarsCollageGenerator.filter_by_keyword(
        data=records, name_key="name", keyword=""
    )
    if len(df) == 0:
        return await call.message.answer(
            "После фильтрации нет элементов.",
            reply_markup=await _main_kb(call.from_user.id),
        )

    rows = _with_counts(df.to_dict(orient="records"))
    total = len(rows)
    if should_send_in_batches(total):
        await call.message.answer(
            f"В коллекции <b>{total}</b> записей — отправлю коллаж "
            f"частями по <b>{COLLAGE_BATCH_SIZE}</b> фигурок.",
            parse_mode="HTML",
        )

    await send_collage_batches(
        call.message,
        rows,
        title="Моя коллекция",
        telegram_id=user_id,
        caption_label=f"{total} записей",
        caption_prefix="🖼 Коллаж",
        reply_markup=collection_menu_kb(),
    )


@router.callback_query(F.data == "collection_excel")
async def cb_collection_excel(call: types.CallbackQuery) -> None:
    if not await ensure_access(call, "my_collection"):
        return
    await call.answer()
    records = await _load_records(str(call.from_user.id))
    if not records:
        return await call.message.answer(
            "Коллекция пуста.",
            reply_markup=await _main_kb(call.from_user.id),
        )

    rows = _with_counts(records)
    df = pd.DataFrame(rows)
    preferred_cols = [
        "bricklink_id",
        "name",
        "count",
        "price_buy",
        "price_sale",
        "description",
        "buy_date",
        "sale_date",
    ]
    cols = [c for c in preferred_cols if c in df.columns]
    if cols:
        df = df[cols]
    buf = BytesIO()
    df.to_excel(buf, index=False)
    buf.seek(0)
    document = BufferedInputFile(buf.read(), filename="collection.xlsx")
    await call.bot.send_document(
        chat_id=call.from_user.id,
        document=document,
        caption=f"📊 Экспорт: {len(rows)} уникальных фигурок",
        reply_markup=collection_menu_kb(),
    )
