"""Карточка фигурки для info и поиска по фото."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

import httpx
from aiogram import Bot
from aiogram.types import BufferedInputFile, InlineKeyboardMarkup
from httpx import HTTPStatusError

from app.api.collection import get_figure_info, get_figure_market, list_user_figures
from app.keyboards.main import make_info_kb

logger = logging.getLogger(__name__)

LOADING_CARD_TEXT = "⏳ Ожидайте, открываю информацию о фигурке…"


def bricklink_catalog_url(bricklink_id: str) -> str:
    return (
        f"https://www.bricklink.com/v2/catalog/catalogitem.page?"
        f"M={bricklink_id.lower()}"
    )


def bricklink_price_guide_url(bricklink_id: str) -> str:
    return f"https://www.bricklink.com/catalogPG.asp?M={bricklink_id.lower()}"


def _format_money(value, currency: str = "") -> str:
    if value is None:
        return "–"
    try:
        num = float(value)
        if currency == "RUB":
            suffix = " ₽"
        elif currency:
            suffix = f" {currency}"
        else:
            suffix = ""
        if num == int(num):
            return f"{int(num)}{suffix}"
        return f"{num:.2f}{suffix}"
    except (TypeError, ValueError):
        return str(value)


def _format_price_dual(
    amount,
    currency: str,
    source_currency: str | None,
    exchange_rate: float | None,
) -> str:
    main = _format_money(amount, currency)
    if (
        not source_currency
        or not exchange_rate
        or amount is None
        or currency == source_currency
    ):
        return main
    try:
        original = float(amount) / float(exchange_rate)
    except (TypeError, ValueError, ZeroDivisionError):
        return main
    return f"{main} ({_format_money(original, source_currency)})"


def _format_rate_date(iso_date: str) -> str:
    try:
        return datetime.strptime(iso_date[:10], "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return iso_date[:10]


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


def _format_market_lines(market: dict | None, bricklink_id: str = "") -> list[str]:
    bid = (market or {}).get("bricklink_id") or bricklink_id
    if not market or market.get("error"):
        return [
            "• 📊 BrickLink: цены временно недоступны",
            f'• <a href="{bricklink_price_guide_url(bid)}">Price Guide на BrickLink</a>',
        ]

    cur = market.get("currency") or "USD"
    src_cur = market.get("source_currency")
    rate = market.get("exchange_rate")
    lines = ["", "📊 <b>BrickLink</b> (средние за 6 мес.)"]
    if src_cur and rate and cur == "RUB":
        rate_date = market.get("exchange_rate_date") or ""
        date_str = _format_rate_date(rate_date) if rate_date else ""
        date_part = f" на {date_str}" if date_str else ""
        lines.append(f"• Курс ЦБ{date_part}: 1 {src_cur} = {rate:.2f} ₽")
    pg_url = market.get("price_guide_url") or bricklink_price_guide_url(
        market.get("bricklink_id", "")
    )

    for label, sale_label, key in (
        ("🆕 Новая", "нов.", "new"),
        ("♻️ Б/У", "б/у", "used"),
    ):
        c = market.get(key) or {}
        avg6 = c.get("avg_price_6m")
        sold = c.get("times_sold_6m")
        if avg6 is not None:
            price_str = _format_price_dual(avg6, cur, src_cur, rate)
            part = f"{label}: <b>{price_str}</b>"
            if sold is not None:
                part += f" · продаж {sold}"
            lines.append(f"• {part}")
        lots = c.get("total_lots")
        qty = c.get("total_qty_for_sale")
        avg_l = c.get("avg_price_listed")
        if lots is not None and qty is not None:
            extra = (
                f" · ср. {_format_price_dual(avg_l, cur, src_cur, rate)}"
                if avg_l
                else ""
            )
            lines.append(
                f"• 🛒 В продаже ({sale_label}): <b>{lots}</b> лотов / "
                f"<b>{qty}</b> шт.{extra}"
            )

    lines.append(f'• <a href="{pg_url}">Подробный Price Guide</a>')
    return lines


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
    market: dict | None = None,
) -> str:
    lines: list[str] = []

    if recognition_score is not None:
        lines.append(f"🔎 <b>Распознано</b> ({recognition_score * 100:.0f}%)")
        lines.append(f"<b>{name}</b>")
    else:
        lines.append(f"🔍 <b>{name}</b>")

    lines.append(f"• Артикул: <code>{bricklink_id}</code>")

    url = bricklink_url or bricklink_catalog_url(bricklink_id)
    lines.append(f'• <a href="{url}">Каталог BrickLink</a>')

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

    lines.append("")
    lines.append("<b>Ваша коллекция</b>")
    if count > 0:
        lines.append(f"• 📦 В коллекции: <b>{count}</b> шт.")
    else:
        lines.append("• 📦 В коллекции: нет")

    if for_sale > 0:
        prices = stats.get("sale_prices") or []
        if prices:
            price_str = ", ".join(_format_money(p) for p in sorted(prices))
            lines.append(
                f"• 💰 Ваши объявления: <b>{for_sale}</b> шт. (цены: {price_str})"
            )
        else:
            lines.append(f"• 💰 Ваши объявления: <b>{for_sale}</b> шт.")
    else:
        lines.append("• 💰 Ваши объявления: нет")

    if user_record:
        lines.append(
            f"• Цена покупки (запись): {_format_money(user_record.get('price_buy'))}"
        )
        if user_record.get("price_sale") is not None:
            lines.append(
                f"• Цена продажи (запись): {_format_money(user_record.get('price_sale'))}"
            )
        desc = (user_record.get("description") or "").strip()
        if desc:
            short = desc[:120] + ("…" if len(desc) > 120 else "")
            lines.append(f"• Заметка: {short}")
        if user_record.get("buy_date"):
            lines.append(f"• Дата покупки: {user_record.get('buy_date')}")
        if user_record.get("sale_date"):
            lines.append(f"• Дата продажи: {user_record.get('sale_date')}")

    lines.extend(_format_market_lines(market, bricklink_id))

    return "\n".join(lines)


async def _fetch_figure_card_data(
    telegram_id: str,
    bricklink_id: str,
    *,
    name: str | None = None,
) -> tuple[bool, str | None, dict | None, dict | None, dict]:
    bricklink_id = bricklink_id.lower()
    in_catalog = True
    catalog_name: str | None = name
    user_record: dict | None = None
    market: dict | None = None

    async def fetch_info() -> None:
        nonlocal in_catalog, catalog_name, user_record
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

    async def fetch_market() -> None:
        nonlocal market
        try:
            market = await get_figure_market(bricklink_id)
        except Exception:
            logger.exception("market prices for %s", bricklink_id)
            market = {"bricklink_id": bricklink_id, "error": "fetch_failed"}

    stats, _, _ = await asyncio.gather(
        get_user_figure_stats(telegram_id, bricklink_id),
        fetch_info(),
        fetch_market(),
    )
    return in_catalog, catalog_name, user_record, market, stats


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
    in_catalog, catalog_name, user_record, market, stats = await _fetch_figure_card_data(
        telegram_id, bricklink_id, name=name
    )
    caption = build_caption(
        name=catalog_name or bricklink_id,
        bricklink_id=bricklink_id,
        bricklink_url=bricklink_url,
        recognition_score=recognition_score,
        in_catalog=in_catalog,
        catalog_name=catalog_name,
        user_record=user_record,
        collection_stats=stats,
        market=market,
    )
    in_collection = bool(stats.get("count", 0))
    kb = reply_markup or make_info_kb(bricklink_id, in_collection=in_collection)
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
        logger.info("send photo fallback for %s", bricklink_id)
        await bot.send_message(
            chat_id=chat_id,
            text=caption,
            parse_mode="HTML",
            reply_markup=kb,
            disable_web_page_preview=False,
        )

    return in_catalog


async def send_figure_card_with_loading(
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
    """Карточка с сообщением «загрузка» (удаляется после отправки)."""
    status = await bot.send_message(chat_id, LOADING_CARD_TEXT)
    try:
        return await send_figure_card(
            bot,
            chat_id,
            telegram_id,
            bricklink_id,
            name=name,
            bricklink_url=bricklink_url,
            recognition_score=recognition_score,
            reply_markup=reply_markup,
        )
    finally:
        try:
            await status.delete()
        except Exception:
            pass
