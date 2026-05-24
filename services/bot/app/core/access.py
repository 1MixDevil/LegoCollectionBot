import logging
from typing import Union

from aiogram.types import CallbackQuery, Message

from app.api.auth import get_user_by_telegram
from app.core.permissions import ROLE_MEMBER, can_access, normalize_role
from app.keyboards.main import build_main_kb

logger = logging.getLogger(__name__)

DENIED_TEXT = "Эта функция недоступна для вашего уровня доступа."


async def get_user_role(telegram_id: str) -> str:
    try:
        user = await get_user_by_telegram(telegram_id)
        return normalize_role(user.get("role"))
    except Exception:
        logger.exception("Failed to load role for %s", telegram_id)
        return ROLE_MEMBER


async def get_main_keyboard(telegram_id: str):
    role = await get_user_role(telegram_id)
    return build_main_kb(role)


async def ensure_access(
    event: Union[Message, CallbackQuery],
    feature: str,
) -> bool:
    user = event.from_user
    if not user:
        return False
    role = await get_user_role(str(user.id))
    if can_access(role, feature):
        return True
    if isinstance(event, CallbackQuery):
        await event.answer(DENIED_TEXT, show_alert=True)
    else:
        await event.answer(DENIED_TEXT)
    return False
