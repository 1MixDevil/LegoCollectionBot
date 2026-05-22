"""Сводка и аналитика пользовательской коллекции."""

from __future__ import annotations

import re
from collections import Counter
from decimal import Decimal
from typing import Any


def _as_records(records: list[Any]) -> list[dict]:
    out: list[dict] = []
    for rec in records:
        if isinstance(rec, dict):
            out.append(rec)
        elif hasattr(rec, "dict"):
            out.append(rec.dict())
        else:
            out.append(dict(rec))
    return out


def _series_prefix(bricklink_id: str) -> str:
    m = re.match(r"^([a-z]+)", (bricklink_id or "").lower())
    return m.group(1) if m else "?"


def _sum_prices(records: list[dict], field: str) -> tuple[int, Decimal]:
    total = Decimal(0)
    count = 0
    for r in records:
        val = r.get(field)
        if val is not None and val != "":
            try:
                total += Decimal(str(val))
                count += 1
            except Exception:
                pass
    return count, total


def build_collection_summary(records: list[Any]) -> str:
    """HTML-сводка для экрана «Моя коллекция»."""
    rows = _as_records(records)
    if not rows:
        return (
            "📦 <b>Моя коллекция</b>\n\n"
            "Коллекция пуста.\n"
            "Нажмите «➕ Добавить», чтобы внести первую фигурку."
        )

    total = len(rows)
    unique_ids = {r.get("bricklink_id", "").lower() for r in rows if r.get("bricklink_id")}
    duplicates = total - len(unique_ids)

    series = Counter(_series_prefix(r.get("bricklink_id", "")) for r in rows)
    top_series = series.most_common(6)
    series_line = ", ".join(
        f"<code>{pfx}</code> ({cnt})" for pfx, cnt in top_series
    )
    if len(series) > 6:
        series_line += f" … (+{len(series) - 6} серий)"

    buy_n, buy_sum = _sum_prices(rows, "price_buy")
    sale_n, sale_sum = _sum_prices(rows, "price_sale")
    with_desc = sum(1 for r in rows if (r.get("description") or "").strip())
    with_buy_date = sum(1 for r in rows if r.get("buy_date"))
    with_sale_date = sum(1 for r in rows if r.get("sale_date"))

    lines = [
        "📦 <b>Моя коллекция</b>",
        "",
        f"📊 Записей: <b>{total}</b>",
        f"🧩 Уникальных артикулов: <b>{len(unique_ids)}</b>",
    ]
    if duplicates > 0:
        lines.append(f"🔁 Повторов (один артикул несколько раз): <b>{duplicates}</b>")
    lines.extend(["", f"🏷 Серии: {series_line}", ""])

    if buy_n:
        lines.append(f"💰 Цена покупки: <b>{buy_n}</b> шт. · сумма <b>{_fmt_money(buy_sum)}</b>")
    if sale_n:
        lines.append(f"💵 Цена продажи: <b>{sale_n}</b> шт. · сумма <b>{_fmt_money(sale_sum)}</b>")
    if with_desc:
        lines.append(f"📝 С заметками: <b>{with_desc}</b>")
    if with_buy_date:
        lines.append(f"📅 С датой покупки: <b>{with_buy_date}</b>")
    if with_sale_date:
        lines.append(f"📅 С датой продажи: <b>{with_sale_date}</b>")

    lines.append("\n<i>Выберите действие ниже.</i>")
    return "\n".join(lines)


def _fmt_money(value: Decimal) -> str:
    if value == value.to_integral_value():
        return f"{int(value):,}".replace(",", " ") + " ₽"
    return f"{float(value):,.2f}".replace(",", " ") + " ₽"


def filter_collection_records(records: list[Any], query: str) -> list[dict]:
    """Поиск по артикулу и названию (все слова должны совпасть)."""
    rows = _as_records(records)
    words = [w.lower() for w in query.split() if w.strip()]
    if not words:
        return rows

    out: list[dict] = []
    for r in rows:
        hay = f"{r.get('bricklink_id', '')} {r.get('name', '')}".lower()
        if all(w in hay for w in words):
            out.append(r)
    return out


def format_collection_page(
    records: list[dict],
    page: int,
    *,
    page_size: int = 12,
    title: str = "📋 Список",
) -> tuple[str, int]:
    """Текст страницы и число страниц."""
    total = len(records)
    if total == 0:
        return f"{title}\n\nНичего не найдено.", 0

    pages = max(1, (total + page_size - 1) // page_size)
    page = max(0, min(page, pages - 1))
    start = page * page_size
    chunk = records[start : start + page_size]

    lines = [
        f"{title} · стр. {page + 1}/{pages} · всего {total}",
        "",
    ]
    for r in chunk:
        bid = r.get("bricklink_id", "?")
        name = (r.get("name") or "—")[:40]
        extra: list[str] = []
        if r.get("price_buy") is not None:
            extra.append(f"куп. {r['price_buy']}")
        if r.get("price_sale") is not None:
            extra.append(f"прод. {r['price_sale']}")
        suffix = f" ({', '.join(extra)})" if extra else ""
        lines.append(f"• <code>{bid}</code> — {name}{suffix}")

    return "\n".join(lines), pages
