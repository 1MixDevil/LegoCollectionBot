import logging

import httpx
from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from app.api.auth import get_user_by_telegram, list_users, set_user_role
from app.core.access import ensure_access, get_main_keyboard, get_user_role
from app.core.permissions import ROLE_LABELS
from app.keyboards.main import admin_panel_kb, admin_role_kb, admin_users_list_kb
from app.states.figures import AdminPanelState
from app.utils.message import answer_callback, safe_edit_or_answer

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


@router.callback_query(F.data == "admin_panel")
async def cb_admin_panel(call: types.CallbackQuery, state: FSMContext):
    if not await ensure_access(call, "admin_panel"):
        return
    await state.clear()
    await call.answer()
    await safe_edit_or_answer(
        call.message,
        "🛡 <b>Админ‑панель</b>\n\nУправление правами пользователей.",
        parse_mode="HTML",
        reply_markup=admin_panel_kb(),
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
        await message.answer("Нужен числовой ID, например <code>123456789</code>.", parse_mode="HTML")
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
