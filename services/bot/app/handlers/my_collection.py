"""Моя коллекция: сводка, список с поиском, экспорт."""

from __future__ import annotations

import logging
import os
import tempfile
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
from app.services.figure_display import send_figure_card
from app.states.figures import CollectionState
from app.utils.message import safe_edit_or_answer

logger = logging.getLogger(__name__)
router = Router()

PREFIX_URL = os.getenv("COLL_PREFIX_URL", "https://img.bricklink.com/ItemImage/MN/0")
MIN_HEIGHT = int(os.getenv("COLL_MIN_HEIGHT", "1050"))
COLS = int(os.getenv("COLL_COLUMNS", "5"))
MAX_CONN = int(os.getenv("CONCURRENT_BATCHES", "5"))
PICK_PAGE_SIZE = int(os.getenv("COLLECTION_PICK_PAGE_SIZE", str(PICK_PAGE_SIZE)))


async def _main_kb(user_id: int):
    return await get_main_keyboard(str(user_id))


async def _load_records(telegram_id: str) -> list[dict]:
    raw = await list_user_figures(telegram_id)
    return [
        r if isinstance(r, dict) else (r.dict() if hasattr(r, "dict") else dict(r))
        for r in raw
    ]


async def _show_collection_home(
    target: types.Message,
    telegram_id: str,
    *,
    edit: bool = False,
) -> None:
    records = await _load_records(telegram_id)
    text = build_collection_summary(records)
    kb = collection_menu_kb() if records else await _main_kb(int(telegram_id))

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
    await state.clear()
    await call.answer()
    await _show_collection_home(
        call.message,
        str(call.from_user.id),
        edit=bool(call.message.text),
    )


@router.callback_query(F.data.startswith("collection_browse:"))
async def cb_collection_browse(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await ensure_access(call, "my_collection"):
        return
    part = call.data.split(":", 1)[1]
    if part == "noop":
        await call.answer()
        return

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


@router.callback_query(F.data == "collection_browse_all")
async def cb_collection_browse_all(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await ensure_access(call, "my_collection"):
        return
    await call.answer()
    records = await _load_records(str(call.from_user.id))
    if not records:
        await call.message.answer(
            "Коллекция пуста.",
            reply_markup=await _main_kb(call.from_user.id),
        )
        return
    await _show_browse(
        call.message,
        state,
        str(call.from_user.id),
        query="",
        page=0,
        edit=bool(call.message.text),
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
    if part == "noop":
        await call.answer()
        return
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
    await state.set_state(CollectionState.waiting_list_query)
    await call.message.answer(
        "🔍 <b>Поиск в списке</b>\n\n"
        "Введите артикул или слова из названия "
        "(например <code>sw0001</code> или <code>Clone</code>).",
        parse_mode="HTML",
        reply_markup=prompt_kb(back="collection_browse:0"),
    )


@router.message(CollectionState.waiting_list_query, F.text)
async def on_collection_list_query(message: types.Message, state: FSMContext) -> None:
    query = message.text.strip()
    if not query:
        await message.answer(
            "Введите текст для поиска.",
            reply_markup=prompt_kb(back="collection_browse:0"),
        )
        return
    await _show_browse(
        message,
        state,
        str(message.from_user.id),
        query=query,
        page=0,
    )


@router.message(CollectionState.browsing, F.text)
async def on_collection_browse_text(message: types.Message, state: FSMContext) -> None:
    text = message.text.strip().lower()
    if not text:
        return

    records = await _load_records(str(message.from_user.id))
    entries = filter_unique_figures(records, text)
    ids = {e["bricklink_id"] for e in entries}

    if text in ids or len(entries) == 1:
        bid = text if text in ids else entries[0]["bricklink_id"]
        await state.set_state(CollectionState.browsing)
        await send_figure_card(
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
    await send_figure_card(
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

    status = await call.message.answer("⏳ Загружаю изображения и собираю коллаж…")
    tmp_path = None
    try:
        raw = await StarWarsCollageGenerator.fetch_and_prepare_images_async(
            records=df,
            id_key="bricklink_id",
            prefix_url=PREFIX_URL,
            min_height=MIN_HEIGHT,
            font_path="arial.ttf",
            font_size=90,
            max_connections=MAX_CONN,
            timeout=15,
        )
        if not raw:
            await status.edit_text("Не удалось загрузить изображения.")
            return

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
            tmp_path = tf.name
        await StarWarsCollageGenerator.create_collage_async(
            images=raw,
            output_path=tmp_path,
            columns=COLS,
            title="Моя коллекция",
            font_path="arial.ttf",
            font_size=90,
        )
        with open(tmp_path, "rb") as f:
            doc = BufferedInputFile(f.read(), filename="collection.png")
        await status.delete()
        await call.bot.send_document(
            chat_id=call.from_user.id,
            document=doc,
            caption=f"🖼 Коллаж из {len(df)} фигурок",
            reply_markup=collection_menu_kb(),
        )
    except Exception:
        logger.exception("collection tierlist")
        await status.edit_text("Ошибка при сборке коллажа.")
    finally:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except OSError:
                pass


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

    df = pd.DataFrame(records)
    buf = BytesIO()
    df.to_excel(buf, index=False)
    buf.seek(0)
    document = BufferedInputFile(buf.read(), filename="collection.xlsx")
    await call.bot.send_document(
        chat_id=call.from_user.id,
        document=document,
        caption=f"📊 Экспорт: {len(records)} записей",
        reply_markup=collection_menu_kb(),
    )
