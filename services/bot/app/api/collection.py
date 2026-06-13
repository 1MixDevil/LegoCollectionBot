from typing import Any, Optional

import httpx

from app.api.auth import resolve_user_id
from app.core.config import COLLECTION_BASE_URL


async def add_figure_to_user(
    telegram_id: str,
    bricklink_id: str,
    price_buy: Optional[float] = None,
    price_sale: Optional[float] = None,
    description: Optional[str] = None,
    buy_date: Optional[str] = None,
    sale_date: Optional[str] = None,
) -> dict[str, Any]:
    user_id = await resolve_user_id(telegram_id)
    payload = {
        "user_id": user_id,
        "bricklink_id": bricklink_id,
        "price_buy": price_buy,
        "price_sale": price_sale,
        "description": description,
        "buy_date": buy_date,
        "sale_date": sale_date,
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{COLLECTION_BASE_URL}/figure/user/", json=payload)
        response.raise_for_status()
        return response.json()


async def update_user_figure_record(rec_id: int, **fields: Any) -> dict[str, Any]:
    payload = dict(fields)
    async with httpx.AsyncClient() as client:
        response = await client.patch(
            f"{COLLECTION_BASE_URL}/figure/user/{rec_id}",
            json=payload,
        )
        response.raise_for_status()
        return response.json()


async def update_all_user_figure_records(
    telegram_id: str,
    bricklink_id: str,
    **fields: Any,
) -> int:
    """Обновляет все записи пользователя с данным артикулом. Возвращает число обновлённых."""
    bricklink_id = bricklink_id.lower()
    records = await list_user_figures(telegram_id)
    updated = 0
    for rec in records:
        if (rec.get("bricklink_id") or "").lower() != bricklink_id:
            continue
        rec_id = rec.get("id")
        if rec_id is None:
            continue
        await update_user_figure_record(int(rec_id), **fields)
        updated += 1
    return updated


async def figure_exists_in_catalog(telegram_id: str, bricklink_id: str) -> bool:
    """Проверка наличия фигурки в общем каталоге."""
    try:
        await get_figure_info(telegram_id, bricklink_id.lower())
        return True
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return False
        raise


async def delete_figure_from_user(telegram_id: str, bricklink_id: str) -> None:
    user_id = await resolve_user_id(telegram_id)
    async with httpx.AsyncClient() as client:
        response = await client.delete(
            f"{COLLECTION_BASE_URL}/figure/user/",
            params={"user_id": user_id, "bricklink_id": bricklink_id},
        )
        response.raise_for_status()


async def list_user_figures(telegram_id: str) -> list[dict[str, Any]]:
    user_id = await resolve_user_id(telegram_id)
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{COLLECTION_BASE_URL}/figure/user/{user_id}/")
        response.raise_for_status()
        return response.json()


async def update_figures_list(article: str, max_miss: int = 20) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=600.0) as client:
        response = await client.put(
            f"{COLLECTION_BASE_URL}/figure/update_figures/",
            params={"article": article, "max_miss": max_miss},
        )
        response.raise_for_status()
        return response.json()


async def fetch_similar_serials(
    serial: str,
    limit: int = 5,
    threshold: float = 0.3,
) -> list[dict[str, Any]]:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{COLLECTION_BASE_URL}/figure/similar/",
            params={"name": serial, "limit": limit, "threshold": threshold},
        )
        if response.status_code == 200:
            return response.json()
    return []


async def clear_user_collection(telegram_id: str) -> None:
    user_id = await resolve_user_id(telegram_id)
    async with httpx.AsyncClient() as client:
        response = await client.delete(
            f"{COLLECTION_BASE_URL}/figure/user/{user_id}/collection"
        )
        response.raise_for_status()


async def get_figure_market(bricklink_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.get(
            f"{COLLECTION_BASE_URL}/figure/market/",
            params={"bricklink_id": bricklink_id},
        )
        response.raise_for_status()
        return response.json()


async def get_figure_info(telegram_id: str, bricklink_id: str) -> dict[str, Any]:
    user_id = await resolve_user_id(telegram_id)
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{COLLECTION_BASE_URL}/figure/info/",
            params={"user_id": user_id, "bricklink_id": bricklink_id},
        )
        response.raise_for_status()
        return response.json()


async def search_figures_by_keyword(
    keyword: str,
    limit: int = 500,
) -> list[dict[str, Any]]:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{COLLECTION_BASE_URL}/figure/search/",
            params={"q": keyword, "limit": limit},
        )
        response.raise_for_status()
        return response.json()


async def fetch_all_catalog_serials(prefix: str | None = None) -> list[str]:
    params = {}
    if prefix:
        params["prefix"] = prefix
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.get(
            f"{COLLECTION_BASE_URL}/figure/all/",
            params=params,
        )
        response.raise_for_status()
        return response.json()


async def add_figure_to_user_bulk(
    telegram_id: str,
    payloads: list[dict[str, Any]],
) -> dict[str, Any]:
    user_id = await resolve_user_id(telegram_id)
    for item in payloads:
        item["user_id"] = user_id

    # Без лимита на число записей; таймаут с запасом на большие списки
    timeout = max(120.0, min(1800.0, 30.0 + len(payloads) * 0.15))
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{COLLECTION_BASE_URL}/figure/user/bulk/",
            json=payloads,
        )
        response.raise_for_status()
        return response.json()
