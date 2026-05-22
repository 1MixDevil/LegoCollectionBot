"""Карточка фигурки для info и поиска по фото."""

from __future__ import annotations

from typing import Any, Optional

import httpx
from aiogram import Bot
from aiogram.types import BufferedInputFile, InlineKeyboardMarkup
from httpx import HTTPStatusError

from app.api.collection import get_figure_info, list_user_figures
from app.keyboards.main import make_info_kb


def bricklink_catalog_url(bricklink_id: str) -> str:
    return (
        f"https://www.bricklink.com/v2/catalog/catalogitem.page?"
        f"M={bricklink_id.lower()}"
    )


def _format_money(value) -> str:
    if value is None:
        return "–"
    try:
        num = float(value)
        if num == int(num):
            return f"{int(num)}"
        return f"{num:.2f}"
    except (TypeError, ValueError):
        return str(value)


async def get_user_figure_stats(
    telegram_id: str,
    bricklink_id: str,
) -> dict[str, Any]:
    """Сколько экземпляров в коллекции и сколько выставлено на продажу."""
    bricklink_id = bricklink_id.lower()
    try:
        records = await list_user_figures(telegram_id)
    except Exception:
        return {"count": 0, "for_sale": 0, "sale_prices": [], "records": []}

    matches = [
        r
        for r in records
        if (r.get("bricklink_id") or "").lower() == bricklink_id
    ]
    sale_prices = [
        float(r["price_sale"])
        for r in matches
        if r.get("price_sale") is not None
    ]
    return {
        "count": len(matches),
        "for_sale": len(sale_prices),
        "sale_prices": sale_prices,
        "records": matches,
    }


def build_caption(
    *,
    name: str,
    bricklink_id: str,
    bricklink_url: str | None = None,
    recognition_score: float | None = None,
    in_catalog: bool = True,
    catalog_name: str | None = None,
    user_record: dict | None = None,
    collection_stats: dict | None = None,
) -> str:
    lines: list[str] = []

    if recognition_score is not None:
        lines.append(f"🔎 <b>Распознано</b> ({recognition_score * 100:.0f}%)")
    else:
        lines.append(f"🔍 <b>{name}</b>")

    if recognition_score is not None:
        lines.append(f"<b>{name}</b>")

    lines.append(f"• Артикул: <code>{bricklink_id}</code>")

    url = bricklink_url or bricklink_catalog_url(bricklink_id)
    lines.append(f'• <a href="{url}">Открыть на BrickLink</a>')

    if in_catalog:
        display_name = catalog_name or name
        if recognition_score is not None and display_name != name:
            lines.append(f"• В каталоге бота: {display_name}")
    else:
        lines.append(
            "• ⚠️ Нет в каталоге — «🔄 Обновить каталог» (админ) или «❓ Помощь»"
        )

    stats = collection_stats or {}
    count = stats.get("count", 0)
    for_sale = stats.get("for_sale", 0)

    if count > 0:
        lines.append(f"• 📦 В вашей коллекции: <b>{count}</b> шт.")
    else:
        lines.append("• 📦 В вашей коллекции: нет")

    if for_sale > 0:
        prices = stats.get("sale_prices") or []
        if prices:
            price_str = ", ".join(_format_money(p) for p in sorted(prices))
            lines.append(
                f"• 💰 На продажу: <b>{for_sale}</b> шт. (цены: {price_str})"
            )
        else:
            lines.append(f"• 💰 На продажу: <b>{for_sale}</b> шт.")
    else:
        lines.append("• 💰 На продажу: нет")

    if user_record:
        lines.append(
            f"• Цена покупки (последняя): "
            f"{_format_money(user_record.get('price_buy'))}"
        )
        lines.append(
            f"• Описание: {user_record.get('description') or '–'}"
        )
        lines.append(
            f"• Дата покупки: {user_record.get('buy_date') or '–'}"
        )

    return "\n".join(lines)


async def send_figure_card(
    bot: Bot,
    chat_id: int,
    telegram_id: str,
    bricklink_id: str,
    *,
    name: str | None = None,
    bricklink_url: str | None = None,
    recognition_score: float | None = None,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> bool:
    """Отправляет фото/текст с карточкой. Возвращает True, если фигурка есть в каталоге БД."""
    bricklink_id = bricklink_id.lower()
    in_catalog = True
    catalog_name: str | None = name
    user_record: dict | None = None

    try:
        info = await get_figure_info(telegram_id, bricklink_id)
        catalog_name = info.get("name") or name or bricklink_id
        user_record = info.get("user_record")
    except HTTPStatusError as e:
        if e.response.status_code == 404:
            in_catalog = False
            catalog_name = name or bricklink_id
        else:
            raise

    stats = await get_user_figure_stats(telegram_id, bricklink_id)
    caption = build_caption(
        name=catalog_name or bricklink_id,
        bricklink_id=bricklink_id,
        bricklink_url=bricklink_url,
        recognition_score=recognition_score,
        in_catalog=in_catalog,
        catalog_name=catalog_name,
        user_record=user_record,
        collection_stats=stats,
    )
    kb = reply_markup or make_info_kb(bricklink_id)
    image_url = f"https://img.bricklink.com/ItemImage/MN/0/{bricklink_id}.png"

    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=20.0,
        ) as client:
            img_resp = await client.get(image_url)
            img_resp.raise_for_status()
            photo = BufferedInputFile(img_resp.content, filename=f"{bricklink_id}.png")
        await bot.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=caption,
            parse_mode="HTML",
            reply_markup=kb,
        )
    except Exception:
        await bot.send_message(
            chat_id=chat_id,
            text=caption,
            parse_mode="HTML",
            reply_markup=kb,
            disable_web_page_preview=False,
        )

    return in_catalog
