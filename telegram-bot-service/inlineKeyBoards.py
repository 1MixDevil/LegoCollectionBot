from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# === Inline‑клавиатуры ===

# 1. Главное меню
main_kb = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="📦 Моя коллекция", callback_data="my_collection"),
        InlineKeyboardButton(text="➕ Добавить",       callback_data="add"),
    ],
    [
        InlineKeyboardButton(text="📋 Желаемое",       callback_data="wishlist"),
        InlineKeyboardButton(text="🏷 Tier‑лист",      callback_data="create_tierlist"),
    ],
    [
        InlineKeyboardButton(text="🛒 Торговля",        callback_data="marketplace"),
        InlineKeyboardButton(text="⚙ Настройки",       callback_data="settings"),
    ],
    [
        InlineKeyboardButton(text="❓ Помощь",          callback_data="help"),
    ],
])

# 2. Подменю «Моя коллекция»
collection_kb = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="🗒 Показать список", callback_data="my_collection"),
        InlineKeyboardButton(text="🗑️ Очистить всё",    callback_data="collection_clear"),
    ],
    [
        InlineKeyboardButton(text="📊 Экспорт Excel",   callback_data="collection_excel"),
    ],
    [
        InlineKeyboardButton(text="↩️ Назад",            callback_data="cancel"),
    ],
])

# 3. Подменю «Добавить»
add_kb = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="➕ Одна фигурка",       callback_data="add_solo_figure"),
        InlineKeyboardButton(text="➕➕ Несколько фигурок", callback_data="add_few_figure"),
    ],
    [
        InlineKeyboardButton(text="↩️ Назад",              callback_data="cancel"),
    ],
])

# 4. Подменю «Желаемое»
wishlist_kb = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="📋 Показать список", callback_data="wishlist"),
        InlineKeyboardButton(text="➕ Добавить",         callback_data="info_action:wishlist"),
    ],
    [
        InlineKeyboardButton(text="🔒 Приватный/Открытый", callback_data="toggle_wishlist_visibility"),
    ],
    [
        InlineKeyboardButton(text="↩️ Назад",              callback_data="cancel"),
    ],
])

# 5. Подменю «Tier‑лист»
tierlist_kb = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="📑 Мои списки",      callback_data="list_tierlists"),
        InlineKeyboardButton(text="➕ Создать новый",   callback_data="create_tierlist"),
    ],
    [
        InlineKeyboardButton(text="↩️ Назад",           callback_data="cancel"),
    ],
])

# 5.1. Подменю конкретного tier‑листа
def tierlist_item_kb(tierlist_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🖼 Показать коллаж",    callback_data=f"show_collage:{tierlist_id}"),
            InlineKeyboardButton(text="➕ Добавить элемент",  callback_data=f"add_to_tierlist:{tierlist_id}"),
        ],
        [
            InlineKeyboardButton(text="➖ Удалить элемент",   callback_data=f"remove_from_tierlist:{tierlist_id}"),
            InlineKeyboardButton(text="📤 Экспорт в Excel",   callback_data=f"export_tierlist_excel:{tierlist_id}"),
        ],
        [
            InlineKeyboardButton(text="🔤 Переименовать",     callback_data=f"rename_tierlist:{tierlist_id}"),
            InlineKeyboardButton(text="↩️ Назад",             callback_data="list_tierlists"),
        ],
    ])

# 6. Подменю «Торговля»
marketplace_kb = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="🛍 Мои объявления", callback_data="my_listings"),
        InlineKeyboardButton(text="🔎 Все лоты",       callback_data="browse_listings"),
    ],
    [
        InlineKeyboardButton(text="↩️ Назад",           callback_data="cancel"),
    ],
])

# 7. Подменю «Настройки»
settings_kb = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="🔗 Привязать BrickLink", callback_data="bind_bricklink"),
    ],
    [
        InlineKeyboardButton(text="🔔 Уведомления ON/OFF",   callback_data="toggle_notifications"),
    ],
    [
        InlineKeyboardButton(text="⭐ Premium",              callback_data="premium"),
    ],
    [
        InlineKeyboardButton(text="↩️ Назад",                callback_data="cancel"),
    ],
])

# 8. Подменю «Помощь»
help_kb = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="📖 FAQ",              callback_data="faq"),
        InlineKeyboardButton(text="✉️ Обратная связь",   callback_data="feedback"),
    ],
    [
        InlineKeyboardButton(text="↩️ Назад",             callback_data="cancel"),
    ],
])

# === Подтверждения ===
confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Да, удалить", callback_data="confirm_yes")],
    [InlineKeyboardButton(text="Отмена",      callback_data="confirm_no")],
])

# Навигационная клавиатура (Назад + Отмена)
def nav_kb(back: str = None) -> InlineKeyboardMarkup:
    buttons = []
    if back:
        buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=back))
    buttons.append(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
    return InlineKeyboardMarkup(inline_keyboard=[buttons])

# === Существующие функции оставлены без изменений ===

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
        [InlineKeyboardButton(text="🖼️ Экспортировать коллекцию в тир‑лист", callback_data="collection_tierlist")],
        [InlineKeyboardButton(text="📊 Экспортировать коллекцию в Excel‑таблицу", callback_data="collection_excel")],
        [InlineKeyboardButton(text="↩️ Отмена", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def tierlist_kb_old() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Создать коллаж", callback_data="create_tierlist")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])


