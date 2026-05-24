from aiogram import types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.core.permissions import ROLE_LABELS, can_access


def _row(*buttons: InlineKeyboardButton | None) -> list[InlineKeyboardButton]:
    return [b for b in buttons if b is not None]


def build_main_kb(role: str) -> InlineKeyboardMarkup:
    """Главное меню с учётом роли."""
    rows: list[list[InlineKeyboardButton]] = []

    row1 = _row(
        InlineKeyboardButton(text="📦 Моя коллекция", callback_data="my_collection")
        if can_access(role, "my_collection")
        else None,
        InlineKeyboardButton(text="➕ Добавить", callback_data="add")
        if can_access(role, "add")
        else None,
    )
    if row1:
        rows.append(row1)

    row2 = _row(
        InlineKeyboardButton(text="ℹ️ Карточка фигурки", callback_data="figure_card")
        if can_access(role, "figure_card")
        else None,
        InlineKeyboardButton(text="🔎 Поиск по фото", callback_data="photo_search")
        if can_access(role, "photo_search")
        else None,
    )
    if row2:
        rows.append(row2)

    # «Желаемое» скрыто до реализации функции

    if can_access(role, "tierlist"):
        rows.append(
            [InlineKeyboardButton(text="🏷 Tier‑лист", callback_data="create_tierlist")]
        )

    row3 = _row(
        InlineKeyboardButton(text="🔄 Обновить каталог", callback_data="update")
        if can_access(role, "update_catalog")
        else None,
        InlineKeyboardButton(text="⚙ Настройки", callback_data="settings")
        if can_access(role, "settings")
        else None,
    )
    if row3:
        rows.append(row3)

    if can_access(role, "marketplace"):
        rows.append(
            [InlineKeyboardButton(text="🛒 Торговля", callback_data="marketplace")]
        )

    if can_access(role, "help"):
        rows.append([InlineKeyboardButton(text="❓ Помощь", callback_data="help")])

    if can_access(role, "admin_panel"):
        rows.append(
            [InlineKeyboardButton(text="🛡 Админ‑панель", callback_data="admin_panel")]
        )

    return InlineKeyboardMarkup(inline_keyboard=rows)


# Обратная совместимость (полное меню админа)
main_kb = build_main_kb("admin")


def tierlist_mode_kb(role: str) -> InlineKeyboardMarkup:
    """Выбор способа заполнения tier‑листа."""
    rows: list[list[InlineKeyboardButton]] = []
    if can_access(role, "tierlist_serials"):
        rows.append(
            [
                InlineKeyboardButton(
                    text="📦 По артикулам",
                    callback_data="tierlist_mode:serials",
                )
            ]
        )
    if can_access(role, "tierlist_keyword"):
        rows.append(
            [
                InlineKeyboardButton(
                    text="🔤 По названию",
                    callback_data="tierlist_mode:keyword",
                )
            ]
        )
    if can_access(role, "tierlist_all"):
        rows.append(
            [
                InlineKeyboardButton(
                    text="🌐 Вся серия",
                    callback_data="tierlist_mode:all",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="↩️ Назад", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔍 Найти по Telegram ID",
                    callback_data="admin_find_user",
                )
            ],
            [
                InlineKeyboardButton(
                    text="👥 Список пользователей",
                    callback_data="admin_users:0",
                )
            ],
            [InlineKeyboardButton(text="↩️ Назад", callback_data="cancel")],
        ]
    )


def admin_role_kb(user_id: int, current_role: str) -> InlineKeyboardMarkup:
    buttons = []
    for role in ("member", "premium", "admin"):
        label = ROLE_LABELS[role]
        prefix = "✓ " if role == current_role else ""
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"{prefix}{label}",
                    callback_data=f"admin_role:{user_id}:{role}",
                )
            ]
        )
    buttons.append(
        [InlineKeyboardButton(text="↩️ В админ‑панель", callback_data="admin_panel")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_users_list_kb(
    users: list[dict],
    page: int,
    page_size: int = 8,
) -> InlineKeyboardMarkup:
    start = page * page_size
    chunk = users[start : start + page_size]
    rows: list[list[InlineKeyboardButton]] = []
    for u in chunk:
        tid = u.get("telegram_username", "?")
        name = u.get("username") or "—"
        role = u.get("role", "member")
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{name} ({tid}) · {ROLE_LABELS.get(role, role)}",
                    callback_data=f"admin_pick:{u['id']}",
                )
            ]
        )
    nav: list[InlineKeyboardButton] = []
    if start > 0:
        nav.append(
            InlineKeyboardButton(text="◀️", callback_data=f"admin_users:{page - 1}")
        )
    if start + page_size < len(users):
        nav.append(
            InlineKeyboardButton(text="▶️", callback_data=f"admin_users:{page + 1}")
        )
    if nav:
        rows.append(nav)
    rows.append(
        [InlineKeyboardButton(text="↩️ В админ‑панель", callback_data="admin_panel")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)

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


def prompt_kb(back: str | None = None, skip: str | None = None) -> InlineKeyboardMarkup:
    """Навигация + опциональная кнопка «Пропустить»."""
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    if back:
        row.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=back))
    row.append(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
    rows.append(row)
    if skip:
        rows.append([InlineKeyboardButton(text="⏭ Пропустить", callback_data=skip)])
    return InlineKeyboardMarkup(inline_keyboard=rows)

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


