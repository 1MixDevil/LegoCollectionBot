
from typing import Optional
import httpx
from config import TOKEN, AUTH_BASE, AUTH_IP, AUTH_PORT, COLL_BASE, COLL_IP, COLL_PORT, RUS_LABELS, TOGGLE_FIELDS


# === HTTP‑вызовы к API ===

async def get_user_settings(telegram_id: str):
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{AUTH_BASE}/users/get_user_settings/{telegram_id}")
        r.raise_for_status()
        return r.json()

async def create_user(telegram_id: str, username: str):
    url = f"{AUTH_BASE}/users/"
    payload = {"telegram_username": telegram_id, "username": username}
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                # Пользователь уже существует
                return None
            raise

async def add_figure_to_user(
    bricklink_id: str,
    user_id: str,
    price_buy: Optional[float]  = None,
    price_sale: Optional[float] = None,
    description: Optional[str]  = None,
    buy_date: Optional[str]     = None,
    sale_date: Optional[str]    = None,
):
    """
    POST /figure/user/ — создаёт связку «пользователь ↔ фигурка»
    со всеми полями из FigureToUserCreate.
    """
    url = f"{COLL_BASE}/figure/user/"
    payload = {
        "user_id":      user_id,
        "bricklink_id": bricklink_id,
        "price_buy":    price_buy,
        "price_sale":   price_sale,
        "description":  description,
        "buy_date":     buy_date,
        "sale_date":    sale_date,
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        return r.json()

async def delete_figure_to_user(serial: str, user_id: str):
    url = f"{COLL_BASE}/figure/user/"
    payload = {
        "user_id": user_id,
        "bricklink_id": serial
    }
    async with httpx.AsyncClient() as client:
        try:
            r = await client.delete(url, params=payload)

            if r.status_code == 204:  # 204 No Content - обычно успешное удаление
                print("Удаление успешно.")
            elif r.status_code == 404:
                print("Фигура не найдена.")
            else:
                print(f"Ошибка при удалении: {r.status_code} - {r.text}")

        except httpx.RequestError as e:
            print(f"Ошибка сети: {e}")
        except Exception as e:
            print(f"Неизвестная ошибка: {e}")


async def list_user_figures(user_id: str):
    url = f"{COLL_BASE}/figure/user/{user_id}/"
    async with httpx.AsyncClient() as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.json()

async def update_figures_list(article: str):
    url = f"{COLL_BASE}/figure/update_figures/"
    params = {"article": article, "max_miss": 20}
    async with httpx.AsyncClient() as client:
        r = await client.put(url, params=params)
        r.raise_for_status()
        return r.text()

async def fetch_similar_serials(serial: str) -> list[str]:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{COLL_BASE}/figure/similar/",
            params={"name": serial, "limit": 5, "threshold": 0.3}
        )
        if r.status_code == 200:
            return r.json()
    return []


async def clear_user_collection(user_id: str):
    """DELETE /user/{user_id}/collection - удаляет все записи коллекции"""
    async with httpx.AsyncClient() as client:
        r = await client.delete(
            f"{COLL_BASE}/figure/users/{user_id}/collection"
        )
        if r.status_code == 204:  # 204 No Content - обычно успешное удаление
            print("Удаление успешно.")
        elif r.status_code == 404:
            print("Фигура не найдена.")
        else:
            print(f"Ошибка при удалении: {r.status_code} - {r.text}")


async def add_figure_to_user_bulk(payloads: list[dict]) -> list[dict]:
    """
    Отправляет список payload'ов на endpoint POST /figure/user/bulk/
    и возвращает JSON‑ответ (List[FigureToUserRead]).
    """
    url = f"{COLL_BASE}/figure/user/bulk/"
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payloads)
        resp.raise_for_status()
        return resp.json()
