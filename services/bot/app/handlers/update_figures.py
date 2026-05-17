import logging

from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from app.api.collection import update_figures_list
from app.keyboards.main import main_kb, nav_kb
from app.states.figures import UpdateFigures

logger = logging.getLogger(__name__)
router = Router()

PROMPT = (
    "Введите префикс серии из каталога BrickLink.\n"
    "Например: <code>sw</code> (Star Wars), <code>hp</code> (Harry Potter).\n\n"
    "Бот скачает новые минифигурки этой серии в общий каталог БД."
)


def format_update_result(article: str, result: dict) -> str:
    status = result.get("status", "unknown")
    added = result.get("added", 0)
    scanned = result.get("scanned_found", 0)
    checked = result.get("checked_base")
    reasons = result.get("miss_reasons") or {}
    reasons_text = ", ".join(f"{k}: {v}" for k, v in reasons.items()) or "—"
    message = result.get("message", "")

    source = result.get("source", "")
    source_line = f"\nИсточник: {source}" if source else ""

    if status == "locked":
        age = result.get("lock_age_sec", "?")
        return (
            f"⏳ Серия <code>{article}</code>: обновление уже запущено "
            f"(lock {age} сек назад).\n\n"
            f"{message or 'Подождите минуту и повторите /update.'}"
        )

    if added > 0:
        return (
            f"✅ Серия <code>{article}</code>: добавлено <b>{added}</b> фигурок.\n"
            f"Загружено из каталога: {scanned}.{source_line}"
        )

    if scanned > 0:
        return (
            f"ℹ️ Серия <code>{article}</code>: новых записей нет "
            f"(все {scanned} уже в каталоге)."
        )

    if status == "blocked":
        return (
            f"🚫 Серия <code>{article}</code>: BrickLink недоступен.\n"
            f"Переключите CATALOG_DATA_SOURCE=rebrickable в .env\n\n"
            f"{message}"
        )

    return (
        f"⚠️ Серия <code>{article}</code>: ничего не найдено.\n"
        f"Проверено базовых номеров: {checked or '?'}.\n"
        f"Причины: {reasons_text}\n\n"
        f"{message or 'Смотри логи: docker compose logs collection-service --tail 50'}"
    )


async def ask_article(message: types.Message, state: FSMContext) -> None:
    await message.answer(PROMPT, parse_mode="HTML", reply_markup=nav_kb())
    await state.set_state(UpdateFigures.waiting_article)


@router.message(Command("update"))
async def cmd_update(message: types.Message, state: FSMContext):
    await ask_article(message, state)


@router.callback_query(lambda cb: cb.data == "update")
async def cb_update(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    await ask_article(call.message, state)


@router.message(UpdateFigures.waiting_article)
async def get_article(message: types.Message, state: FSMContext):
    article = message.text.strip().lower()
    if not article:
        await message.answer("Введите префикс, например sw.", reply_markup=nav_kb())
        return

    status_msg = await message.answer(
        f"⏳ Загружаю каталог <code>{article}</code> с BrickLink…\n"
        "Обычно 10–60 сек.\n"
        "Логи: <code>docker compose logs -f collection-service</code>",
        parse_mode="HTML",
    )

    try:
        logger.info("Запрос update для серии %s", article)
        result = await update_figures_list(article=article)
        logger.info("Ответ update: %s", result)
        text = format_update_result(article, result)
        await status_msg.edit_text(text, parse_mode="HTML", reply_markup=main_kb)
    except Exception as e:
        logger.exception("Ошибка update")
        await status_msg.edit_text(
            f"❌ Ошибка обновления: {e}",
            reply_markup=main_kb,
        )
    finally:
        await state.clear()
