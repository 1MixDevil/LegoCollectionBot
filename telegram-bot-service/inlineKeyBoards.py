from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# === Inline‑клавиатуры ===
main_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="/add",           callback_data="add")],
    [InlineKeyboardButton(text="/delete",        callback_data="delete")],
    [InlineKeyboardButton(text="/my_collection", callback_data="my_collection")],
    [InlineKeyboardButton(text="/settings",      callback_data="settings")],
    [InlineKeyboardButton(text="/info",          callback_data="info")],
    [InlineKeyboardButton(text="/update",        callback_data="update")],
    [InlineKeyboardButton(text="/create_tierlist",        callback_data="create_tierlist")],
])

confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Да, удалить", callback_data="confirm_yes")],
    [InlineKeyboardButton(text="Отмена",      callback_data="confirm_no")],
])

# Inline‑клавиатура для команды info
# Добавлена кнопка "❌ Отмена" под кнопкой удаления
# и разместим в последнем ряду

def make_info_kb(serial: str) -> InlineKeyboardMarkup:
    """
    Возвращает inline‑клавиатуру для info‑команды
    с кнопками: wishlist, buy, sell, add, delete, cancel
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Добавить в «Желаемое»",
                callback_data=f"info_action:wishlist:{serial}"
            ),
            InlineKeyboardButton(
                text="Купить",
                callback_data=f"info_action:buy:{serial}"
            ),
        ],
        [
            InlineKeyboardButton(
                text="Продать",
                callback_data=f"info_action:sell:{serial}"
            ),
            InlineKeyboardButton(
                text="Добавить в коллекцию",
                callback_data=f"info_action:add:{serial}"
            ),
        ],
        [
            InlineKeyboardButton(
                text="Удалить из коллекции",
                callback_data=f"info_action:delete:{serial}"
            )
        ],
        [
            InlineKeyboardButton(
                text="❌ Отмена",
                callback_data="cancel"
            )
        ]
    ])


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
            max_serial_len = MAX_CALLBACK_LENGTH - len(PREFIX.encode("utf-8"))
            serial = serial.encode("utf-8")[:max_serial_len].decode("utf-8", errors="ignore")
            callback_data = PREFIX + serial

        suffix = f" ({serial})"
        max_name_len = MAX_TEXT_LENGTH - len(suffix)
        display_name = name[:max_name_len - 1] + "…" if len(name) > max_name_len else name
        display_text = f"{display_name}{suffix}"
        keyboard.append([InlineKeyboardButton(text=display_text, callback_data=callback_data)])

    keyboard.append([InlineKeyboardButton(text="Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Функция навигационной клавиатуры (Назад + Отмена)
def nav_kb(back: str = None) -> InlineKeyboardMarkup:
    buttons = []
    if back:
        buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=back))
    buttons.append(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
    return InlineKeyboardMarkup(inline_keyboard=[buttons])

# Функция навигационной клавиатуры (Назад + Отмена)
def add_choice_kb() -> InlineKeyboardMarkup:
    """
    Создает inline-клавиатуру с двумя кнопками в первой строке и одной кнопкой во второй.
    """
    buttons_row1 = [
        InlineKeyboardButton(text="➕ Добавить одну фигурку", callback_data="add_solo_figure"),
        InlineKeyboardButton(text="➕➕ Добавить несколько фигурок", callback_data="add_few_figure"),
    ]
    buttons_row2 = [
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"),
    ]

    return InlineKeyboardMarkup(inline_keyboard=[buttons_row1, buttons_row2])


def collection_output_kb() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🗑️ Очистить коллекцию", callback_data="collection_clear")],
        [InlineKeyboardButton(text="🖼️ Экспортировать коллекцию в тир-лист", callback_data="collection_tierlist")],
        [InlineKeyboardButton(text="📊 Экспортировать коллекцию в Excel-таблицу", callback_data="collection_excel")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def tierlist_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Создать коллаж", callback_data="create_tierlist")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])
