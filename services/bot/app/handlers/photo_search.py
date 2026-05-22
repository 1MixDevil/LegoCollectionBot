"""Поиск минифигурки по фото (Brickognize)."""

from __future__ import annotations

import logging
from io import BytesIO

import httpx
from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.core.access import ensure_access, get_main_keyboard
from app.keyboards.main import prompt_kb
from app.services.brickognize import format_top_candidates, search_by_image_bytes
from app.services.figure_display import send_figure_card
from app.states.figures import PhotoSearchState
from app.utils.message import answer_callback

logger = logging.getLogger(__name__)
router = Router()


def _candidate_picker_kb(candidates: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for row in candidates:
        bid = row["bricklink_id"]
        name = (row.get("name") or bid)[:36]
        score = (row.get("score") or 0) * 100
        builder.button(
            text=f"{name} ({score:.0f}%)",
            callback_data=f"photo_pick:{bid}",
        )
    builder.button(text="📷 Другой снимок", callback_data="photo_search")
    builder.button(text="❌ Отмена", callback_data="cancel")
    builder.adjust(1)
    return builder.as_markup()


async def _download_telegram_image(message: types.Message) -> tuple[bytes, str]:
    if message.photo:
        photo = message.photo[-1]
        filename = "photo.jpg"
    elif message.document and message.document.mime_type:
        if not message.document.mime_type.startswith("image/"):
            raise ValueError("not_image")
        photo = message.document
        filename = message.document.file_name or "photo.jpg"
    else:
        raise ValueError("no_image")

    buf = BytesIO()
    tg_file = await message.bot.get_file(photo.file_id)
    await message.bot.download_file(tg_file.file_path, buf)
    return buf.getvalue(), filename


@router.callback_query(F.data == "photo_search")
async def cb_photo_search_start(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await ensure_access(call, "photo_search"):
        return
    await state.set_state(PhotoSearchState.waiting_photo)
    await answer_callback(
        call,
        "📷 <b>Поиск по фото</b>\n\n"
        "Отправьте фото минифигурки (как изображение, не файлом — "
        "или как .jpg/.png).\n"
        "Я попробую определить артикул BrickLink.",
        parse_mode="HTML",
        reply_markup=prompt_kb(),
    )


@router.message(PhotoSearchState.waiting_photo, F.photo | F.document)
async def on_photo_received(message: types.Message, state: FSMContext) -> None:
    telegram_id = str(message.from_user.id)
    kb = await get_main_keyboard(telegram_id)
    status = await message.answer("🔎 Ищу на Brickognize…", reply_markup=kb)

    try:
        image_bytes, filename = await _download_telegram_image(message)
    except ValueError as exc:
        if str(exc) == "not_image":
            text = "Отправьте изображение (фото или .jpg/.png)."
        else:
            text = "Пришлите фото минифигурки."
        await status.edit_text(text, reply_markup=prompt_kb())
        return

    try:
        result = await search_by_image_bytes(image_bytes, filename)
        candidates = format_top_candidates(result, limit=5, minifigs_only=True)
        if not candidates:
            candidates = format_top_candidates(result, limit=5, minifigs_only=False)
    except httpx.HTTPStatusError as e:
        logger.exception("Brickognize HTTP error")
        await status.edit_text(
            f"Сервис распознавания недоступен ({e.response.status_code}). "
            "Попробуйте позже.",
            reply_markup=kb,
        )
        await state.clear()
        return
    except Exception:
        logger.exception("Brickognize error")
        await status.edit_text(
            "Не удалось распознать фото. Попробуйте другой ракурс или освещение.",
            reply_markup=kb,
        )
        await state.clear()
        return

    await status.delete()

    if not candidates:
        await message.answer(
            "Ничего похожего на минифигурку не найдено.\n"
            "Попробуйте крупнее, на однотонном фоне.",
            reply_markup=kb,
        )
        await state.clear()
        return

    if len(candidates) == 1 or (candidates[0].get("score") or 0) >= 0.85:
        best = candidates[0]
        await send_figure_card(
            message.bot,
            message.chat.id,
            telegram_id,
            best["bricklink_id"],
            name=best.get("name"),
            bricklink_url=best.get("bricklink_url"),
            recognition_score=best.get("score"),
        )
        await state.clear()
        return

    await message.answer(
        "Найдено несколько вариантов. Выберите подходящий:",
        reply_markup=_candidate_picker_kb(candidates),
    )
    await state.clear()


@router.message(PhotoSearchState.waiting_photo)
async def on_photo_invalid(message: types.Message) -> None:
    await message.answer(
        "Нужно фото минифигурки. Отправьте снимок или нажмите «Отмена».",
        reply_markup=prompt_kb(),
    )


@router.callback_query(F.data.startswith("photo_pick:"))
async def cb_photo_pick(call: types.CallbackQuery) -> None:
    await call.answer()
    bricklink_id = call.data.split(":", 1)[1].lower()
    telegram_id = str(call.from_user.id)
    try:
        await call.message.edit_text("Загружаю карточку…")
    except Exception:
        pass
    await send_figure_card(
        call.bot,
        call.message.chat.id,
        telegram_id,
        bricklink_id,
    )
