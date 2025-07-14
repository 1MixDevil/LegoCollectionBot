
from aiogram import types
from aiogram.types import BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# === Inline‑клавиатуры ===
main_kb = types.InlineKeyboardMarkup(inline_keyboard=[
    [types.InlineKeyboardButton(text="/add",           callback_data="add")],
    [types.InlineKeyboardButton(text="/delete",        callback_data="delete")],
    [types.InlineKeyboardButton(text="/my_collection", callback_data="my_collection")],
    [types.InlineKeyboardButton(text="/settings",      callback_data="settings")],
    [types.InlineKeyboardButton(text="/info",          callback_data="info")],
    [types.InlineKeyboardButton(text="/update",        callback_data="update")],
])

confirm_kb = types.InlineKeyboardMarkup(inline_keyboard=[
    [types.InlineKeyboardButton(text="Да, удалить", callback_data="confirm_yes")],
    [types.InlineKeyboardButton(text="Отмена",      callback_data="confirm_no")],
])

# в начале файла, после main_kb и confirm_kb
def make_info_kb(serial: str) -> types.InlineKeyboardMarkup:
    """
    Возвращает inline‑клавиатуру для info‑команды
    с кнопками: wishlist, buy, sell, add, delete
    """
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text="Добавить в «Желаемое»",
                callback_data=f"info_action:wishlist:{serial}"
            ),
            types.InlineKeyboardButton(
                text="Купить",
                callback_data=f"info_action:buy:{serial}"
            ),
        ],
        [
            types.InlineKeyboardButton(
                text="Продать",
                callback_data=f"info_action:sell:{serial}"
            ),
            types.InlineKeyboardButton(
                text="Добавить в коллекцию",
                callback_data=f"info_action:add:{serial}"
            ),
        ],
        [
            types.InlineKeyboardButton(
                text="Удалить из коллекции",
                callback_data=f"info_action:delete:{serial}"
            )
        ]
    ])

def nav_kb(back: str = None) -> InlineKeyboardMarkup:
    """
    Собирает Inline-клавиатуру:
     - всегда кнопка «Отмена» с callback_data='cancel'
     - если указан back, добавляется кнопка «Назад» с callback_data=back
    """
    buttons = []
    if back:
        buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=back))
    buttons.append(InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    return InlineKeyboardMarkup(inline_keyboard=[buttons])