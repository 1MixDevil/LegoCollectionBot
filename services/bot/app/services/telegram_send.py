"""Отправка файлов в Telegram из Celery (sync)."""

from __future__ import annotations

import logging
import os

import httpx

from app.core.config import TG_TOKEN

logger = logging.getLogger(__name__)
API_BASE = "https://api.telegram.org"
MAX_FILE_BYTES = int(os.getenv("COLLAGE_MAX_FILE_BYTES", str(45 * 1024 * 1024)))


def send_document_sync(
    chat_id: int,
    file_path: str,
    caption: str,
    *,
    filename: str | None = None,
) -> None:
    if not TG_TOKEN:
        raise RuntimeError("TG_TOKEN is not set")
    if not os.path.isfile(file_path):
        raise FileNotFoundError(file_path)
    size = os.path.getsize(file_path)
    if size > MAX_FILE_BYTES:
        raise ValueError(f"file too large: {size}")

    name = filename or os.path.basename(file_path)
    url = f"{API_BASE}/bot{TG_TOKEN}/sendDocument"
    with open(file_path, "rb") as f:
        data = {"chat_id": str(chat_id), "caption": caption[:1024], "parse_mode": "HTML"}
        files = {"document": (name, f)}
        with httpx.Client(timeout=600.0) as client:
            resp = client.post(url, data=data, files=files)
            resp.raise_for_status()
            body = resp.json()
            if not body.get("ok"):
                raise RuntimeError(body.get("description", "sendDocument failed"))


def send_message_sync(chat_id: int, text: str) -> None:
    if not TG_TOKEN:
        raise RuntimeError("TG_TOKEN is not set")
    url = f"{API_BASE}/bot{TG_TOKEN}/sendMessage"
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(
            url,
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
        )
        resp.raise_for_status()
