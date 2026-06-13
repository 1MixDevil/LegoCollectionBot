from aiogram import Router, types

from app.api.auth import get_user_settings, update_user_settings
from app.core.access import ensure_access, get_main_keyboard
from app.core.config import RUS_LABELS, SETTING_HINTS, TOGGLE_FIELDS
from app.services.menu import MAIN_MENU_HTML
from app.utils.message import safe_edit_or_answer

router = Router()


def _settings_text() -> str:
    lines = ["⚙ <b>Настройки</b>", "", "Нажмите пункт, чтобы включить или выключить:", ""]
    for field in TOGGLE_FIELDS:
        hint = SETTING_HINTS.get(field, "")
        if hint:
            lines.append(f"• <b>{RUS_LABELS[field]}</b> — {hint}")
    return "\n".join(lines)


def _settings_kb(settings: dict) -> types.InlineKeyboardMarkup:
    db_user_id = settings["user_id"]
    inline_keyboard = []
    for field in TOGGLE_FIELDS:
        curr = settings.get(field, False)
        label = RUS_LABELS[field]
        text = ("✅ " if curr else "❌ ") + label
        cb_data = f"settings:{db_user_id}:{field}:{int(not curr)}"
        inline_keyboard.append(
            [types.InlineKeyboardButton(text=text, callback_data=cb_data)]
        )
    inline_keyboard.append(
        [types.InlineKeyboardButton(text="↩️ В главное меню", callback_data="settings:close")]
    )
    return types.InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


@router.callback_query(lambda cb: cb.data == "settings")
async def cb_settings(call: types.CallbackQuery):
    if not await ensure_access(call, "settings"):
        return
    tg_id = str(call.from_user.id)
    settings = await get_user_settings(tg_id)
    await call.answer()
    await safe_edit_or_answer(
        call.message,
        _settings_text(),
        parse_mode="HTML",
        reply_markup=_settings_kb(settings),
    )


@router.callback_query(lambda cb: cb.data and cb.data.startswith("settings:"))
async def cb_settings_toggle(call: types.CallbackQuery):
    parts = call.data.split(":")
    if parts[1] == "close":
        await call.answer()
        kb = await get_main_keyboard(str(call.from_user.id))
        await safe_edit_or_answer(
            call.message,
            MAIN_MENU_HTML,
            parse_mode="HTML",
            reply_markup=kb,
        )
        return

    _, db_user_id, field, new_val = parts
    new_value = bool(int(new_val))
    await update_user_settings(int(db_user_id), **{field: new_value})

    settings = await get_user_settings(str(call.from_user.id))
    kb = _settings_kb(settings)
    await call.message.edit_reply_markup(reply_markup=kb)
    action = "включено" if new_value else "выключено"
    await call.answer(f"{RUS_LABELS[field]} {action}")
