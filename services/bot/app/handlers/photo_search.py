"""Поиск минифигурки по фото (Brickognize)."""

from __future__ import annotations

import logging
from io import BytesIO

import httpx
from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.core.access import ensure_access, get_main_keyboard
from app.services.brickognize import format_top_candidates, search_by_image_bytes
from app.services.figure_display import send_figure_card_with_loading
from app.services.menu import send_main_menu
from app.states.figures import PhotoSearchState
logger = logging.getLogger(__name__)
router = Router()

PHOTO_SEARCH_HINT = (
    "📷 <b>Поиск по фото</b>\n\n"
    "Отправьте фото минифигурки (как изображение или .jpg/.png).\n"
    "После результата можно сразу прислать следующий снимок.\n\n"
    "<i>Выход — кнопка ниже.</i>"
)

PHOTO_SEARCH_CONTINUE = (
    "Можете отправить <b>ещё одно фото</b> — поиск продолжится.\n"
    "<i>Выход — «Выйти из поиска».</i>"
)


def photo_search_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="↩️ Выйти из поиска",
                    callback_data="photo_search_exit",
                )
            ],
        ]
    )


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
    builder.button(text="↩️ Выйти из поиска", callback_data="photo_search_exit")
    builder.adjust(1)
    return builder.as_markup()


async def _enter_photo_search(
    target: types.Message,
    state: FSMContext,
    *,
    edit: bool = False,
) -> None:
    await state.set_state(PhotoSearchState.waiting_photo)
    kb = photo_search_kb()
    if edit and target.text:
        try:
            await target.edit_text(PHOTO_SEARCH_HINT, parse_mode="HTML", reply_markup=kb)
        except Exception:
            await target.answer(PHOTO_SEARCH_HINT, parse_mode="HTML", reply_markup=kb)
    else:
        await target.answer(PHOTO_SEARCH_HINT, parse_mode="HTML", reply_markup=kb)


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


async def _process_photo_search(
    message: types.Message,
    state: FSMContext,
) -> None:
    telegram_id = str(message.from_user.id)
    kb = photo_search_kb()
    status = await message.answer("🔎 Ищу на Brickognize…", reply_markup=kb)

    try:
        image_bytes, filename = await _download_telegram_image(message)
    except ValueError as exc:
        if str(exc) == "not_image":
            text = "Отправьте изображение (фото или .jpg/.png)."
        else:
            text = "Пришлите фото минифигурки."
        await status.edit_text(text, reply_markup=kb)
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
            "Попробуйте другой снимок.",
            reply_markup=kb,
        )
        return
    except Exception:
        logger.exception("Brickognize error")
        await status.edit_text(
            "Не удалось распознать фото. Попробуйте другой ракурс или освещение.",
            reply_markup=kb,
        )
        return

    await status.delete()

    if not candidates:
        await message.answer(
            "Ничего похожего на минифигурку не найдено.\n"
            "Попробуйте крупнее, на однотонном фоне.",
            parse_mode="HTML",
            reply_markup=kb,
        )
        return

    await state.set_state(PhotoSearchState.waiting_photo)

    if len(candidates) == 1 or (candidates[0].get("score") or 0) >= 0.85:
        best = candidates[0]
        await send_figure_card_with_loading(
            message.bot,
            message.chat.id,
            telegram_id,
            best["bricklink_id"],
            name=best.get("name"),
            bricklink_url=best.get("bricklink_url"),
            recognition_score=best.get("score"),
        )
        await message.answer(PHOTO_SEARCH_CONTINUE, parse_mode="HTML", reply_markup=kb)
        return

    await state.set_state(PhotoSearchState.waiting_photo)
    await message.answer(
        "Найдено несколько вариантов. Выберите подходящий:",
        reply_markup=_candidate_picker_kb(candidates),
    )


@router.callback_query(F.data == "photo_search")
async def cb_photo_search_start(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await ensure_access(call, "photo_search"):
        return
    await call.answer()
    await _enter_photo_search(call.message, state, edit=bool(call.message.text))


@router.callback_query(F.data == "photo_search_exit")
async def cb_photo_search_exit(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await ensure_access(call, "photo_search"):
        return
    await state.clear()
    await call.answer("Выход из поиска по фото")
    await send_main_menu(call.message, str(call.from_user.id))


@router.message(PhotoSearchState.waiting_photo, F.photo | F.document)
async def on_photo_received(message: types.Message, state: FSMContext) -> None:
    await _process_photo_search(message, state)


@router.message(PhotoSearchState.waiting_photo)
async def on_photo_invalid(message: types.Message) -> None:
    if message.text and message.text.strip().startswith("/"):
        return
    await message.answer(
        "Нужно фото минифигурки. Отправьте снимок или нажмите «Выйти из поиска».",
        reply_markup=photo_search_kb(),
    )


@router.callback_query(F.data.startswith("photo_pick:"))
async def cb_photo_pick(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await ensure_access(call, "photo_search"):
        return
    await call.answer()
    bricklink_id = call.data.split(":", 1)[1].lower()
    telegram_id = str(call.from_user.id)
    try:
        await call.message.edit_text("⏳ Открываю карточку…")
    except Exception:
        pass
    await send_figure_card_with_loading(
        call.bot,
        call.message.chat.id,
        telegram_id,
        bricklink_id,
    )
    await state.set_state(PhotoSearchState.waiting_photo)
    await call.message.answer(PHOTO_SEARCH_CONTINUE, parse_mode="HTML", reply_markup=photo_search_kb())
