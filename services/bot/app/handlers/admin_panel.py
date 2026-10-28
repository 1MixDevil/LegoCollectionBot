import logging

import httpx
from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from app.api.auth import (
    get_collage_limits,
    get_collage_watermark,
    get_user_by_telegram,
    list_users,
    set_collage_limits,
    set_collage_watermark,
    set_user_role,
)
from app.core.access import ensure_access
from app.core.permissions import ROLE_LABELS
from app.keyboards.main import (
    admin_limits_kb,
    admin_panel_kb,
    admin_role_kb,
    admin_users_list_kb,
    admin_watermark_kb,
)
from app.services.collage_limits import (
    LIMIT_KEYS,
    LIMIT_LABELS,
    get_limits,
    invalidate_limits_cache,
)
from app.states.figures import AdminPanelState
from app.utils.message import safe_edit_or_answer

logger = logging.getLogger(__name__)
router = Router()


def _format_user_card(user: dict) -> str:
    role = user.get("role", "member")
    label = ROLE_LABELS.get(role, role)
    username = user.get("username") or "—"
    tid = user.get("telegram_username", "—")
    return (
        f"<b>Пользователь #{user['id']}</b>\n"
        f"Имя: {username}\n"
        f"Telegram ID: <code>{tid}</code>\n"
        f"Роль: <b>{label}</b>\n\n"
        "Выберите новую роль:"
    )


def _watermark_card(text: str) -> str:
    current = text.strip() if text else ""
    shown = f"<code>{current}</code>" if current else "<i>не задан</i>"
    return (
        "💧 <b>Водяной знак коллажей</b>\n\n"
        f"Текущий текст: {shown}\n\n"
        "Надпись полупрозрачно отображается на фоне всех тир‑листов и коллажей."
    )


def _limits_card(limits: dict) -> str:
    lines = ["⚙️ <b>Лимиты коллажей / tier‑листов</b>\n"]
    for key in LIMIT_KEYS:
        label = LIMIT_LABELS.get(key, key)
        lines.append(f"• {label}: <code>{limits.get(key, '—')}</code>")
    lines.append("\nНажмите параметр, чтобы изменить число.")
    return "\n".join(lines)


@router.callback_query(F.data == "admin_panel")
async def cb_admin_panel(call: types.CallbackQuery, state: FSMContext):
    if not await ensure_access(call, "admin_panel"):
        return
    await state.clear()
    await call.answer()
    await safe_edit_or_answer(
        call.message,
        "🛡 <b>Админ‑панель</b>\n\n"
        "Права пользователей, водяной знак и лимиты коллажей.",
        parse_mode="HTML",
        reply_markup=admin_panel_kb(),
    )


@router.callback_query(F.data == "admin_limits")
async def cb_admin_limits(call: types.CallbackQuery, state: FSMContext):
    if not await ensure_access(call, "admin_panel"):
        return
    await state.clear()
    await call.answer()
    try:
        limits = await get_collage_limits()
    except Exception:
        logger.exception("get_collage_limits failed")
        limits = get_limits(force_refresh=True)
    await safe_edit_or_answer(
        call.message,
        _limits_card(limits),
        parse_mode="HTML",
        reply_markup=admin_limits_kb(limits),
    )


@router.callback_query(F.data.startswith("admin_limit_edit:"))
async def cb_admin_limit_edit(call: types.CallbackQuery, state: FSMContext):
    if not await ensure_access(call, "admin_panel"):
        return
    key = call.data.split(":", 1)[1]
    if key not in LIMIT_KEYS:
        await call.answer("Неизвестный параметр.", show_alert=True)
        return
    await call.answer()
    await state.set_state(AdminPanelState.waiting_limit_value)
    await state.update_data(limit_key=key)
    label = LIMIT_LABELS.get(key, key)
    await call.message.answer(
        f"Введите новое значение для <b>{label}</b> "
        f"(целое число ≥ 1):",
        parse_mode="HTML",
    )


@router.message(AdminPanelState.waiting_limit_value)
async def on_admin_limit_value(message: types.Message, state: FSMContext):
    if not await ensure_access(message, "admin_panel"):
        return
    raw = (message.text or "").strip()
    if not raw.isdigit() or int(raw) < 1:
        await message.answer("Нужно целое число ≥ 1.")
        return
    data = await state.get_data()
    key = data.get("limit_key")
    if key not in LIMIT_KEYS:
        await state.clear()
        await message.answer("Сессия устарела. Откройте лимиты заново.")
        return
    value = int(raw)
    try:
        limits = await set_collage_limits(**{key: value})
    except Exception:
        logger.exception("set_collage_limits failed")
        await message.answer("Не удалось сохранить.")
        return
    invalidate_limits_cache()
    await state.clear()
    label = LIMIT_LABELS.get(key, key)
    await message.answer(
        f"✅ {label} = <code>{value}</code>\n\n" + _limits_card(limits),
        parse_mode="HTML",
        reply_markup=admin_limits_kb(limits),
    )


@router.callback_query(F.data == "admin_watermark")
async def cb_admin_watermark(call: types.CallbackQuery, state: FSMContext):
    if not await ensure_access(call, "admin_panel"):
        return
    await state.clear()
    await call.answer()
    try:
        text = await get_collage_watermark()
    except Exception:
        logger.exception("get_collage_watermark failed")
        await call.message.answer("Не удалось загрузить водяной знак.")
        return
    await safe_edit_or_answer(
        call.message,
        _watermark_card(text),
        parse_mode="HTML",
        reply_markup=admin_watermark_kb(),
    )


@router.callback_query(F.data == "admin_watermark_edit")
async def cb_admin_watermark_edit(call: types.CallbackQuery, state: FSMContext):
    if not await ensure_access(call, "admin_panel"):
        return
    await call.answer()
    await state.set_state(AdminPanelState.waiting_watermark_text)
    await call.message.answer(
        "Введите текст водяного знака (до 200 символов).\n"
        "Отправьте <code>-</code>, чтобы очистить.",
        parse_mode="HTML",
    )


@router.callback_query(F.data == "admin_watermark_clear")
async def cb_admin_watermark_clear(call: types.CallbackQuery, state: FSMContext):
    if not await ensure_access(call, "admin_panel"):
        return
    await state.clear()
    try:
        await set_collage_watermark("")
    except Exception:
        logger.exception("clear watermark failed")
        await call.answer("Ошибка сохранения.", show_alert=True)
        return
    await call.answer("Водяной знак очищен")
    await safe_edit_or_answer(
        call.message,
        _watermark_card(""),
        parse_mode="HTML",
        reply_markup=admin_watermark_kb(),
    )


@router.message(AdminPanelState.waiting_watermark_text)
async def on_admin_watermark_text(message: types.Message, state: FSMContext):
    if not await ensure_access(message, "admin_panel"):
        return
    raw = (message.text or "").strip()
    if not raw:
        await message.answer(
            "Пришлите текст или <code>-</code> для очистки.",
            parse_mode="HTML",
        )
        return
    text = "" if raw == "-" else raw[:200]
    try:
        saved = await set_collage_watermark(text)
    except Exception:
        logger.exception("set_collage_watermark failed")
        await message.answer("Не удалось сохранить водяной знак.")
        return
    await state.clear()
    await message.answer(
        _watermark_card(saved) + "\n\n✅ Сохранено.",
        parse_mode="HTML",
        reply_markup=admin_watermark_kb(),
    )


@router.callback_query(F.data == "admin_find_user")
async def cb_admin_find(call: types.CallbackQuery, state: FSMContext):
    if not await ensure_access(call, "admin_panel"):
        return
    await call.answer()
    await state.set_state(AdminPanelState.waiting_telegram_id)
    await call.message.answer(
        "Введите числовой <b>Telegram ID</b> пользователя:",
        parse_mode="HTML",
    )


@router.message(AdminPanelState.waiting_telegram_id)
async def on_admin_telegram_id(message: types.Message, state: FSMContext):
    if not await ensure_access(message, "admin_panel"):
        return
    tid = (message.text or "").strip()
    if not tid.isdigit():
        await message.answer(
            "Нужен числовой ID, например <code>123456789</code>.",
            parse_mode="HTML",
        )
        return
    try:
        user = await get_user_by_telegram(tid)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            await message.answer(
                "Пользователь не найден. Пусть откроет бота и отправит /start."
            )
            return
        await message.answer("Ошибка сервиса авторизации.")
        return
    await state.clear()
    await message.answer(
        _format_user_card(user),
        parse_mode="HTML",
        reply_markup=admin_role_kb(user["id"], user.get("role", "member")),
    )


@router.callback_query(F.data.startswith("admin_users:"))
async def cb_admin_users_list(call: types.CallbackQuery, state: FSMContext):
    if not await ensure_access(call, "admin_panel"):
        return
    await state.clear()
    await call.answer()
    page = int(call.data.split(":")[1])
    try:
        users = await list_users()
    except Exception:
        logger.exception("list_users failed")
        await call.message.answer("Не удалось загрузить список пользователей.")
        return
    if not users:
        await safe_edit_or_answer(
            call.message, "Пользователей пока нет.", reply_markup=admin_panel_kb()
        )
        return
    await safe_edit_or_answer(
        call.message,
        f"👥 Пользователи (стр. {page + 1}):",
        reply_markup=admin_users_list_kb(users, page),
    )


@router.callback_query(F.data.startswith("admin_pick:"))
async def cb_admin_pick_user(call: types.CallbackQuery, state: FSMContext):
    if not await ensure_access(call, "admin_panel"):
        return
    await call.answer()
    user_id = int(call.data.split(":")[1])
    try:
        users = await list_users()
    except Exception:
        await call.message.answer("Ошибка загрузки.")
        return
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        await call.message.answer("Пользователь не найден.")
        return
    await safe_edit_or_answer(
        call.message,
        _format_user_card(user),
        parse_mode="HTML",
        reply_markup=admin_role_kb(user_id, user.get("role", "member")),
    )


@router.callback_query(F.data.startswith("admin_role:"))
async def cb_admin_set_role(call: types.CallbackQuery, state: FSMContext):
    if not await ensure_access(call, "admin_panel"):
        return
    _, user_id_s, role = call.data.split(":", 2)
    user_id = int(user_id_s)
    try:
        user = await set_user_role(user_id, role)
    except Exception:
        logger.exception("set_user_role failed")
        await call.answer("Ошибка при смене роли.", show_alert=True)
        return
    label = ROLE_LABELS.get(role, role)
    await call.answer(f"Роль изменена: {label}")
    await safe_edit_or_answer(
        call.message,
        _format_user_card(user) + f"\n\n✅ Сохранено: <b>{label}</b>",
        parse_mode="HTML",
        reply_markup=admin_role_kb(user_id, role),
    )
