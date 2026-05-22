from aiogram import Router, types

from app.api.auth import get_user_settings, update_user_settings
from app.core.access import ensure_access, get_main_keyboard
from app.core.config import RUS_LABELS, TOGGLE_FIELDS
from app.utils.message import safe_edit_or_answer

router = Router()


@router.callback_query(lambda cb: cb.data == "settings")
async def cb_settings(call: types.CallbackQuery):
    if not await ensure_access(call, "settings"):
        return
    tg_id = str(call.from_user.id)
    settings = await get_user_settings(tg_id)

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
        [types.InlineKeyboardButton(text="Закрыть", callback_data="settings:close")]
    )
    kb = types.InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
    await call.message.answer("Настройки пользователя:", reply_markup=kb)
    await call.answer()


@router.callback_query(lambda cb: cb.data and cb.data.startswith("settings:"))
async def cb_settings_toggle(call: types.CallbackQuery):
    parts = call.data.split(":")
    if parts[1] == "close":
        await call.answer()
        kb = await get_main_keyboard(str(call.from_user.id))
        await safe_edit_or_answer(
            call.message,
            "Вы вернулись в главное меню.",
            reply_markup=kb,
        )
        return

    _, db_user_id, field, new_val = parts
    new_value = bool(int(new_val))
    await update_user_settings(int(db_user_id), **{field: new_value})

    settings = await get_user_settings(str(call.from_user.id))
    inline_keyboard = []
    for fld in TOGGLE_FIELDS:
        curr = settings.get(fld, False)
        label = RUS_LABELS[fld]
        text = ("✅ " if curr else "❌ ") + label
        cb_data = f"settings:{db_user_id}:{fld}:{int(not curr)}"
        inline_keyboard.append(
            [types.InlineKeyboardButton(text=text, callback_data=cb_data)]
        )
    inline_keyboard.append(
        [types.InlineKeyboardButton(text="Закрыть", callback_data="settings:close")]
    )
    kb = types.InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
    await call.message.edit_reply_markup(reply_markup=kb)
    action = "включено" if new_value else "выключено"
    await call.answer(f"{RUS_LABELS[field]} {action}")
