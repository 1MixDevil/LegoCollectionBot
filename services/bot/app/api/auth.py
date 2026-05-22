from typing import Any, Optional

import httpx

from app.core.config import AUTH_BASE_URL


async def get_user_by_telegram(telegram_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{AUTH_BASE_URL}/users/telegram/{telegram_id}")
        response.raise_for_status()
        return response.json()


async def resolve_user_id(telegram_id: str) -> int:
    user = await get_user_by_telegram(telegram_id)
    return int(user["id"])


async def get_user_settings(telegram_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{AUTH_BASE_URL}/users/get_user_settings/{telegram_id}"
        )
        response.raise_for_status()
        return response.json()


async def create_user(telegram_id: str, username: str) -> Optional[dict[str, Any]]:
    payload = {"telegram_username": telegram_id, "username": username}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{AUTH_BASE_URL}/users/", json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 400:
                return None
            raise


async def list_users() -> list[dict[str, Any]]:
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{AUTH_BASE_URL}/users/")
        response.raise_for_status()
        return response.json()


async def set_user_role(user_id: int, role: str) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        response = await client.patch(
            f"{AUTH_BASE_URL}/users/{user_id}/role",
            json={"role": role},
        )
        response.raise_for_status()
        return response.json()


async def update_user_settings(user_id: int, **fields: bool) -> dict[str, Any]:
    payload = {"user_id": user_id, **fields}
    async with httpx.AsyncClient() as client:
        response = await client.put(
            f"{AUTH_BASE_URL}/users/update_user_settings/",
            json=payload,
        )
        response.raise_for_status()
        return response.json()
