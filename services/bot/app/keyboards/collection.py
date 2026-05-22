from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def collection_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📋 Список фигурок",
                    callback_data="collection_list:0",
                ),
                InlineKeyboardButton(
                    text="🔍 Поиск",
                    callback_data="collection_search",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔎 Карточка фигурки",
                    callback_data="collection_info",
                ),
                InlineKeyboardButton(
                    text="➖ Удалить",
                    callback_data="collection_remove",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🖼️ Коллаж tier‑лист",
                    callback_data="collection_tierlist",
                ),
                InlineKeyboardButton(
                    text="📊 Excel",
                    callback_data="collection_excel",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Обновить сводку",
                    callback_data="my_collection",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🗑️ Очистить всё",
                    callback_data="collection_clear_confirm",
                ),
            ],
            [InlineKeyboardButton(text="↩️ В главное меню", callback_data="cancel")],
        ]
    )


def collection_list_kb(page: int, total_pages: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if total_pages > 1:
        nav: list[InlineKeyboardButton] = []
        if page > 0:
            nav.append(
                InlineKeyboardButton(text="◀️", callback_data=f"collection_list:{page - 1}")
            )
        nav.append(
            InlineKeyboardButton(
                text=f"{page + 1}/{total_pages}",
                callback_data="collection_list:noop",
            )
        )
        if page < total_pages - 1:
            nav.append(
                InlineKeyboardButton(text="▶️", callback_data=f"collection_list:{page + 1}")
            )
        rows.append(nav)
    rows.append(
        [InlineKeyboardButton(text="↩️ К коллекции", callback_data="my_collection")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def collection_confirm_clear_kb(count: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"✅ Да, удалить все ({count})",
                    callback_data="collection_clear_yes",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="❌ Нет",
                    callback_data="my_collection",
                ),
            ],
        ]
    )
