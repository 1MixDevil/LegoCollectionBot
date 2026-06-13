"""Разбор артикулов BrickLink из текста пользователя."""

from __future__ import annotations

import re

# sw0001a, lor129, hp0023
SERIAL_RE = re.compile(r"^[a-z][a-z0-9]*\d+[a-z]?$", re.IGNORECASE)


def parse_serial_list(text: str) -> list[str] | None:
    """
    Список артикулов, если токены разделены «,», «;» или пробелами
    и каждый токен — артикул BrickLink.
    Один артикул без разделителей — один элемент.
    Иначе None (поиск по названию целиком).
    """
    text = text.strip()
    if not text:
        return []

    if re.search(r"[,;\s]", text):
        tokens = [t.strip() for t in re.split(r"[,;\s]+", text) if t.strip()]
        if tokens and all(SERIAL_RE.match(t) for t in tokens):
            return [t.lower() for t in tokens]
        return None

    if SERIAL_RE.match(text):
        return [text.lower()]

    return None
