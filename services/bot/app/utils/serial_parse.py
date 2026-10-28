"""Разбор артикулов BrickLink из текста пользователя."""

from __future__ import annotations

import re

# sw0001a, lor129, hp0023, njo204
SERIAL_RE = re.compile(r"^[a-z][a-z0-9]*\d+[a-z]?$", re.IGNORECASE)


def parse_serial_list(text: str) -> list[str] | None:
    """
    Список артикулов, если после разбиения по «,» / «;» / пробелам / переносам
    каждый токен — артикул BrickLink.

    Так можно вводить и через запятую, и просто пробелами/с новой строки.
    Фраза вроде «Clone Trooper» не распознаётся как список (не все токены — артикулы).
    """
    text = text.strip()
    if not text:
        return []

    tokens = [t.strip() for t in re.split(r"[,;\s]+", text) if t.strip()]
    if not tokens:
        return []

    if all(SERIAL_RE.match(t) for t in tokens):
        return [t.lower() for t in tokens]

    return None
