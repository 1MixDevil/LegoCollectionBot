"""
Нормализация BrickLink ID и типа каталога.

Минифигурки: sw0001a, njo0001 → ?M=
Сеты (и Comic-Con exclusives): 75192-1, comcon029-1 → ?S=
Детали: 973pb1795c01 → ?P=

Раньше всё открывали как ?M= — отсюда «No Item(s) were found» на comcon*-1.
"""

from __future__ import annotations

import re

# API type → query letter на catalogitem.page / catalogPG.asp
_TYPE_LETTER = {
    "MINIFIG": "M",
    "SET": "S",
    "PART": "P",
    "BOOK": "B",
    "GEAR": "G",
    "CATALOG": "C",
}

_SET_RE = re.compile(r"^.+-\d+$", re.IGNORECASE)
# Детали: начинаются с цифры или типичные суффиксы печати/паттерна
_PART_HINT_RE = re.compile(
    r"(?:^\d)|(?:pb\d)|(?:pr\d)|(?:pat\d)|(?:c\d{2}pb)|(?:^\d+c\d)",
    re.IGNORECASE,
)
_MINIFIG_RE = re.compile(r"^[a-z]{1,8}\d+[a-z]?$", re.IGNORECASE)


def normalize_bricklink_id(item_id: str) -> str:
    return (item_id or "").strip().lower()


def infer_item_type(item_id: str) -> str:
    """
    BrickLink Store API type: MINIFIG | SET | PART.
    Эвристика по номеру (без сети).
    """
    item_id = normalize_bricklink_id(item_id)
    if not item_id:
        return "MINIFIG"
    if _SET_RE.match(item_id):
        return "SET"
    if _MINIFIG_RE.match(item_id):
        return "MINIFIG"
    if _PART_HINT_RE.search(item_id):
        return "PART"
    return "MINIFIG"


def catalog_query_letter(item_id: str) -> str:
    return _TYPE_LETTER.get(infer_item_type(item_id), "M")


def catalog_item_url(item_id: str) -> str:
    item_id = normalize_bricklink_id(item_id)
    letter = catalog_query_letter(item_id)
    return (
        f"https://www.bricklink.com/v2/catalog/catalogitem.page?"
        f"{letter}={item_id}"
    )


def price_guide_url(item_id: str) -> str:
    item_id = normalize_bricklink_id(item_id)
    letter = catalog_query_letter(item_id)
    return f"https://www.bricklink.com/catalogPG.asp?{letter}={item_id}"


def item_image_url(item_id: str) -> str:
    """Крупное фото каталога (N = large)."""
    item_id = normalize_bricklink_id(item_id)
    letter = catalog_query_letter(item_id)
    return f"https://img.bricklink.com/ItemImage/{letter}N/0/{item_id}.png"
