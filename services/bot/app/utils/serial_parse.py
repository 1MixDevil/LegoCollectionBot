"""Разбор артикулов BrickLink из текста пользователя."""

from __future__ import annotations

import re

# sw0001a, lor129, hp0023
SERIAL_RE = re.compile(r"^[a-z][a-z0-9]*\d+[a-z]?$", re.IGNORECASE)


def parse_serial_list(text: str) -> list[str] | None:
    """
    Список артикулов только если разделены «,» или «;» и каждый токен — артикул.
    Один артикул без разделителей — один элемент.
    Иначе None (фраза целиком, не дробить по пробелам).
    """
    text = text.strip()
    if not text:
        return []

    if re.search(r"[,;]", text):
        tokens = [t.strip() for t in re.split(r"[,;]+", text) if t.strip()]
        if tokens and all(SERIAL_RE.match(t) for t in tokens):
            return [t.lower() for t in tokens]
        return None

    if SERIAL_RE.match(text):
        return [text.lower()]

    return None
