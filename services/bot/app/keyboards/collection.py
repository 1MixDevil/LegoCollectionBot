from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.keyboards.main import make_info_kb
from app.services.collection_stats import PICK_PAGE_SIZE, figure_button_label


def collection_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📋 Список фигурок",
                    callback_data="collection_browse:0",
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
                    text="🗑️ Очистить всё",
                    callback_data="collection_clear_confirm",
                ),
            ],
            [InlineKeyboardButton(text="↩️ В главное меню", callback_data="cancel")],
        ]
    )


def collection_browse_kb(
    entries: list[dict],
    page: int,
    *,
    page_size: int = PICK_PAGE_SIZE,
) -> InlineKeyboardMarkup:
    total = len(entries)
    pages = max(1, (total + page_size - 1) // page_size) if total else 1
    page = max(0, min(page, pages - 1))
    chunk = entries[page * page_size : (page + 1) * page_size]

    rows: list[list[InlineKeyboardButton]] = []
    for entry in chunk:
        bid = entry.get("bricklink_id", "")
        rows.append(
            [
                InlineKeyboardButton(
                    text=figure_button_label(entry),
                    callback_data=f"coll_pick:{bid}",
                )
            ]
        )

    if pages > 1:
        nav: list[InlineKeyboardButton] = []
        if page > 0:
            nav.append(
                InlineKeyboardButton(
                    text="◀️",
                    callback_data=f"collection_browse:{page - 1}",
                )
            )
        nav.append(
            InlineKeyboardButton(
                text=f"{page + 1}/{pages}",
                callback_data="collection_browse:noop",
            )
        )
        if page < pages - 1:
            nav.append(
                InlineKeyboardButton(
                    text="▶️",
                    callback_data=f"collection_browse:{page + 1}",
                )
            )
        rows.append(nav)

    rows.append(
        [
            InlineKeyboardButton(
                text="🔍 Поиск в списке",
                callback_data="collection_find",
            ),
            InlineKeyboardButton(
                text="📋 Все фигурки",
                callback_data="collection_browse_all",
            ),
        ]
    )
    rows.append(
        [InlineKeyboardButton(text="↩️ К коллекции", callback_data="my_collection")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def collection_figure_kb(bricklink_id: str) -> InlineKeyboardMarkup:
    """Карточка из списка коллекции: действия + возврат к списку."""
    base = make_info_kb(bricklink_id)
    rows = [list(row) for row in base.inline_keyboard]
    rows.insert(
        -1,
        [
            InlineKeyboardButton(
                text="↩️ К списку",
                callback_data="collection_browse_resume",
            )
        ],
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
