import logging
import os
import re

from aiogram import Bot, Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile

from app.api.collection import fetch_all_catalog_serials, search_figures_by_keyword
from app.core.access import ensure_access, get_main_keyboard, get_user_role
from app.core.config import MAX_SERIALS_PER_REQUEST
from app.core.permissions import can_access
from app.keyboards.main import nav_kb, tierlist_mode_kb
from app.services.collage import StarWarsCollageGenerator
from app.states.figures import CreateTierList

logger = logging.getLogger(__name__)
router = Router()
TMP_DIR = os.getenv("TMP_DIR", "/tmp")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 100))
TIERLIST_KEYWORD_MAX = int(os.getenv("TIERLIST_KEYWORD_MAX", "500"))
PREFIX_URL = os.getenv(
    "COLL_PREFIX_URL", "https://img.bricklink.com/ItemImage/MN/0"
)

# Артикул BrickLink: sw0001a, lor129, hp0023
SERIAL_RE = re.compile(r"^[a-z][a-z0-9]*\d+[a-z]?$", re.IGNORECASE)

# Вся серия (без __ — Telegram ломает подчёркивания в Markdown)
SERIES_COMMAND = "series"


def parse_series_prefix(text: str) -> str | None:
    """series → sw, series:lor → lor."""
    low = text.strip().lower()
    if low == SERIES_COMMAND:
        return "sw"
    prefix = f"{SERIES_COMMAND}:"
    if low.startswith(prefix):
        return text.split(":", 1)[1].strip().lower() or "sw"
    return None


def parse_tierlist_input(text: str) -> tuple[str, object] | None:
    """
    Режимы: all (префикс), serials (список артикулов), keyword (фраза в названии).
    """
    text = text.strip()
    if not text:
        return None

    series_prefix = parse_series_prefix(text)
    if series_prefix is not None:
        return ("all", series_prefix)

    if re.search(r"[,;]", text):
        tokens = [t.strip() for t in re.split(r"[,;]+", text) if t.strip()]
        if tokens and all(SERIAL_RE.match(t) for t in tokens):
            return ("serials", tokens)
        return ("keyword", re.sub(r"[,;]+", " ", text).strip())

    if SERIAL_RE.match(text):
        return ("serials", [text])

    return ("keyword", text)


PARSE_MODE_FEATURE = {
    "serials": "tierlist_serials",
    "keyword": "tierlist_keyword",
    "all": "tierlist_all",
}

MODE_HINTS = {
    "serials": (
        "Введите <b>артикулы</b> через запятую или «;»:\n"
        "<code>sw0001a, sw0002</code>"
    ),
    "keyword": (
        "Введите <b>ключевые слова</b> для поиска по названию:\n"
        "<code>Clone Trooper</code>"
    ),
    "all": (
        "Введите серию целиком:\n"
        "<code>series</code> (Star Wars) или <code>series:lor</code>"
    ),
}


def parse_serials_only(text: str) -> tuple[str, list[str]] | None:
    text = text.strip()
    if not text:
        return None
    if re.search(r"[,;]", text):
        tokens = [t.strip() for t in re.split(r"[,;]+", text) if t.strip()]
        if tokens and all(SERIAL_RE.match(t) for t in tokens):
            return ("serials", [t.lower() for t in tokens])
        return None
    if SERIAL_RE.match(text):
        return ("serials", [text.lower()])
    return None


@router.callback_query(lambda cb: cb.data == "create_tierlist")
async def cb_start_tierlist(call: types.CallbackQuery, state: FSMContext):
    if not await ensure_access(call, "tierlist"):
        return
    await call.answer()
    await call.message.answer(
        "Введите название вашего Tier List.\n"
        "Если не нужно — отправьте `null`.",
        parse_mode="Markdown",
    )
    await state.set_state(CreateTierList.waiting_name_list)


@router.message(CreateTierList.waiting_name_list)
async def on_name_entered(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if name.lower() == "null":
        name = None
    await state.update_data(title=name)
    role = await get_user_role(str(message.from_user.id))

    has_choice = can_access(role, "tierlist_keyword") or can_access(role, "tierlist_all")
    if has_choice:
        await message.answer(
            "Как собрать tier‑лист?",
            reply_markup=tierlist_mode_kb(role),
        )
        await state.set_state(CreateTierList.waiting_mode)
        return

    await state.update_data(tierlist_mode="serials")
    await message.answer(
        MODE_HINTS["serials"]
        + f"\n\nЛимит: до {MAX_SERIALS_PER_REQUEST} артикулов.",
        parse_mode="HTML",
        reply_markup=nav_kb(),
    )
    await state.set_state(CreateTierList.waiting_serials)


@router.callback_query(lambda cb: cb.data and cb.data.startswith("tierlist_mode:"))
async def cb_tierlist_mode(call: types.CallbackQuery, state: FSMContext):
    mode = call.data.split(":", 1)[1]
    feature = PARSE_MODE_FEATURE.get(mode)
    if not feature or not await ensure_access(call, feature):
        return
    await call.answer()
    await state.update_data(tierlist_mode=mode)
    hint = MODE_HINTS.get(mode, "")
    if mode == "serials":
        hint += f"\n\nЛимит: до {MAX_SERIALS_PER_REQUEST} артикулов."
    elif mode == "keyword":
        hint += (
            f"\n\nЛимит: до {TIERLIST_KEYWORD_MAX} "
            f"(если больше {BATCH_SIZE} — несколько файлов)."
        )
    await call.message.answer(hint, parse_mode="HTML", reply_markup=nav_kb())
    await state.set_state(CreateTierList.waiting_serials)


@router.message(CreateTierList.waiting_serials)
async def on_serials_entered(message: types.Message, state: FSMContext):
    if not message.text:
        await message.answer("Введите текстом.", reply_markup=nav_kb())
        return

    data = await state.get_data()
    title = data.get("title") or ""
    telegram_id = str(message.from_user.id)
    role = await get_user_role(telegram_id)
    forced_mode = data.get("tierlist_mode")

    if forced_mode == "serials":
        parsed = parse_serials_only(message.text)
        if not parsed:
            await message.answer(
                "Только артикулы BrickLink (например <code>sw0001a</code>).",
                parse_mode="HTML",
                reply_markup=nav_kb(),
            )
            return
    elif forced_mode == "keyword":
        kw = message.text.strip()
        if not kw:
            await message.answer("Введите ключевые слова.", reply_markup=nav_kb())
            return
        parsed = ("keyword", kw)
    elif forced_mode == "all":
        series_prefix = parse_series_prefix(message.text)
        if series_prefix is None:
            await message.answer(
                "Используйте <code>series</code> (Star Wars) или <code>series:lor</code>.",
                parse_mode="HTML",
                reply_markup=nav_kb(),
            )
            return
        parsed = ("all", series_prefix)
    else:
        parsed = parse_tierlist_input(message.text)
        if not parsed:
            await message.answer("Пустой ввод.", reply_markup=nav_kb())
            return

    mode, payload = parsed
    feature = PARSE_MODE_FEATURE.get(mode)
    if feature and not can_access(role, feature):
        await message.answer(
            "Для вашего уровня доступен только режим «по артикулам».",
            reply_markup=nav_kb(),
        )
        return

    if mode == "serials":
        serials = [s.lower() for s in payload]
        if len(serials) > MAX_SERIALS_PER_REQUEST:
            await message.answer(
                f"❗️ Максимум {MAX_SERIALS_PER_REQUEST} артикулов за раз.",
                reply_markup=nav_kb(),
            )
            return

    if mode == "all":
        await _handle_all_mode(message, str(payload), title, telegram_id)
    elif mode == "keyword":
        await _handle_keyword_mode(message, str(payload), title)
    else:
        await _handle_serials_mode(message, list(payload), title, telegram_id)

    await state.clear()


async def _main_kb(telegram_id: str):
    return await get_main_keyboard(telegram_id)


async def _handle_keyword_mode(
    message: types.Message,
    keyword: str,
    title: str,
) -> None:
    telegram_id = str(message.from_user.id)
    kb = await _main_kb(telegram_id)
    await message.answer(
        f"🔎 Ищу в каталоге: <i>{keyword}</i>…",
        parse_mode="HTML",
    )
    try:
        found = await search_figures_by_keyword(keyword, limit=TIERLIST_KEYWORD_MAX)
    except Exception:
        logger.exception("search figures by keyword")
        await message.answer(
            "Ошибка поиска в каталоге. Загрузите серию через «🔄 Обновить каталог» "
            "(админ) или напишите в «❓ Помощь».",
            reply_markup=kb,
        )
        return

    if not found:
        await message.answer(
            f"По запросу «{keyword}» ничего не найдено в каталоге БД.\n"
            "Проверьте написание. Серию в каталог можно добавить через "
            "«🔄 Обновить каталог» или «❓ Помощь».",
            reply_markup=kb,
        )
        return

    records = [
        {"bricklink_id": row["bricklink_id"], "name": row["name"]}
        for row in found
    ]
    await message.answer(
        f"Найдено <b>{len(records)}</b> фигурок. Собираю коллаж…",
        parse_mode="HTML",
    )
    await _send_collage_batches(
        message,
        records,
        title=title,
        telegram_id=telegram_id,
        caption_label=f"поиск: {keyword}",
    )


async def _handle_serials_mode(
    message: types.Message,
    serials: list[str],
    title: str,
    telegram_id: str,
) -> None:
    await message.answer("Генерируем тир-лист…")
    records = [{"bricklink_id": s} for s in serials]
    await _generate_and_send_collage(
        records, telegram_id, title, message, attach_menu=True
    )


async def _handle_all_mode(
    message: types.Message,
    prefix: str,
    title: str,
    telegram_id: str,
) -> None:
    await message.answer(
        f"Загружаю все <code>{prefix}</code> из каталога…",
        parse_mode="HTML",
    )
    kb = await _main_kb(telegram_id)
    try:
        serials = await fetch_all_catalog_serials(prefix=prefix)
    except Exception:
        logger.exception("fetch all catalog")
        await message.answer("Ошибка загрузки каталога.", reply_markup=kb)
        return

    if not serials:
        await message.answer(
            f"В каталоге нет фигурок с префиксом <code>{prefix}</code>. "
            f"Серии <code>{prefix}</code> нет в каталоге — "
            f"«🔄 Обновить каталог» (префикс {prefix}) или «❓ Помощь».",
            parse_mode="HTML",
            reply_markup=kb,
        )
        return

    records = [{"bricklink_id": s} for s in serials]
    await _send_collage_batches(
        message,
        records,
        title=title,
        telegram_id=telegram_id,
        caption_label=f"серия {prefix}",
    )


async def _update_status_message(
    status: types.Message,
    text: str,
    *,
    reply_markup=None,
    parse_mode: str | None = "HTML",
) -> types.Message:
    """Обновить статус; при ошибке редактирования — новое сообщение (кнопки на старом не ломают процесс)."""
    try:
        await status.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        return status
    except TelegramBadRequest:
        return await status.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)


async def _build_collage_file(
    records: list[dict],
    telegram_id: str,
    title: str,
) -> tuple[str, str] | None:
    """Собрать PNG во временный файл. Возвращает (path, filename) или None."""
    images = await StarWarsCollageGenerator.fetch_and_prepare_images_async(
        records=records,
        id_key="bricklink_id",
        prefix_url=PREFIX_URL,
        min_height=1050,
        font_path="arial.ttf",
        font_size=90,
        max_connections=10,
    )
    if not images:
        return None

    base_name = f"tierlist_{telegram_id}{f'_{title}' if title else ''}.png"
    base_name = re.sub(r'[<>:"/\\|?*]', "_", base_name)[:200]
    if not base_name.endswith(".png"):
        base_name += ".png"

    output_path = os.path.join(TMP_DIR, base_name)
    os.makedirs(TMP_DIR, exist_ok=True)
    await StarWarsCollageGenerator.create_collage_async(
        images=images,
        output_path=output_path,
        columns=5,
        title=title or None,
    )
    return output_path, base_name


async def _send_collage_file(
    bot: Bot,
    chat_id: int,
    file_path: str,
    filename: str,
    caption: str,
    *,
    reply_markup=None,
) -> None:
    with open(file_path, "rb") as f:
        doc = BufferedInputFile(f.read(), filename=filename)
    await bot.send_document(
        chat_id,
        doc,
        caption=caption,
        reply_markup=reply_markup,
    )


async def _send_collage_batches(
    message: types.Message,
    records: list[dict],
    *,
    title: str,
    telegram_id: str,
    caption_label: str,
) -> None:
    if not records:
        return

    total = len(records)
    chat_id = message.chat.id
    bot = message.bot

    if total <= BATCH_SIZE:
        await _generate_and_send_collage(
            records,
            telegram_id,
            title,
            message,
            caption_extra=caption_label,
            attach_menu=True,
        )
        return

    total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
    kb = await _main_kb(telegram_id)
    status = await message.answer(
        f"⏳ Собираю tier‑лист: 0/{total_batches} частей (по {BATCH_SIZE} шт.)…",
        parse_mode="HTML",
    )

    sent = 0
    for batch_no, start in enumerate(range(0, total, BATCH_SIZE), start=1):
        batch = records[start : start + BATCH_SIZE]
        batch_title = f"{title} {batch_no}/{total_batches}".strip()
        await _update_status_message(
            status,
            f"⏳ Часть {batch_no}/{total_batches}: загрузка изображений…",
        )

        built = await _build_collage_file(batch, telegram_id, batch_title)
        if not built:
            await message.answer(
                f"⚠️ Часть {batch_no}/{total_batches}: не удалось собрать коллаж.",
            )
            continue

        file_path, filename = built
        caption = f"Тир-лист {batch_title} ({caption_label})"
        try:
            await _update_status_message(
                status,
                f"⏳ Часть {batch_no}/{total_batches}: отправка файла…",
            )
            await _send_collage_file(
                bot, chat_id, file_path, filename, caption.strip()
            )
            sent += 1
        except Exception as e:
            logger.exception("send collage batch %s", batch_no)
            await message.answer(
                f"⚠️ Часть {batch_no}/{total_batches}: ошибка отправки ({e}).",
            )
        finally:
            try:
                os.remove(file_path)
            except OSError:
                pass

    if sent:
        await _update_status_message(
            status,
            f"✅ Tier‑лист готов: отправлено <b>{sent}</b> из {total_batches} частей.",
            reply_markup=kb,
        )
    else:
        await _update_status_message(
            status,
            "❌ Не удалось отправить ни одной части tier‑листа.",
            reply_markup=kb,
        )


async def _generate_and_send_collage(
    records: list[dict],
    telegram_id: str,
    title: str,
    message: types.Message,
    caption_extra: str = "",
    *,
    attach_menu: bool = False,
) -> None:
    kb = await _main_kb(telegram_id) if attach_menu else None
    built = await _build_collage_file(records, telegram_id, title)
    if not built:
        await message.answer(
            f"Не удалось загрузить изображения"
            f"{f' ({caption_extra})' if caption_extra else ''}.",
            reply_markup=kb or await _main_kb(telegram_id),
        )
        return

    file_path, filename = built
    caption = f"Тир-лист {title or ''} готов!"
    if caption_extra:
        caption += f" ({caption_extra})"

    try:
        await _send_collage_file(
            message.bot,
            message.chat.id,
            file_path,
            filename,
            caption.strip(),
            reply_markup=kb,
        )
    except Exception as e:
        logger.exception("send collage")
        await message.answer(
            f"Ошибка отправки файла: {e}",
            reply_markup=kb or await _main_kb(telegram_id),
        )
    finally:
        try:
            os.remove(file_path)
        except OSError:
            pass
