"""Celery: сборка и доставка коллажей в Telegram."""

from __future__ import annotations

import gc
import logging
import os
from typing import Any

from app.celery_app import celery_app
from app.services.collage_build import build_caption, sync_build_collage
from app.services.collage_limits import COLLAGE_BATCH_SIZE
from app.services.telegram_send import send_document_sync, send_message_sync

logger = logging.getLogger(__name__)


def _owned_frozenset(raw: list[str] | None) -> frozenset[str] | None:
    if not raw:
        return None
    return frozenset(x.lower() for x in raw)


@celery_app.task(name="collage.process_job", bind=True, max_retries=0)
def process_collage_job(self, payload: dict[str, Any]) -> dict[str, Any]:
    """
    payload:
      chat_id, telegram_id,
      parts: [{records, title, caption_prefix, caption_extra, owned_ids?}, ...]
    """
    chat_id = int(payload["chat_id"])
    telegram_id = str(payload["telegram_id"])
    parts: list[dict] = payload.get("parts") or []
    sent = 0
    errors: list[str] = []

    try:
        for idx, part in enumerate(parts, start=1):
            records = part.get("records") or []
            title = part.get("title") or ""
            caption_prefix = part.get("caption_prefix") or "Коллаж"
            caption_extra = part.get("caption_extra") or ""
            owned = _owned_frozenset(part.get("owned_ids"))

            built = sync_build_collage(
                records,
                telegram_id,
                title,
                owned_ids=owned,
            )
            if not built:
                errors.append(f"part {idx}: no images")
                continue

            file_path, filename = built
            caption = build_caption(
                caption_prefix, title, caption_extra, records, owned
            )
            try:
                send_document_sync(chat_id, file_path, caption, filename=filename)
                sent += 1
            finally:
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                except OSError:
                    pass
                gc.collect()

        if sent == 0:
            send_message_sync(
                chat_id,
                "❌ Не удалось собрать коллаж. Проверьте артикулы и попробуйте снова.",
            )
        elif errors:
            send_message_sync(
                chat_id,
                f"⚠️ Отправлено {sent} из {len(parts)} частей. Ошибки: {', '.join(errors)}",
            )

        return {"ok": True, "sent": sent, "parts": len(parts), "errors": errors}
    except Exception as exc:
        logger.exception("collage job failed")
        try:
            send_message_sync(
                chat_id,
                "❌ Ошибка при сборке коллажа на сервере. Попробуйте позже или "
                f"уменьшите список (батч {COLLAGE_BATCH_SIZE} фиг.).",
            )
        except Exception:
            logger.exception("failed to notify user about collage error")
        return {"ok": False, "error": str(exc)}
