import logging

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from app.api.auth import list_users
from app.content.guide import USER_GUIDE_HTML
from app.core.access import ensure_access, get_main_keyboard
from app.core.admin_ids import permanent_admin_ids
from app.keyboards.help import help_contact_kb, help_menu_kb
from app.states.figures import HelpState
from app.utils.message import safe_edit_or_answer

logger = logging.getLogger(__name__)
router = Router()


async def _admin_telegram_ids() -> list[str]:
    ids: set[str] = set(permanent_admin_ids())
    try:
        users = await list_users()
        for user in users:
            if user.get("role") == "admin":
                tid = str(user.get("telegram_username", "")).strip()
                if tid.isdigit():
                    ids.add(tid)
    except Exception:
        logger.exception("Failed to load admin list")
    return sorted(ids)


def _format_user_header(message: types.Message) -> str:
    user = message.from_user
    name = user.full_name if user else "—"
    uid = user.id if user else "—"
    username = f"@{user.username}" if user and user.username else "—"
    return (
        "📩 <b>Сообщение пользователя</b>\n"
        f"Имя: {name}\n"
        f"Telegram ID: <code>{uid}</code>\n"
        f"Username: {username}\n"
        "────────────\n"
    )


@router.callback_query(F.data == "help")
async def cb_help(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await ensure_access(call, "help"):
        return
    await state.clear()
    await call.answer()
    await safe_edit_or_answer(
        call.message,
        USER_GUIDE_HTML,
        parse_mode="HTML",
        reply_markup=help_menu_kb(),
    )


@router.callback_query(F.data == "help_contact_admin")
async def cb_help_contact_admin(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await ensure_access(call, "help"):
        return
    await call.answer()
    await state.set_state(HelpState.waiting_admin_message)
    await call.message.answer(
        "✉️ <b>Связаться с администратором</b>\n\n"
        "Опишите проблему или какую серию фигурок нужно добавить в каталог.\n"
        "Отправьте одним сообщением — бот перешлёт его всем администраторам.\n\n"
        "Если передумали — «Назад» или «В главное меню».",
        parse_mode="HTML",
        reply_markup=help_contact_kb(),
    )


@router.message(HelpState.waiting_admin_message, F.text)
async def on_admin_message_text(message: types.Message, state: FSMContext) -> None:
    if not message.text or message.text.startswith("/"):
        await message.answer(
            "Отправьте текст сообщения или нажмите «В главное меню».",
            reply_markup=help_contact_kb(),
        )
        return

    admin_ids = await _admin_telegram_ids()
    if not admin_ids:
        await message.answer(
            "Сейчас нет доступных администраторов. Попробуйте позже.",
            reply_markup=await get_main_keyboard(str(message.from_user.id)),
        )
        await state.clear()
        return

    body = _format_user_header(message) + message.text
    sent = 0
    for admin_id in admin_ids:
        if admin_id == str(message.from_user.id):
            continue
        try:
            await message.bot.send_message(
                int(admin_id),
                body,
                parse_mode="HTML",
            )
            sent += 1
        except Exception:
            logger.warning("Could not deliver admin message to %s", admin_id)

    await state.clear()
    kb = await get_main_keyboard(str(message.from_user.id))
    if sent:
        await message.answer(
            "✅ Сообщение отправлено администратору. Ответ придёт вам в личку от админа.",
            reply_markup=kb,
        )
    else:
        await message.answer(
            "Не удалось доставить сообщение. Попробуйте позже.",
            reply_markup=kb,
        )


@router.message(HelpState.waiting_admin_message)
async def on_admin_message_invalid(message: types.Message) -> None:
    await message.answer(
        "Нужен текст. Фото и файлы пока не поддерживаются — опишите словами.",
        reply_markup=help_contact_kb(),
    )
