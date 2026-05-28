"""Постановка задач коллажа в Celery."""

from __future__ import annotations

import logging
from typing import Any

from app.celery_app import celery_app
from app.tasks.collage_tasks import process_collage_job

logger = logging.getLogger(__name__)


def estimate_queue_position() -> int:
    """Сколько задач collage уже в работе/очереди (приблизительно)."""
    try:
        inspect = celery_app.control.inspect(timeout=1.0)
        if not inspect:
            return 0
        count = 0
        for bucket in (inspect.active() or {}, inspect.reserved() or {}):
            for tasks in bucket.values():
                for task in tasks:
                    name = task.get("name") or ""
                    if "collage" in name:
                        count += 1
        return count
    except Exception:
        logger.debug("celery inspect unavailable", exc_info=True)
        return 0


def enqueue_collage_job(
    *,
    chat_id: int,
    telegram_id: str,
    parts: list[dict[str, Any]],
) -> str:
    """
    parts: список {records, title, caption_prefix, caption_extra, owned_ids?}
    Возвращает Celery task id.
    """
    payload = {
        "chat_id": chat_id,
        "telegram_id": telegram_id,
        "parts": parts,
    }
    async_result = process_collage_job.delay(payload)
    return async_result.id


def format_queue_message(task_id: str, position: int) -> str:
    if position <= 0:
        return (
            "⏳ <b>Коллаж принят в работу</b>\n"
            f"ID: <code>{task_id[:8]}</code>\n"
            "Файл придёт в этот чат, когда сборка завершится."
        )
    return (
        "⏳ <b>Коллаж в очереди</b>\n"
        f"Перед вами примерно <b>{position}</b> задач(и). "
        f"ID: <code>{task_id[:8]}</code>\n"
        "Можно пользоваться ботом — результат пришлю сюда."
    )
