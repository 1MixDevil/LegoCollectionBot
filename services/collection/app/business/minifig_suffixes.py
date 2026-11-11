"""Буквенные варианты BrickLink-артикула.

Печатные варианты идут подряд: a, b, c… На них можно останавливаться
после нескольких пустых букв.

Отдельно от этого ряда стоят суффиксы, которые бывают единственной буквой:
  s — со стикером (bob009s есть, bob009a/b нет);
  i — plain / без принта (gb001i, bat011i).

Их нужно проверять даже если a и b пустые.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Не продолжение a,b,c. Проверяются всегда, если до них не дошёл последовательный обход.
DETACHED_SUFFIXES: tuple[str, ...] = ("s", "i")


class SuffixProbe:
    """Какую следующую букву запросить для одного номера."""

    def __init__(
        self,
        max_consecutive_miss: int = 2,
        detached: tuple[str, ...] = DETACHED_SUFFIXES,
    ) -> None:
        self.max_consecutive_miss = max(1, int(max_consecutive_miss))
        self._detached = [ch for ch in detached if ch]
        self._next_ord = ord("a")
        self._seq_miss = 0
        self._seq_open = True
        self._tried: set[str] = set()
        self._from_sequence: set[str] = set()

    def next_letter(self) -> str | None:
        if self._seq_open:
            if self._seq_miss >= self.max_consecutive_miss or self._next_ord > ord("z"):
                self._seq_open = False
            else:
                ch = chr(self._next_ord)
                self._next_ord += 1
                self._tried.add(ch)
                self._from_sequence.add(ch)
                return ch
        while self._detached:
            ch = self._detached.pop(0)
            if ch in self._tried or len(ch) != 1 or not ("a" <= ch <= "z"):
                continue
            self._tried.add(ch)
            return ch
        return None

    def observe(self, letter: str, found: bool) -> None:
        """Учесть ответ BrickLink. На s/i счётчик промахов a,b,c не влияет."""
        if letter not in self._from_sequence:
            return
        if found:
            self._seq_miss = 0
        else:
            self._seq_miss += 1


def letters_if_unknown(max_consecutive_miss: int = 2) -> list[str]:
    """Буквы, которые имеет смысл спросить, если ни одной ещё не находили."""
    probe = SuffixProbe(max_consecutive_miss)
    letters: list[str] = []
    while True:
        letter = probe.next_letter()
        if letter is None:
            return letters
        letters.append(letter)
        probe.observe(letter, False)


def drop_unstickered_shells(
    records: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """
    bob009 «without sticker» в каталоге BrickLink есть, но это не отдельная
    фигурка (cannot be inventoried). Собирают bob009s.
    Убираем такую оболочку, только если вариант со стикером тоже в наборе.
    """
    present = {(bid or "").strip().lower() for bid, _ in records}
    kept: list[tuple[str, str]] = []
    for bid, name in records:
        key = (bid or "").strip().lower()
        if (
            key
            and not key.endswith("s")
            and f"{key}s" in present
            and "without sticker" in (name or "").lower()
        ):
            logger.info("Пропуск оболочки без стикера %s (%s)", key, name)
            continue
        kept.append((key or bid, name))
    return kept
