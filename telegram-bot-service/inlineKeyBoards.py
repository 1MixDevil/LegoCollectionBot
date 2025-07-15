
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


def make_suggestions_kb(suggestions: list[dict]) -> InlineKeyboardMarkup:
    keyboard = []
    MAX_CALLBACK_LENGTH = 64
    PREFIX = "select_similar:"
    MAX_TEXT_LENGTH = 45  # лимит на текст кнопки

    for s in suggestions:
        serial = s["bricklink_id"]
        name = s["name"]

        callback_data = PREFIX + serial
        if len(callback_data.encode("utf-8")) > MAX_CALLBACK_LENGTH:
            # обрезаем serial, чтобы влез в callback_data
            max_serial_len = MAX_CALLBACK_LENGTH - len(PREFIX.encode("utf-8"))
            serial = serial.encode("utf-8")[:max_serial_len].decode("utf-8", errors="ignore")
            callback_data = PREFIX + serial

        # текст кнопки = name (serial), но name может быть длинным
        # надо оставить место под " (sw0001)" — включая пробел, скобки и сам артикул
        suffix = f" ({serial})"
        max_name_len = MAX_TEXT_LENGTH - len(suffix)
        display_name = name
        if len(name) > max_name_len:
            display_name = name[:max_name_len - 1] + "…"  # -1 под "…" (многоточие)

        display_text = f"{display_name}{suffix}"
        keyboard.append([InlineKeyboardButton(text=display_text, callback_data=callback_data)])

    keyboard.append([InlineKeyboardButton(text="Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
