from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.keyboards.nav_labels import BACK_LABEL, MAIN_MENU_LABEL


def help_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✉️ Связаться с администратором",
                    callback_data="help_contact_admin",
                )
            ],
            [InlineKeyboardButton(text=MAIN_MENU_LABEL, callback_data="cancel")],
        ]
    )


def help_contact_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BACK_LABEL, callback_data="help")],
            [InlineKeyboardButton(text=MAIN_MENU_LABEL, callback_data="cancel")],
        ]
    )
