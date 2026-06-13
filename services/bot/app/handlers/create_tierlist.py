import logging
import os

from aiogram import Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.api.collection import (
    fetch_all_catalog_serials,
    list_user_figures,
    search_figures_by_keyword,
)
from app.core.access import ensure_access, get_main_keyboard, get_user_role
from app.core.config import MAX_SERIALS_PER_REQUEST
from app.core.permissions import can_access
from app.keyboards.main import nav_kb, tierlist_menu_kb, tierlist_mode_kb
from app.keyboards.nav_labels import MAIN_MENU_LABEL
from app.services.collage_delivery import (
    generate_and_send_collage,
    send_collage_batches,
)
from app.services.collage_limits import (
    COLLAGE_BATCH_SIZE,
    cap_tierlist_records,
    should_send_in_batches,
    tierlist_max_figures,
)
from app.services.tierlist_title import (
    TIERLIST_TITLE_MAX,
    looks_like_serial_list,
    normalize_tierlist_title,
)
from app.states.figures import CreateTierList
from app.utils.message import safe_edit_or_answer
from app.utils.serial_parse import parse_serial_list
from app.utils.telegram_network import safe_callback_answer

logger = logging.getLogger(__name__)
router = Router()
TIERLIST_KEYWORD_MAX = int(os.getenv("TIERLIST_KEYWORD_MAX", "500"))

SERIES_COMMAND = "series"


async def _notify_stale_button(call: types.CallbackQuery, text: str) -> None:
    if not await safe_callback_answer(call, text, show_alert=True):
        try:
            await call.message.answer(
                f"⚠️ {text}\n\nОткройте /menu и создайте tier‑лист заново.",
            )
        except Exception:
            pass


def tierlist_mark_owned_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, красным крестиком",
                    callback_data="tierlist_mark_owned:yes",
                ),
                InlineKeyboardButton(
                    text="❌ Нет",
                    callback_data="tierlist_mark_owned:no",
                ),
            ],
            [InlineKeyboardButton(text=MAIN_MENU_LABEL, callback_data="cancel")],
        ]
    )


TIERLIST_NAME_PROMPT = (
    f"Введите название коллажа (до <b>{TIERLIST_TITLE_MAX}</b> символов).\n"
    "Короткое имя — на коллаже и в подписи к файлу.\n"
    "Если не нужно — отправьте <code>null</code>.\n\n"
    "<i>Не вставляйте сюда список артикулов — их введёте на следующем шаге.</i>"
)


async def _prompt_tierlist_name(message: types.Message) -> None:
    await message.answer(TIERLIST_NAME_PROMPT, parse_mode="HTML", reply_markup=nav_kb())


@router.callback_query(lambda cb: cb.data == "tierlist_menu")
async def cb_tierlist_menu(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await ensure_access(call, "tierlist"):
        return
    await state.clear()
    await call.answer()
    await safe_edit_or_answer(
        call.message,
        "🖼 <b>Коллаж</b>\n\n"
        "• <b>Создать коллаж</b> — выбрать фигурки и собрать tier‑лист.\n"
        "• <b>Коллаж коллекции</b> — все фигурки из вашей коллекции.",
        parse_mode="HTML",
        reply_markup=tierlist_menu_kb(),
    )


@router.callback_query(lambda cb: cb.data == "tierlist_back_name")
async def cb_tierlist_back_name(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await ensure_access(call, "tierlist"):
        return
    await call.answer()
    await state.set_state(CreateTierList.waiting_name_list)
    await call.message.answer(
        TIERLIST_NAME_PROMPT,
        parse_mode="HTML",
        reply_markup=nav_kb(back="tierlist_menu"),
    )


@router.callback_query(lambda cb: cb.data == "tierlist_back_mode")
async def cb_tierlist_back_mode(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await ensure_access(call, "tierlist"):
        return
    await call.answer()
    role = await get_user_role(str(call.from_user.id))
    await state.set_state(CreateTierList.waiting_mode)
    await call.message.answer(
        "Как собрать коллаж?",
        reply_markup=tierlist_mode_kb(role),
    )


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

    serials = parse_serial_list(text)
    if serials is not None:
        return ("serials", serials)

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
    serials = parse_serial_list(text)
    if serials is not None:
        return ("serials", serials)
    return None


def _dedupe_records_with_counts(records: list[dict]) -> tuple[list[dict], list[str]]:
    uniq: list[dict] = []
    counts: dict[str, int] = {}
    by_id: dict[str, dict] = {}
    for rec in records:
        bid = (rec.get("bricklink_id") or "").strip().lower()
        if not bid:
            continue
        counts[bid] = counts.get(bid, 0) + 1
        if bid not in by_id:
            by_id[bid] = rec
            uniq.append(rec)
    for rec in uniq:
        bid = (rec.get("bricklink_id") or "").strip().lower()
        cnt = counts.get(bid, 1)
        if cnt > 1:
            rec["repeat_count"] = cnt
        else:
            rec.pop("repeat_count", None)
    duplicates = [f"{bid} ×{cnt}" for bid, cnt in counts.items() if cnt > 1]
    return uniq, duplicates


async def _owned_ids(telegram_id: str, mark_owned: bool) -> frozenset[str] | None:
    if not mark_owned:
        return None
    try:
        figures = await list_user_figures(telegram_id)
        owned = frozenset(
            (f.get("bricklink_id") or "").lower()
            for f in figures
            if f.get("bricklink_id")
        )
        logger.info(
            "Tierlist owned marks: %s ids in collection for telegram %s",
            len(owned),
            telegram_id,
        )
        return owned
    except Exception:
        logger.exception("load collection for tierlist marks")
        return frozenset()


async def _ask_mark_owned(
    message: types.Message,
    state: FSMContext,
    records: list[dict],
    caption_label: str,
) -> None:
    await state.update_data(
        tierlist_pending={
            "records": records,
            "caption_label": caption_label,
        }
    )
    await message.answer(
        "Помечать фигурки, которые уже есть в <b>вашей коллекции</b>, "
        "красным крестиком на коллаже?",
        parse_mode="HTML",
        reply_markup=tierlist_mark_owned_kb(),
    )
    await state.set_state(CreateTierList.waiting_mark_owned)


async def _deliver_tierlist(
    message: types.Message,
    *,
    pending: dict,
    title: str,
    mark_owned: bool,
    telegram_id: str,
) -> None:
    records = pending.get("records") or []
    caption_label = pending.get("caption_label") or ""
    kb = await get_main_keyboard(telegram_id)
    owned = await _owned_ids(telegram_id, mark_owned)
    records, duplicates = _dedupe_records_with_counts(records)
    if duplicates:
        preview = ", ".join(duplicates[:10])
        more = "" if len(duplicates) <= 10 else f" (+{len(duplicates) - 10})"
        await message.answer(
            "ℹ️ Повторы в tier-листе (на коллаже — <b>×N</b> у артикула):\n"
            f"<code>{preview}{more}</code>",
            parse_mode="HTML",
        )

    title = normalize_tierlist_title(title, figure_count=len(records))

    role = await get_user_role(telegram_id)
    records, dropped = cap_tierlist_records(records, role)
    if dropped > 0:
        limit = tierlist_max_figures(role)
        await message.answer(
            f"⚠️ Tier‑лист ограничен <b>{limit}</b> фигурками для вашего уровня. "
            f"В коллаж попали первые {limit} из списка.",
            parse_mode="HTML",
        )

    if not should_send_in_batches(len(records)):
        await generate_and_send_collage(
            records,
            telegram_id,
            title,
            message,
            caption_label,
            caption_prefix="Тир-лист",
            reply_markup=kb,
            owned_ids=owned,
        )
    else:
        await send_collage_batches(
            message,
            records,
            title=title,
            telegram_id=telegram_id,
            caption_label=caption_label,
            caption_prefix="Тир-лист",
            reply_markup=kb,
            owned_ids=owned,
        )


@router.callback_query(lambda cb: cb.data and cb.data.startswith("tierlist_mark_owned:"))
async def cb_tierlist_mark_owned(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await ensure_access(call, "tierlist"):
        return

    if await state.get_state() != CreateTierList.waiting_mark_owned.state:
        await _notify_stale_button(
            call, "Коллаж уже собирается или кнопка устарела."
        )
        return

    data = await state.get_data()
    pending = data.get("tierlist_pending")
    if not pending or not pending.get("records"):
        await state.clear()
        try:
            await call.message.delete()
        except Exception:
            pass
        await _notify_stale_button(call, "Создайте tier‑лист заново.")
        return

    title = data.get("title") or ""
    mark = call.data.endswith(":yes")
    telegram_id = str(call.from_user.id)

    await state.clear()
    try:
        await call.message.delete()
    except TelegramBadRequest:
        pass
    except Exception:
        logger.debug("Could not delete tierlist prompt message", exc_info=True)

    if not await safe_callback_answer(call, "⏳ Собираю коллаж…"):
        await _notify_stale_button(call, "Кнопка устарела.")
        return
    await _deliver_tierlist(
        call.message,
        pending=pending,
        title=title,
        mark_owned=mark,
        telegram_id=telegram_id,
    )


@router.callback_query(lambda cb: cb.data == "create_tierlist")
async def cb_start_tierlist(call: types.CallbackQuery, state: FSMContext):
    if not await ensure_access(call, "tierlist"):
        return
    if not await safe_callback_answer(call):
        await _notify_stale_button(call, "Это старое меню.")
        return
    await call.message.answer(
        TIERLIST_NAME_PROMPT,
        parse_mode="HTML",
        reply_markup=nav_kb(back="tierlist_menu"),
    )
    await state.set_state(CreateTierList.waiting_name_list)


@router.message(CreateTierList.waiting_name_list)
async def on_name_entered(message: types.Message, state: FSMContext):
    name = (message.text or "").strip()
    if name.lower() == "null":
        name = None
    elif looks_like_serial_list(name):
        await message.answer(
            "Похоже на список артикулов. Введите <b>короткое название</b> "
            f"(до {TIERLIST_TITLE_MAX} символов) или <code>null</code>.",
            parse_mode="HTML",
        )
        return
    elif name and len(name) > TIERLIST_TITLE_MAX:
        await message.answer(
            f"Слишком длинное название ({len(name)} симв.). "
            f"Максимум <b>{TIERLIST_TITLE_MAX}</b>.",
            parse_mode="HTML",
        )
        return
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
        reply_markup=nav_kb(back="tierlist_back_name"),
    )
    await state.set_state(CreateTierList.waiting_serials)


@router.callback_query(lambda cb: cb.data and cb.data.startswith("tierlist_mode:"))
async def cb_tierlist_mode(call: types.CallbackQuery, state: FSMContext):
    mode = call.data.split(":", 1)[1]
    feature = PARSE_MODE_FEATURE.get(mode)
    if not feature or not await ensure_access(call, feature):
        return
    if not await safe_callback_answer(call):
        await _notify_stale_button(call, "Кнопка устарела.")
        return
    await state.update_data(tierlist_mode=mode)
    hint = MODE_HINTS.get(mode, "")
    if mode == "serials":
        hint += f"\n\nЛимит: до {MAX_SERIALS_PER_REQUEST} артикулов."
    elif mode == "keyword":
        hint += (
            f"\n\nЛимит: до {TIERLIST_KEYWORD_MAX} "
            f"(если больше {COLLAGE_BATCH_SIZE} — несколько файлов)."
        )
    await call.message.answer(hint, parse_mode="HTML", reply_markup=nav_kb(back="tierlist_back_mode"))
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
        records = [{"bricklink_id": s} for s in serials]
        await message.answer("Готово. Уточним оформление коллажа…")
        await _ask_mark_owned(message, state, records, caption_label="")
        return

    if mode == "all":
        await _prepare_all_mode(message, state, str(payload), title, telegram_id)
        return
    if mode == "keyword":
        await _prepare_keyword_mode(message, state, str(payload), title)
        return

    await message.answer("Неизвестный режим.", reply_markup=nav_kb())


async def _prepare_keyword_mode(
    message: types.Message,
    state: FSMContext,
    keyword: str,
    title: str,
) -> None:
    telegram_id = str(message.from_user.id)
    kb = await get_main_keyboard(telegram_id)
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
        f"Найдено <b>{len(records)}</b> фигурок.",
        parse_mode="HTML",
    )
    await _ask_mark_owned(
        message, state, records, caption_label=f"поиск: {keyword}"
    )


async def _prepare_all_mode(
    message: types.Message,
    state: FSMContext,
    prefix: str,
    title: str,
    telegram_id: str,
) -> None:
    await message.answer(
        f"Загружаю все <code>{prefix}</code> из каталога…",
        parse_mode="HTML",
    )
    kb = await get_main_keyboard(telegram_id)
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
    await _ask_mark_owned(
        message, state, records, caption_label=f"серия {prefix}"
    )
