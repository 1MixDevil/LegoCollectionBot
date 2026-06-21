"""Список желаний пользователя."""

from __future__ import annotations

import logging
import re

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile
from httpx import HTTPStatusError

from app.api.auth import (
    check_wishlist_public,
    get_wishlist_owner_by_token,
    get_wishlist_share_settings,
    list_public_wishlist_owners,
    set_wishlist_public,
)
from app.api.collection import (
    create_wishlist_item,
    delete_wishlist_item,
    list_user_wishlist,
    list_wishlist_by_user_id,
    update_wishlist_item,
)
from app.core.access import ensure_access
from app.keyboards.wishlist import (
    wishlist_edit_field_kb,
    wishlist_item_kb,
    wishlist_list_kb,
    wishlist_menu_kb,
    wishlist_public_item_kb,
    wishlist_public_list_kb,
    wishlist_public_users_kb,
    wishlist_skip_kb,
)
from app.states.figures import WishlistState
from app.services.wishlist_image import fetch_wishlist_image
from app.utils.message import safe_edit_or_answer

logger = logging.getLogger(__name__)
router = Router()

URL_RE = re.compile(r"^https?://", re.I)
SKIP_WORDS = frozenset({"-", "пропустить", "skip", "null"})
WISHLIST_START_PREFIX = "wl_"


def _display_name(username: str | None, user_id: int) -> str:
    return (username or f"Пользователь #{user_id}").strip()


async def _load_share_settings(telegram_id: str) -> dict:
    try:
        return await get_wishlist_share_settings(telegram_id)
    except Exception:
        logger.exception("wishlist share settings failed")
        return {"wishlist_public": False, "wishlist_share_token": None}


async def _menu_kb(telegram_id: str):
    settings = await _load_share_settings(telegram_id)
    return wishlist_menu_kb(is_public=bool(settings.get("wishlist_public")))


def _menu_text(is_public: bool) -> str:
    visibility = (
        "🔓 <b>Список открытый</b> — можно поделиться ссылкой."
        if is_public
        else "🔒 <b>Список закрытый</b> — видите только вы."
    )
    return (
        "💫 <b>Желания</b>\n\n"
        f"{visibility}\n\n"
        "Храните наборы и фигурки, которые хотите купить: "
        "название, описание, цена и ссылка."
    )


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
    *,
    owner_id: int | None = None,
    readonly: bool = False,
) -> None:
    """Карточка желания: фото (если нашли) + подпись."""
    caption = _format_item(item)
    if readonly and owner_id is not None:
        kb = wishlist_public_item_kb(owner_id)
    else:
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


async def _show_menu(
    target: types.Message,
    telegram_id: str,
    *,
    edit: bool = False,
) -> None:
    settings = await _load_share_settings(telegram_id)
    is_public = bool(settings.get("wishlist_public"))
    text = _menu_text(is_public)
    kb = wishlist_menu_kb(is_public=is_public)
    if edit and target.text:
        await safe_edit_or_answer(target, text, parse_mode="HTML", reply_markup=kb)
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=kb)


async def _load_public_owners(exclude_user_id: int) -> list[dict]:
    try:
        owners = await list_public_wishlist_owners()
    except Exception:
        logger.exception("list public wishlist owners failed")
        return []

    result: list[dict] = []
    for owner in owners:
        owner_id = int(owner["user_id"])
        if owner_id == exclude_user_id:
            continue
        try:
            items = await list_wishlist_by_user_id(owner_id)
        except Exception:
            logger.debug("wishlist load failed for owner %s", owner_id, exc_info=True)
            continue
        if not items:
            continue
        result.append(
            {
                "user_id": owner_id,
                "username": owner.get("username"),
                "count": len(items),
            }
        )
    return result


async def open_shared_wishlist_from_start(
    message: types.Message,
    state: FSMContext,
    token: str,
) -> bool:
    """Deep link ?start=wl_{token}. Возвращает True, если обработано."""
    if not await ensure_access(message, "wishlist"):
        return True
    token = token.strip()
    if not token:
        return False
    await state.clear()
    try:
        owner = await get_wishlist_owner_by_token(token)
    except Exception:
        await message.answer(
            "Ссылка недействительна или список желаний снова закрыт.",
        )
        return True

    owner_id = int(owner["user_id"])
    owner_name = _display_name(owner.get("username"), owner_id)
    try:
        items = await list_wishlist_by_user_id(owner_id)
    except Exception:
        await message.answer("Не удалось загрузить список желаний.")
        return True

    if not items:
        await message.answer(f"У {owner_name} пока пустой список желаний.")
        return True

    text = (
        f"💫 <b>Желания</b> — {_display_name(owner.get('username'), owner_id)}\n"
        f"{len(items)} поз.\n\nВыберите:"
    )
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=wishlist_public_list_kb(items, owner_id, 0),
    )
    return True


@router.callback_query(F.data == "wishlist")
async def cb_wishlist_menu(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await ensure_access(call, "wishlist"):
        return
    await state.clear()
    await call.answer()
    telegram_id = str(call.from_user.id)
    await _show_menu(call.message, telegram_id, edit=bool(call.message.text))


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
            reply_markup=await _menu_kb(telegram_id),
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


@router.callback_query(F.data == "wishlist_toggle_public")
async def cb_wishlist_toggle_public(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await ensure_access(call, "wishlist"):
        return
    await state.clear()
    telegram_id = str(call.from_user.id)
    settings = await _load_share_settings(telegram_id)
    new_public = not bool(settings.get("wishlist_public"))
    try:
        settings = await set_wishlist_public(telegram_id, new_public)
    except Exception:
        await call.answer("Не удалось изменить режим.", show_alert=True)
        return
    await call.answer("Открытый список" if new_public else "Закрытый список")
    await _show_menu(call.message, telegram_id, edit=bool(call.message.text))


@router.callback_query(F.data == "wishlist_share_link")
async def cb_wishlist_share_link(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await ensure_access(call, "wishlist"):
        return
    await call.answer()
    telegram_id = str(call.from_user.id)
    settings = await _load_share_settings(telegram_id)
    if not settings.get("wishlist_public"):
        await call.message.answer("Сначала сделайте список открытым.")
        return
    token = settings.get("wishlist_share_token")
    if not token:
        try:
            settings = await set_wishlist_public(telegram_id, True)
            token = settings.get("wishlist_share_token")
        except Exception:
            await call.message.answer("Не удалось получить ссылку.")
            return
    bot_user = await call.bot.get_me()
    link = f"https://t.me/{bot_user.username}?start={WISHLIST_START_PREFIX}{token}"
    await call.message.answer(
        "🔗 <b>Ссылка на ваш список желаний</b>\n\n"
        f"<code>{link}</code>\n\n"
        "Пока список открытый — любой с этой ссылкой может его просмотреть.",
        parse_mode="HTML",
        reply_markup=await _menu_kb(telegram_id),
    )


@router.callback_query(F.data.startswith("wishlist_public_users:"))
async def cb_wishlist_public_users(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await ensure_access(call, "wishlist"):
        return
    await state.clear()
    page = int(call.data.split(":", 1)[1])
    await call.answer()
    telegram_id = str(call.from_user.id)
    try:
        me_id = int((await get_wishlist_share_settings(telegram_id))["user_id"])
    except Exception:
        me_id = -1
    owners = await _load_public_owners(me_id)
    if not owners:
        await safe_edit_or_answer(
            call.message,
            "🌍 <b>Чужие желания</b>\n\n"
            "Пока никто не открыл свой список или все списки пустые.\n"
            "Откройте свой — другие смогут увидеть его здесь.",
            parse_mode="HTML",
            reply_markup=await _menu_kb(telegram_id),
        )
        return
    await safe_edit_or_answer(
        call.message,
        "🌍 <b>Чужие желания</b>\n\nВыберите человека:",
        parse_mode="HTML",
        reply_markup=wishlist_public_users_kb(owners, page),
    )


@router.callback_query(F.data.startswith("wishlist_public_user:"))
async def cb_wishlist_public_user(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await ensure_access(call, "wishlist"):
        return
    await state.clear()
    _, owner_id_s, page_s = call.data.split(":", 2)
    owner_id = int(owner_id_s)
    page = int(page_s)
    await call.answer()
    if not await check_wishlist_public(owner_id):
        await call.message.answer("Этот список желаний снова закрыт.")
        return
    try:
        items = await list_wishlist_by_user_id(owner_id)
        owners = await list_public_wishlist_owners()
        owner_info = next((o for o in owners if int(o["user_id"]) == owner_id), None)
    except Exception:
        await call.message.answer("Не удалось загрузить список.")
        return
    if not items:
        await call.message.answer("Список пуст.")
        return
    name = _display_name(
        owner_info.get("username") if owner_info else None,
        owner_id,
    )
    await safe_edit_or_answer(
        call.message,
        f"💫 <b>Желания</b> — {name}\n{len(items)} поз.\n\nВыберите:",
        parse_mode="HTML",
        reply_markup=wishlist_public_list_kb(items, owner_id, page),
    )


@router.callback_query(F.data.startswith("wishlist_public_view:"))
async def cb_wishlist_public_view(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await ensure_access(call, "wishlist"):
        return
    await state.clear()
    _, owner_id_s, item_id_s = call.data.split(":", 2)
    owner_id = int(owner_id_s)
    item_id = int(item_id_s)
    await call.answer("Открываем…")
    if not await check_wishlist_public(owner_id):
        await call.message.answer("Этот список желаний снова закрыт.")
        return
    try:
        items = await list_wishlist_by_user_id(owner_id)
    except Exception:
        await call.message.answer("Ошибка загрузки.")
        return
    item = next((x for x in items if x["id"] == item_id), None)
    if not item:
        await call.message.answer("Позиция не найдена.")
        return
    await _show_wishlist_item(
        call.message,
        item,
        item_id,
        owner_id=owner_id,
        readonly=True,
    )


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
    await _show_menu(call.message, str(call.from_user.id))


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
    telegram_id = str(call.from_user.id)
    await call.message.answer(
        "🗑 Позиция удалена из желаний.",
        reply_markup=await _menu_kb(telegram_id),
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
