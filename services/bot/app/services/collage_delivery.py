"""Сборка и отправка коллажей в Telegram (с разбиением на части)."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import uuid

from aiogram import Bot, types
from aiogram.exceptions import TelegramBadRequest, TelegramEntityTooLarge, TelegramNetworkError
from aiogram.types import BufferedInputFile, InlineKeyboardMarkup

from app.services.collage import StarWarsCollageGenerator
from app.utils.telegram_network import TELEGRAM_DOCUMENT_TIMEOUT, with_telegram_retry

logger = logging.getLogger(__name__)


class CollageFileTooLarge(Exception):
    """PNG превышает лимит отправки в Telegram."""

TMP_DIR = os.getenv("TMP_DIR", "/tmp")
COLLAGE_BATCH_SIZE = int(
    os.getenv("COLLAGE_BATCH_SIZE", os.getenv("BATCH_SIZE", "60"))
)
MAX_FILE_BYTES = int(os.getenv("COLLAGE_MAX_FILE_BYTES", str(45 * 1024 * 1024)))
PREFIX_URL = os.getenv(
    "COLL_PREFIX_URL", "https://img.bricklink.com/ItemImage/MN/0"
)
COLLAGE_COLUMNS = int(os.getenv("COLL_COLUMNS", "5"))
COLLAGE_MIN_HEIGHT = int(os.getenv("COLL_MIN_HEIGHT", "900"))
COLLAGE_IMAGE_FORMAT = os.getenv("COLLAGE_IMAGE_FORMAT", "jpeg").lower()
COLLAGE_SEND_DELAY = float(os.getenv("COLLAGE_SEND_DELAY", "2.0"))


async def update_status_message(
    status: types.Message,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str | None = "HTML",
) -> types.Message:
    try:
        await status.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        return status
    except (TelegramBadRequest, TelegramNetworkError):
        try:
            return await status.answer(
                text, reply_markup=reply_markup, parse_mode=parse_mode
            )
        except TelegramNetworkError:
            return status


async def build_collage_file(
    records: list[dict],
    telegram_id: str,
    title: str,
    *,
    owned_ids: frozenset[str] | None = None,
) -> tuple[str, str] | None:
    images = await StarWarsCollageGenerator.fetch_and_prepare_images_async(
        records=records,
        id_key="bricklink_id",
        prefix_url=PREFIX_URL,
        min_height=COLLAGE_MIN_HEIGHT,
        font_path="arial.ttf",
        font_size=90,
        max_connections=int(os.getenv("CONCURRENT_BATCHES", "5")),
        owned_ids=owned_ids,
    )
    if not images:
        return None

    safe_title = re.sub(r'[<>:"/\\|?*]', "_", title or "")[:80]
    base_name = f"collage_{telegram_id}"
    if safe_title:
        base_name += f"_{safe_title}"
    base_name = re.sub(r"\s+", "_", base_name)[:180]
    ext = ".jpg" if COLLAGE_IMAGE_FORMAT == "jpeg" else ".png"
    base_name = f"{base_name}_{uuid.uuid4().hex[:8]}{ext}"

    output_path = os.path.join(TMP_DIR, base_name)
    os.makedirs(TMP_DIR, exist_ok=True)
    await StarWarsCollageGenerator.create_collage_async(
        images=images,
        output_path=output_path,
        columns=COLLAGE_COLUMNS,
        title=title or None,
    )
    return output_path, base_name


async def send_collage_file(
    bot: Bot,
    chat_id: int,
    file_path: str,
    filename: str,
    caption: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Collage file missing: {file_path}")

    with open(file_path, "rb") as f:
        payload = f.read()
    if len(payload) > MAX_FILE_BYTES:
        raise CollageFileTooLarge(len(payload))
    doc = BufferedInputFile(payload, filename=filename)
    timeout = int(TELEGRAM_DOCUMENT_TIMEOUT)

    async def _send() -> None:
        await bot.send_document(
            chat_id,
            doc,
            caption=caption,
            reply_markup=reply_markup,
            request_timeout=timeout,
        )

    await with_telegram_retry(_send, label="send_document")


async def generate_and_send_collage(
    records: list[dict],
    telegram_id: str,
    title: str,
    message: types.Message,
    caption_extra: str = "",
    *,
    caption_prefix: str = "Тир-лист",
    reply_markup: InlineKeyboardMarkup | None = None,
    owned_ids: frozenset[str] | None = None,
) -> bool:
    built = await build_collage_file(
        records, telegram_id, title, owned_ids=owned_ids
    )
    if not built:
        await message.answer(
            f"Не удалось загрузить изображения"
            f"{f' ({caption_extra})' if caption_extra else ''}.",
            reply_markup=reply_markup,
        )
        return False

    file_path, filename = built
    caption = f"{caption_prefix} {title or ''} готов!".strip()
    if caption_extra:
        caption += f" ({caption_extra})"

    try:
        await send_collage_file(
            message.bot,
            message.chat.id,
            file_path,
            filename,
            caption,
            reply_markup=reply_markup,
        )
        return True
    except (TelegramEntityTooLarge, CollageFileTooLarge):
        await message.answer(
            "⚠️ Коллаж слишком большой для Telegram. "
            f"В коллекции {len(records)} фигурок — бот разобьёт на части "
            f"по {COLLAGE_BATCH_SIZE} шт., нажмите кнопку ещё раз.",
            reply_markup=reply_markup,
        )
        return False
    except TelegramNetworkError:
        await message.answer(
            "⚠️ Не удалось отправить файл: обрыв связи с Telegram. "
            "Проверьте интернет и попробуйте снова.",
            reply_markup=reply_markup,
        )
        return False
    except FileNotFoundError:
        logger.warning("collage file missing on send (duplicate request?)")
        await message.answer(
            "⚠️ Файл коллажа уже отправлен или устарел. "
            "Не нажимайте кнопку повторно — создайте tier‑лист заново.",
            reply_markup=reply_markup,
        )
        return False
    except Exception as e:
        logger.exception("send collage")
        await message.answer(
            f"Ошибка отправки файла: {e}",
            reply_markup=reply_markup,
        )
        return False
    finally:
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
        except OSError:
            pass


async def send_collage_batches(
    message: types.Message,
    records: list[dict],
    *,
    title: str,
    telegram_id: str,
    caption_label: str = "",
    caption_prefix: str = "Коллаж",
    reply_markup: InlineKeyboardMarkup | None = None,
    owned_ids: frozenset[str] | None = None,
) -> None:
    if not records:
        return

    total = len(records)
    chat_id = message.chat.id
    bot = message.bot

    if total <= COLLAGE_BATCH_SIZE:
        await generate_and_send_collage(
            records,
            telegram_id,
            title,
            message,
            caption_label,
            caption_prefix=caption_prefix,
            reply_markup=reply_markup,
            owned_ids=owned_ids,
        )
        return

    total_batches = (total + COLLAGE_BATCH_SIZE - 1) // COLLAGE_BATCH_SIZE
    status = await message.answer(
        f"⏳ Собираю коллаж: 0/{total_batches} частей "
        f"(по {COLLAGE_BATCH_SIZE} из {total} фиг.)…",
        parse_mode="HTML",
    )

    sent = 0
    for batch_no, start in enumerate(range(0, total, COLLAGE_BATCH_SIZE), start=1):
        batch = records[start : start + COLLAGE_BATCH_SIZE]
        batch_title = f"{title} {batch_no}/{total_batches}".strip()
        await update_status_message(
            status,
            f"⏳ Часть {batch_no}/{total_batches}: загрузка изображений…",
        )

        built = await build_collage_file(
            batch, telegram_id, batch_title, owned_ids=owned_ids
        )
        if not built:
            await message.answer(
                f"⚠️ Часть {batch_no}/{total_batches}: не удалось собрать коллаж.",
                reply_markup=reply_markup,
            )
            continue

        file_path, filename = built
        caption = f"{caption_prefix} {batch_title}"
        if caption_label:
            caption += f" ({caption_label})"
        try:
            await update_status_message(
                status,
                f"⏳ Часть {batch_no}/{total_batches}: отправка файла…",
            )
            await send_collage_file(bot, chat_id, file_path, filename, caption.strip())
            sent += 1
            if batch_no < total_batches and COLLAGE_SEND_DELAY > 0:
                await asyncio.sleep(COLLAGE_SEND_DELAY)
        except TelegramNetworkError:
            logger.warning("collage batch %s network error", batch_no)
            try:
                await message.answer(
                    f"⚠️ Часть {batch_no}/{total_batches}: сбой сети при отправке. "
                    "Повторите коллаж позже.",
                    reply_markup=reply_markup,
                )
            except TelegramNetworkError:
                pass
        except (TelegramEntityTooLarge, CollageFileTooLarge):
            logger.warning("collage batch %s too large", batch_no)
            await message.answer(
                f"⚠️ Часть {batch_no}/{total_batches} слишком большая для Telegram. "
                f"Уменьшите COLLAGE_BATCH_SIZE (сейчас {COLLAGE_BATCH_SIZE}).",
                reply_markup=reply_markup,
            )
        except Exception as e:
            logger.exception("send collage batch %s", batch_no)
            try:
                await message.answer(
                    f"⚠️ Часть {batch_no}/{total_batches}: ошибка отправки.",
                    reply_markup=reply_markup,
                )
            except TelegramNetworkError:
                pass
        finally:
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
            except OSError:
                pass

    if sent:
        await update_status_message(
            status,
            f"✅ Коллаж готов: отправлено <b>{sent}</b> из {total_batches} частей.",
            reply_markup=reply_markup,
        )
    else:
        await update_status_message(
            status,
            "❌ Не удалось отправить ни одной части коллажа.",
            reply_markup=reply_markup,
        )
