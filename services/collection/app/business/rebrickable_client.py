"""
Клиент Rebrickable API v3 для каталога минифигурок.

Документация: https://rebrickable.com/api/v3/docs/
Ключ: Account → Settings → API (заголовок Authorization: key YOUR_KEY)
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Optional

import httpx

logger = logging.getLogger("RebrickableClient")

API_BASE = "https://rebrickable.com/api/v3"
REQUEST_INTERVAL = float(os.getenv("REBRICKABLE_REQUEST_INTERVAL", "1.05"))


class RebrickableAPIError(Exception):
    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(f"Rebrickable API {status}: {detail}")


@dataclass
class RebrickableMinifig:
    set_num: str
    name: str
    num_parts: Optional[int] = None
    set_img_url: Optional[str] = None


def api_key_configured() -> bool:
    return bool(os.getenv("REBRICKABLE_API_KEY", "").strip())


def get_catalog_source() -> str:
    """rebrickable | bricklink — откуда наполнять каталог."""
    source = os.getenv("CATALOG_DATA_SOURCE", "rebrickable").strip().lower()
    if source == "auto":
        return "rebrickable" if api_key_configured() else "bricklink"
    return source


def _headers() -> dict[str, str]:
    key = os.environ["REBRICKABLE_API_KEY"]
    return {
        "Authorization": f"key {key}",
        "Accept": "application/json",
    }


class RebrickableClient:
    def __init__(self):
        self._last_request_at = 0.0

    async def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < REQUEST_INTERVAL:
            await asyncio.sleep(REQUEST_INTERVAL - elapsed)
        self._last_request_at = time.monotonic()

    async def _get(
        self,
        client: httpx.AsyncClient,
        path: str,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        await self._throttle()
        url = f"{API_BASE}{path}"
        response = await client.get(url, headers=_headers(), params=params, timeout=60.0)

        if response.status_code == 429:
            retry_after = float(response.headers.get("Retry-After", "2"))
            logger.warning("Rate limit 429, ждём %.1f сек", retry_after)
            await asyncio.sleep(retry_after)
            return await self._get(client, path, params)

        if response.status_code == 404:
            raise RebrickableAPIError(404, "Not found")

        if response.status_code >= 400:
            try:
                body = response.json()
                detail = body.get("detail", response.text[:200])
            except Exception:
                detail = response.text[:200]
            raise RebrickableAPIError(response.status_code, str(detail))

        return response.json()

    async def get_minifig(self, set_num: str) -> RebrickableMinifig:
        set_num = set_num.strip().lower()
        async with httpx.AsyncClient() as client:
            data = await self._get(client, f"/lego/minifigs/{set_num}/")
        return RebrickableMinifig(
            set_num=data.get("set_num", set_num).lower(),
            name=data.get("name", "").strip(),
            num_parts=data.get("num_parts"),
            set_img_url=data.get("set_img_url"),
        )

    async def list_minifigs_page(
        self,
        client: httpx.AsyncClient,
        page: int = 1,
        page_size: int = 1000,
        search: Optional[str] = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "page": page,
            "page_size": min(page_size, 1000),
            "ordering": "set_num",
        }
        if search:
            params["search"] = search
        return await self._get(client, "/lego/minifigs/", params)

    async def fetch_minifigs_by_prefix(self, article: str) -> list[RebrickableMinifig]:
        """
        Загружает все минифигурки с set_num, начинающимся на article (sw, hp, …).
        Использует search + постраничную выборку; фильтрует на всякий случай.
        """
        article = article.strip().lower()
        collected: list[RebrickableMinifig] = []
        page = 1

        async with httpx.AsyncClient() as client:
            while True:
                payload = await self.list_minifigs_page(
                    client, page=page, search=article
                )
                results = payload.get("results") or []
                if not results:
                    break

                matched_on_page = 0
                for row in results:
                    set_num = str(row.get("set_num", "")).lower()
                    if not set_num.startswith(article):
                        continue
                    matched_on_page += 1
                    collected.append(
                        RebrickableMinifig(
                            set_num=set_num,
                            name=str(row.get("name", "")).strip(),
                            num_parts=row.get("num_parts"),
                            set_img_url=row.get("set_img_url"),
                        )
                    )

                logger.info(
                    "[%s] Rebrickable стр.%s: получено %s, подходит %s (всего %s)",
                    article,
                    page,
                    len(results),
                    matched_on_page,
                    len(collected),
                )

                if not payload.get("next"):
                    break
                page += 1

        return collected


_client: Optional[RebrickableClient] = None


def get_client() -> RebrickableClient:
    global _client
    if _client is None:
        _client = RebrickableClient()
    return _client
