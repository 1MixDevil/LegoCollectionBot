# handlers/settings.py
import httpx
from aiogram import Router, types
from inlineKeyBoards import main_kb
from config import AUTH_BASE, RUS_LABELS, TOGGLE_FIELDS

router = Router()

@router.callback_query(lambda cb: cb.data == "settings")
async def cb_settings(call: types.CallbackQuery):
    tg_id = call.from_user.id
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{AUTH_BASE}/users/get_user_settings/{tg_id}")
        settings = r.json()

    db_user_id = settings["user_id"]
    inline_keyboard = []
    for field in TOGGLE_FIELDS:
        curr = settings.get(field, False)
        label = RUS_LABELS[field]
        text = ("✅ " if curr else "❌ ") + label
        cb_data = f"settings:{db_user_id}:{field}:{int(not curr)}"
        inline_keyboard.append([types.InlineKeyboardButton(text=text, callback_data=cb_data)])

    inline_keyboard.append([types.InlineKeyboardButton(text="Закрыть", callback_data="settings:close")])
    kb = types.InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
    await call.message.answer("Настройки пользователя:", reply_markup=kb)
    await call.answer()

@router.callback_query(lambda cb: cb.data and cb.data.startswith("settings:"))
async def cb_settings_toggle(call: types.CallbackQuery):
    parts = call.data.split(":")
    if parts[1] == "close":
        await call.message.edit_text("Вы вернулись в главное меню.", reply_markup=main_kb)
        return await call.answer()

    _, db_user_id, field, new_val = parts
    new_value = bool(int(new_val))
    payload = {"user_id": int(db_user_id), field: new_value}
    async with httpx.AsyncClient() as client:
        await client.put(f"{AUTH_BASE}/users/update_user_settings/", json=payload)
        r = await client.get(f"{AUTH_BASE}/users/get_user_settings/{call.from_user.id}")
        settings = r.json()

    inline_keyboard = []
    for fld in TOGGLE_FIELDS:
        curr = settings.get(fld, False)
        label = RUS_LABELS[fld]
        text = ("✅ " if curr else "❌ ") + label
        cb_data = f"settings:{db_user_id}:{fld}:{int(not curr)}"
        inline_keyboard.append([types.InlineKeyboardButton(text=text, callback_data=cb_data)])
    inline_keyboard.append([types.InlineKeyboardButton(text="Закрыть", callback_data="settings:close")])
    kb = types.InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
    await call.message.edit_reply_markup(reply_markup=kb)
    action = "включено" if new_value else "выключено"
    await call.answer(f"{RUS_LABELS[field]} {action}")
    

@router.callback_query()
async def callback_fallback(callback: types.CallbackQuery):
    await callback.answer("Неизвестная кнопка", show_alert=True)
