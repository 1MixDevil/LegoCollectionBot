"""
Дополнение к Rebrickable CSV: минифигурки, которые есть на BrickLink,
но отсутствуют в set_mappings (часто «without sticker» / редкие варианты).

BrickLink catalogList с VPS режет AWS WAF, поэтому держим явный seed.
Ключ — префикс артикула (bob, …), значение — (bricklink_id, name).
"""

from __future__ import annotations

# Только Minifigure (M=), не Parts (P=). bob004/bob018 — Gary (parts), не сюда.
# bob009 / bob010 в каталоге BrickLink есть, но это оболочки «without sticker»:
# их нельзя инвентаризировать, фигурка живёт на bob009s / bob010s.
SUPPLEMENT_BY_PREFIX: dict[str, list[tuple[str, str]]] = {
    "bob": [
        ("bob009s", "Robot SpongeBob with Sticker"),
        ("bob010s", "Robot Customer with Stickers"),
        ("bob017b", "Bikini Bottom Emergency Room Doctor - Chest Pocket"),
        ("bob024s", "Plankton with Sticker"),
    ],
}


def supplement_for_prefix(article: str) -> list[tuple[str, str]]:
    article = article.strip().lower()
    return list(SUPPLEMENT_BY_PREFIX.get(article, []))
