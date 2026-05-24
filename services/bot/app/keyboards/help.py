from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def help_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✉️ Связаться с администратором",
                    callback_data="help_contact_admin",
                )
            ],
            [InlineKeyboardButton(text="↩️ В главное меню", callback_data="cancel")],
        ]
    )
