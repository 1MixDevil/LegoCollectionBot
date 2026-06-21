from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.keyboards.nav_labels import BACK_LABEL, MAIN_MENU_LABEL

WISHLIST_PAGE_SIZE = 6


def wishlist_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📋 Список желаний",
                    callback_data="wishlist_list:0",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="➕ Добавить",
                    callback_data="wishlist_add",
                ),
            ],
            [InlineKeyboardButton(text=MAIN_MENU_LABEL, callback_data="cancel")],
        ]
    )


def wishlist_list_kb(items: list[dict], page: int) -> InlineKeyboardMarkup:
    total = len(items)
    pages = max(1, (total + WISHLIST_PAGE_SIZE - 1) // WISHLIST_PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    chunk = items[page * WISHLIST_PAGE_SIZE : (page + 1) * WISHLIST_PAGE_SIZE]

    rows: list[list[InlineKeyboardButton]] = []
    for item in chunk:
        label = (item.get("title") or "—")[:42]
        rows.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"wishlist_view:{item['id']}",
                )
            ]
        )

    if pages > 1:
        nav: list[InlineKeyboardButton] = []
        if page > 0:
            nav.append(
                InlineKeyboardButton(
                    text="◀️",
                    callback_data=f"wishlist_list:{page - 1}",
                )
            )
        nav.append(
            InlineKeyboardButton(
                text=f"{page + 1}/{pages}",
                callback_data=f"wishlist_list:{page}",
            )
        )
        if page < pages - 1:
            nav.append(
                InlineKeyboardButton(
                    text="▶️",
                    callback_data=f"wishlist_list:{page + 1}",
                )
            )
        rows.append(nav)

    rows.append(
        [
            InlineKeyboardButton(text="➕ Добавить", callback_data="wishlist_add"),
            InlineKeyboardButton(text=BACK_LABEL, callback_data="wishlist"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def wishlist_item_kb(item_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Изменить",
                    callback_data=f"wishlist_edit:{item_id}",
                ),
                InlineKeyboardButton(
                    text="🗑 Удалить",
                    callback_data=f"wishlist_delete:{item_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="↩️ К списку",
                    callback_data="wishlist_list:0",
                ),
            ],
        ]
    )


def wishlist_edit_field_kb(item_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📝 Название",
                    callback_data=f"wishlist_edit_field:title:{item_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="💬 Описание",
                    callback_data=f"wishlist_edit_field:description:{item_id}",
                ),
                InlineKeyboardButton(
                    text="💰 Цена",
                    callback_data=f"wishlist_edit_field:price:{item_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔗 Ссылка",
                    callback_data=f"wishlist_edit_field:url:{item_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="↩️ Назад",
                    callback_data=f"wishlist_view:{item_id}",
                ),
            ],
        ]
    )


def wishlist_skip_kb(skip: str = "wishlist_skip") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Пропустить", callback_data=skip)],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="wishlist")],
        ]
    )
