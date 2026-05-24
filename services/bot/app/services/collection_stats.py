"""Сводка и аналитика пользовательской коллекции."""

from __future__ import annotations

import re
from collections import Counter
from decimal import Decimal
from typing import Any

PICK_PAGE_SIZE = 8


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

    lines.append(
        "\n<i>Сразу введите артикул или название для поиска — "
        "или выберите кнопку ниже.</i>"
    )
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


def unique_figure_entries(records: list[Any]) -> list[dict]:
    """Одна строка на артикул + счётчик записей в коллекции."""
    rows = _as_records(records)
    by_id: dict[str, dict] = {}
    for r in rows:
        bid = (r.get("bricklink_id") or "").lower()
        if not bid:
            continue
        if bid not in by_id:
            by_id[bid] = {**r, "bricklink_id": bid, "count": 1}
        else:
            by_id[bid]["count"] = by_id[bid].get("count", 1) + 1
    return sorted(by_id.values(), key=lambda x: x["bricklink_id"])


def filter_unique_figures(records: list[Any], query: str) -> list[dict]:
    filtered = filter_collection_records(records, query)
    return unique_figure_entries(filtered)


def format_browse_header(
    *,
    query: str | None,
    total: int,
    page: int,
    pages: int,
) -> str:
    if query:
        title = f"🔍 <b>Поиск:</b> {query}"
    else:
        title = "📋 <b>Список фигурок</b>"
    if total == 0:
        return f"{title}\n\nНичего не найдено."
    return (
        f"{title}\n"
        f"Найдено: <b>{total}</b> · стр. <b>{page + 1}/{pages}</b>\n\n"
        "Нажмите кнопку или введите артикул в чат.\n"
        "<i>Удаление — на карточке фигурки.</i>"
    )


def figure_button_label(entry: dict) -> str:
    bid = entry.get("bricklink_id", "?")
    name = (entry.get("name") or "").strip()
    count = int(entry.get("count") or 1)
    if name:
        short = name if len(name) <= 22 else name[:21] + "…"
        label = f"{bid} · {short}"
    else:
        label = bid
    if count > 1:
        label += f" ×{count}"
    return label[:60]
