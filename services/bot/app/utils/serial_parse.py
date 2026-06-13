"""Разбор артикулов BrickLink из текста пользователя."""

from __future__ import annotations

import re

# sw0001a, sh0689, 85863pb101, 47394pb187
_SERIAL_CHARS_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*$", re.IGNORECASE)


def is_serial_token(token: str) -> bool:
    """Токен похож на артикул BrickLink (есть цифра, только допустимые символы)."""
    token = (token or "").strip()
    if not token or len(token) > 64:
        return False
    if not _SERIAL_CHARS_RE.match(token):
        return False
    return bool(re.search(r"\d", token))


def _split_tokens(text: str) -> list[str]:
    return [t.strip() for t in re.split(r"[,;\s]+", text.strip()) if t.strip()]


def invalid_serial_tokens(text: str) -> list[str]:
    """Токены из строки, которые не похожи на артикулы."""
    return [t for t in _split_tokens(text) if not is_serial_token(t)]


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
        tokens = _split_tokens(text)
        if tokens and all(is_serial_token(t) for t in tokens):
            return [t.lower() for t in tokens]
        return None

    if is_serial_token(text):
        return [text.lower()]

    return None
