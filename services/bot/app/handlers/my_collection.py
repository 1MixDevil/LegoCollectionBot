"""Моя коллекция: сводка, список, поиск, экспорт."""

from __future__ import annotations

import logging
import os
import tempfile
from io import BytesIO

import pandas as pd
from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile

from app.api.collection import clear_user_collection, delete_figure_from_user, list_user_figures
from app.core.access import ensure_access, get_main_keyboard
from app.keyboards.collection import (
    collection_confirm_clear_kb,
    collection_list_kb,
    collection_menu_kb,
)
from app.keyboards.main import prompt_kb
from app.services.collection_stats import (
    build_collection_summary,
    filter_collection_records,
    format_collection_page,
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
LIST_PAGE_SIZE = int(os.getenv("COLLECTION_LIST_PAGE_SIZE", "12"))


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


@router.callback_query(F.data.startswith("collection_list:"))
async def cb_collection_list(call: types.CallbackQuery, state: FSMContext) -> None:
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

    text, pages = format_collection_page(
        records, page, page_size=LIST_PAGE_SIZE, title="📋 Ваша коллекция"
    )
    await safe_edit_or_answer(
        call.message,
        text,
        parse_mode="HTML",
        reply_markup=collection_list_kb(page, pages),
    )


@router.callback_query(F.data == "collection_search")
async def cb_collection_search(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await ensure_access(call, "my_collection"):
        return
    await call.answer()
    await state.set_state(CollectionState.waiting_search)
    await call.message.answer(
        "🔍 <b>Поиск в коллекции</b>\n\n"
        "Введите артикул или слова из названия "
        "(например <code>sw0001</code> или <code>Clone Trooper</code>).",
        parse_mode="HTML",
        reply_markup=prompt_kb(back="my_collection"),
    )


@router.message(CollectionState.waiting_search, F.text)
async def on_collection_search(message: types.Message, state: FSMContext) -> None:
    query = message.text.strip()
    if not query:
        await message.answer("Введите текст для поиска.", reply_markup=prompt_kb(back="my_collection"))
        return

    records = await _load_records(str(message.from_user.id))
    found = filter_collection_records(records, query)
    await state.clear()

    if not found:
        await message.answer(
            f"По запросу «{query}» в коллекции ничего нет.",
            reply_markup=collection_menu_kb(),
        )
        return

    text, pages = format_collection_page(
        found,
        0,
        page_size=LIST_PAGE_SIZE,
        title=f"🔍 Поиск: {query}",
    )
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=collection_list_kb(0, pages),
    )


@router.callback_query(F.data == "collection_info")
async def cb_collection_info(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await ensure_access(call, "my_collection"):
        return
    await call.answer()
    await state.set_state(CollectionState.waiting_info_serial)
    await call.message.answer(
        "🔎 Введите артикул BrickLink из вашей коллекции "
        "(например <code>sw0001a</code>):",
        parse_mode="HTML",
        reply_markup=prompt_kb(back="my_collection"),
    )


@router.message(CollectionState.waiting_info_serial, F.text)
async def on_collection_info_serial(message: types.Message, state: FSMContext) -> None:
    serial = message.text.strip().lower()
    await state.clear()
    if not serial:
        return
    await send_figure_card(
        message.bot,
        message.chat.id,
        str(message.from_user.id),
        serial,
        reply_markup=collection_menu_kb(),
    )


@router.callback_query(F.data == "collection_remove")
async def cb_collection_remove(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await ensure_access(call, "my_collection"):
        return
    await call.answer()
    await state.set_state(CollectionState.waiting_remove)
    await call.message.answer(
        "➖ <b>Удалить из коллекции</b>\n\n"
        "Введите артикул. Удалится одна запись "
        "(если артикул добавляли дважды — удалите ещё раз).",
        parse_mode="HTML",
        reply_markup=prompt_kb(back="my_collection"),
    )


@router.message(CollectionState.waiting_remove, F.text)
async def on_collection_remove(message: types.Message, state: FSMContext) -> None:
    serial = message.text.strip().lower()
    await state.clear()
    try:
        await delete_figure_from_user(str(message.from_user.id), serial)
        records = await _load_records(str(message.from_user.id))
        await message.answer(
            f"✅ <code>{serial}</code> удалён из коллекции.\n\n"
            + build_collection_summary(records),
            parse_mode="HTML",
            reply_markup=collection_menu_kb() if records else await _main_kb(message.from_user.id),
        )
    except Exception as e:
        await message.answer(
            f"Не удалось удалить: {e}",
            reply_markup=collection_menu_kb(),
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
    """Старый callback — перенаправляем на подтверждение."""
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
