"""Список желаний пользователя."""

from __future__ import annotations

import logging
import re

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile
from httpx import HTTPStatusError

from app.api.collection import (
    create_wishlist_item,
    delete_wishlist_item,
    list_user_wishlist,
    update_wishlist_item,
)
from app.core.access import ensure_access
from app.keyboards.wishlist import (
    wishlist_edit_field_kb,
    wishlist_item_kb,
    wishlist_list_kb,
    wishlist_menu_kb,
    wishlist_skip_kb,
)
from app.states.figures import WishlistState
from app.services.wishlist_image import fetch_wishlist_image
from app.utils.message import safe_edit_or_answer

logger = logging.getLogger(__name__)
router = Router()

URL_RE = re.compile(r"^https?://", re.I)
SKIP_WORDS = frozenset({"-", "пропустить", "skip", "null"})


def _format_money(value) -> str:
    if value is None:
        return "—"
    try:
        num = float(value)
        if num == int(num):
            return f"{int(num)} ₽"
        return f"{num:.2f} ₽"
    except (TypeError, ValueError):
        return str(value)


def _format_item(item: dict) -> str:
    lines = [
        f"⭐ <b>{item.get('title') or '—'}</b>",
    ]
    bid = item.get("bricklink_id")
    if bid:
        lines.append(f"• Артикул: <code>{bid}</code>")
    price = item.get("price_estimate")
    if price is not None:
        lines.append(f"• Примерная цена: <b>{_format_money(price)}</b>")
    desc = (item.get("description") or "").strip()
    if desc:
        short = desc[:400] + ("…" if len(desc) > 400 else "")
        lines.append(f"• Описание: {short}")
    url = (item.get("product_url") or "").strip()
    if url:
        lines.append(f'• <a href="{url}">Ссылка на товар</a>')
    return "\n".join(lines)


def _parse_price(raw: str) -> float | None:
    text = raw.strip().replace(",", ".")
    if not text or text.lower() in SKIP_WORDS:
        return None
    return float(text)


def _parse_url(raw: str) -> str | None:
    text = raw.strip()
    if not text or text.lower() in SKIP_WORDS:
        return None
    if not URL_RE.match(text):
        raise ValueError("bad_url")
    return text[:500]


async def _show_wishlist_item(
    message: types.Message,
    item: dict,
    item_id: int,
) -> None:
    """Карточка желания: фото (если нашли) + подпись."""
    caption = _format_item(item)
    kb = wishlist_item_kb(item_id)
    loading = await message.answer("⏳ Открываем…")
    try:
        image_bytes, filename = await fetch_wishlist_image(item)
        if image_bytes:
            photo = BufferedInputFile(image_bytes, filename=filename)
            await message.answer_photo(
                photo=photo,
                caption=caption,
                parse_mode="HTML",
                reply_markup=kb,
            )
            return
    except Exception:
        logger.debug("wishlist photo send failed", exc_info=True)
    finally:
        try:
            await loading.delete()
        except Exception:
            pass

    await message.answer(
        caption,
        parse_mode="HTML",
        reply_markup=kb,
        disable_web_page_preview=True,
    )


async def _show_menu(target: types.Message, *, edit: bool = False) -> None:
    text = (
        "💫 <b>Желания</b>\n\n"
        "Здесь можно хранить наборы и фигурки, которые хотите купить.\n"
        "Для каждой позиции: название, описание, цена и ссылка (Avito и т.п.)."
    )
    kb = wishlist_menu_kb()
    if edit and target.text:
        await safe_edit_or_answer(target, text, parse_mode="HTML", reply_markup=kb)
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data == "wishlist")
async def cb_wishlist_menu(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await ensure_access(call, "wishlist"):
        return
    await state.clear()
    await call.answer()
    await _show_menu(call.message, edit=bool(call.message.text))


@router.callback_query(F.data.startswith("wishlist_list:"))
async def cb_wishlist_list(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await ensure_access(call, "wishlist"):
        return
    await state.clear()
    page = int(call.data.split(":", 1)[1])
    await call.answer()
    telegram_id = str(call.from_user.id)
    try:
        items = await list_user_wishlist(telegram_id)
    except Exception:
        logger.exception("list wishlist failed")
        await call.message.answer("Не удалось загрузить список желаний.")
        return

    if not items:
        await safe_edit_or_answer(
            call.message,
            "💫 Список желаний пуст.\n\nНажмите «➕ Добавить».",
            reply_markup=wishlist_menu_kb(),
        )
        return

    text = f"💫 <b>Желания</b> — {len(items)} шт.\n\nВыберите позицию:"
    await safe_edit_or_answer(
        call.message,
        text,
        parse_mode="HTML",
        reply_markup=wishlist_list_kb(items, page),
    )


@router.callback_query(F.data.startswith("wishlist_view:"))
async def cb_wishlist_view(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await ensure_access(call, "wishlist"):
        return
    await state.clear()
    item_id = int(call.data.split(":", 1)[1])
    await call.answer("Открываем…")
    telegram_id = str(call.from_user.id)
    try:
        items = await list_user_wishlist(telegram_id)
    except Exception:
        await call.message.answer("Ошибка загрузки.")
        return
    item = next((x for x in items if x["id"] == item_id), None)
    if not item:
        await call.message.answer("Позиция не найдена.")
        return
    await _show_wishlist_item(call.message, item, item_id)


@router.callback_query(F.data == "wishlist_add")
async def cb_wishlist_add(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await ensure_access(call, "wishlist"):
        return
    await call.answer()
    await state.clear()
    await state.set_state(WishlistState.waiting_title)
    await state.update_data(wishlist_draft={})
    await call.message.answer(
        "➕ <b>Новое желание</b>\n\n"
        "Введите <b>название</b> (набор, фигурка, набор BrickLink и т.п.):",
        parse_mode="HTML",
        reply_markup=wishlist_skip_kb("wishlist_cancel_add"),
    )


@router.callback_query(F.data == "wishlist_cancel_add")
async def cb_wishlist_cancel_add(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await ensure_access(call, "wishlist"):
        return
    await state.clear()
    await call.answer("Отменено")
    await _show_menu(call.message)


async def start_wishlist_from_figure(
    message: types.Message,
    state: FSMContext,
    *,
    bricklink_id: str,
    title: str,
) -> None:
    """Быстрое добавление из карточки фигурки."""
    await state.set_state(WishlistState.waiting_description)
    await state.update_data(
        wishlist_draft={
            "title": title[:200],
            "bricklink_id": bricklink_id.lower(),
        }
    )
    await message.answer(
        f"💫 Добавляем в желания: <b>{title}</b>\n"
        f"Артикул: <code>{bricklink_id}</code>\n\n"
        "Введите <b>описание</b> (или «-» чтобы пропустить):",
        parse_mode="HTML",
        reply_markup=wishlist_skip_kb(),
    )


@router.message(WishlistState.waiting_title)
async def on_wishlist_title(message: types.Message, state: FSMContext) -> None:
    title = (message.text or "").strip()
    if not title:
        await message.answer("Нужно название.", reply_markup=wishlist_skip_kb("wishlist_cancel_add"))
        return
    if len(title) > 200:
        await message.answer("Слишком длинное название (макс. 200 символов).")
        return
    await state.update_data(wishlist_draft={"title": title})
    await state.set_state(WishlistState.waiting_description)
    await message.answer(
        "Введите <b>описание</b> (заметки, состояние, комплектность…)\n"
        "Или «-» / «Пропустить».",
        parse_mode="HTML",
        reply_markup=wishlist_skip_kb(),
    )


@router.message(WishlistState.waiting_description)
async def on_wishlist_description(message: types.Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    data = await state.get_data()
    draft = dict(data.get("wishlist_draft") or {})
    draft["description"] = None if raw.lower() in SKIP_WORDS else raw[:1000]
    await state.update_data(wishlist_draft=draft)
    await state.set_state(WishlistState.waiting_price)
    await message.answer(
        "Укажите <b>примерную цену</b> (число, ₽).\n"
        "Или «-» / «Пропустить».",
        parse_mode="HTML",
        reply_markup=wishlist_skip_kb(),
    )


@router.callback_query(F.data == "wishlist_skip")
async def cb_wishlist_skip(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await ensure_access(call, "wishlist"):
        return
    await call.answer()
    current = await state.get_state()
    if current == WishlistState.waiting_description.state:
        data = await state.get_data()
        draft = dict(data.get("wishlist_draft") or {})
        draft["description"] = None
        await state.update_data(wishlist_draft=draft)
        await state.set_state(WishlistState.waiting_price)
        await call.message.answer(
            "Укажите <b>примерную цену</b> (число).\nИли «-» / «Пропустить».",
            parse_mode="HTML",
            reply_markup=wishlist_skip_kb(),
        )
    elif current == WishlistState.waiting_price.state:
        data = await state.get_data()
        draft = dict(data.get("wishlist_draft") or {})
        draft["price_estimate"] = None
        await state.update_data(wishlist_draft=draft)
        await state.set_state(WishlistState.waiting_url)
        await call.message.answer(
            "Пришлите <b>ссылку</b> на товар (https://…).\n"
            "Или «-» / «Пропустить».",
            parse_mode="HTML",
            reply_markup=wishlist_skip_kb(),
        )
    elif current == WishlistState.waiting_url.state:
        await _save_draft(call.message, state, product_url=None)


@router.message(WishlistState.waiting_price)
async def on_wishlist_price(message: types.Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    data = await state.get_data()
    draft = dict(data.get("wishlist_draft") or {})
    try:
        draft["price_estimate"] = _parse_price(raw)
    except ValueError:
        await message.answer("Нужно число, например <code>1500</code>.", parse_mode="HTML")
        return
    await state.update_data(wishlist_draft=draft)
    await state.set_state(WishlistState.waiting_url)
    await message.answer(
        "Пришлите <b>ссылку</b> на товар (Avito, Ozon, BrickLink…).\n"
        "Или «-» / «Пропустить».",
        parse_mode="HTML",
        reply_markup=wishlist_skip_kb(),
    )


@router.message(WishlistState.waiting_url)
async def on_wishlist_url(message: types.Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    try:
        url = _parse_url(raw)
    except ValueError:
        await message.answer(
            "Нужна ссылка, начинающаяся с <code>http://</code> или <code>https://</code>.",
            parse_mode="HTML",
        )
        return
    await _save_draft(message, state, product_url=url)


async def _save_draft(
    message: types.Message,
    state: FSMContext,
    *,
    product_url: str | None,
) -> None:
    data = await state.get_data()
    draft = dict(data.get("wishlist_draft") or {})
    title = (draft.get("title") or "").strip()
    if not title:
        await state.clear()
        await message.answer("Не указано название. Начните заново из «Желания».")
        return
    draft["product_url"] = product_url
    telegram_id = str(message.from_user.id)
    try:
        item = await create_wishlist_item(
            telegram_id,
            title=title,
            description=draft.get("description"),
            price_estimate=draft.get("price_estimate"),
            product_url=draft.get("product_url"),
            bricklink_id=draft.get("bricklink_id"),
        )
    except HTTPStatusError:
        await message.answer("Не удалось сохранить. Попробуйте позже.")
        return
    except Exception:
        logger.exception("create wishlist item")
        await message.answer("Ошибка сохранения.")
        return

    await state.clear()
    await _show_wishlist_item(message, item, item["id"])


@router.callback_query(F.data.startswith("wishlist_delete:"))
async def cb_wishlist_delete(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await ensure_access(call, "wishlist"):
        return
    item_id = int(call.data.split(":", 1)[1])
    await call.answer()
    try:
        await delete_wishlist_item(str(call.from_user.id), item_id)
    except HTTPStatusError:
        await call.message.answer("Не удалось удалить.")
        return
    await call.message.answer(
        "🗑 Позиция удалена из желаний.",
        reply_markup=wishlist_menu_kb(),
    )


@router.callback_query(F.data.startswith("wishlist_edit:"))
async def cb_wishlist_edit(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await ensure_access(call, "wishlist"):
        return
    item_id = int(call.data.split(":", 1)[1])
    await call.answer()
    await state.clear()
    await safe_edit_or_answer(
        call.message,
        "Что изменить?",
        reply_markup=wishlist_edit_field_kb(item_id),
    )


@router.callback_query(F.data.startswith("wishlist_edit_field:"))
async def cb_wishlist_edit_field(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await ensure_access(call, "wishlist"):
        return
    _, field, item_id_s = call.data.split(":", 2)
    item_id = int(item_id_s)
    await call.answer()
    await state.set_state(WishlistState.waiting_edit_value)
    await state.update_data(wishlist_edit_id=item_id, wishlist_edit_field=field)
    prompts = {
        "title": "Новое название:",
        "description": "Новое описание (или «-» чтобы очистить):",
        "price": "Новая цена (или «-» чтобы очистить):",
        "url": "Новая ссылка https://… (или «-» чтобы очистить):",
    }
    await call.message.answer(prompts.get(field, "Введите значение:"))


@router.message(WishlistState.waiting_edit_value)
async def on_wishlist_edit_value(message: types.Message, state: FSMContext) -> None:
    data = await state.get_data()
    item_id = data.get("wishlist_edit_id")
    field = data.get("wishlist_edit_field")
    if not item_id or not field:
        await state.clear()
        return
    raw = (message.text or "").strip()
    payload: dict = {}
    try:
        if field == "title":
            if not raw:
                await message.answer("Название не может быть пустым.")
                return
            payload["title"] = raw[:200]
        elif field == "description":
            payload["description"] = None if raw.lower() in SKIP_WORDS else raw[:1000]
        elif field == "price":
            payload["price_estimate"] = _parse_price(raw)
        elif field == "url":
            payload["product_url"] = _parse_url(raw)
    except ValueError:
        if field == "url":
            await message.answer("Нужна ссылка http(s)://…")
        else:
            await message.answer("Некорректное значение.")
        return

    try:
        item = await update_wishlist_item(str(message.from_user.id), int(item_id), **payload)
    except HTTPStatusError:
        await message.answer("Не удалось сохранить.")
        return

    await state.clear()
    await message.answer("✅ Сохранено.")
    await _show_wishlist_item(message, item, item["id"])
