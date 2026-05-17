"""
Официальный BrickLink Store API (OAuth 1.0).

Ключи не протухают как aws-waf-token — настраиваются один раз:
https://www.bricklink.com/v2/api/register_consumer.page

При создании токена укажите внешний IP сервера (для Docker на ПК — ваш публичный IP).
"""

from __future__ import annotations

import logging
import os
from html import unescape
from typing import Any, Optional

import requests
from requests_oauthlib import OAuth1

from app.business.bricklink_client import CatalogItemData

logger = logging.getLogger("BrickLinkAPI")

API_BASE = "https://api.bricklink.com/api/store/v1"


class BrickLinkAPIError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"BrickLink API {code}: {message}")


class BrickLinkItemNotFound(BrickLinkAPIError):
    pass


def api_credentials_configured() -> bool:
    keys = (
        "BRICKLINK_CONSUMER_KEY",
        "BRICKLINK_CONSUMER_SECRET",
        "BRICKLINK_TOKEN",
        "BRICKLINK_TOKEN_SECRET",
    )
    return all(os.getenv(key, "").strip() for key in keys)


def get_data_source() -> str:
    """auto | api | scrape — при auto сначала API, иначе HTML+cookies."""
    return os.getenv("BRICKLINK_DATA_SOURCE", "auto").strip().lower()


def _oauth_session() -> requests.Session:
    auth = OAuth1(
        client_key=os.environ["BRICKLINK_CONSUMER_KEY"],
        client_secret=os.environ["BRICKLINK_CONSUMER_SECRET"],
        resource_owner_key=os.environ["BRICKLINK_TOKEN"],
        resource_owner_secret=os.environ["BRICKLINK_TOKEN_SECRET"],
        signature_method="HMAC-SHA1",
    )
    session = requests.Session()
    session.auth = auth
    session.headers["Accept"] = "application/json"
    return session


def get_catalog_item(item_no: str, item_type: str = "MINIFIG") -> CatalogItemData:
    """
  GET /items/{type}/{no} — см. BrickLink API Catalog Item.
  https://www.bricklink.com/v3/api.page
    """
    item_no = item_no.strip()
    url = f"{API_BASE}/items/{item_type}/{item_no}"

    session = _oauth_session()
    response = session.get(url, timeout=30)
    try:
        payload: dict[str, Any] = response.json()
    except ValueError as exc:
        raise BrickLinkAPIError(
            str(response.status_code),
            f"Не JSON: {response.text[:200]}",
        ) from exc

    meta = payload.get("meta") or {}
    code = str(meta.get("code", response.status_code))

    if code == "404":
        raise BrickLinkItemNotFound(code, meta.get("message", "Item not found"))
    if code != "200":
        raise BrickLinkAPIError(
            code,
            meta.get("description") or meta.get("message") or "Unknown error",
        )

    data = payload.get("data") or {}
    name = unescape(str(data.get("name") or "")).strip()
    if not name:
        raise BrickLinkAPIError(code, "Пустое имя в ответе API")

    extra: dict[str, Any] = {}
    if data.get("year_released"):
        extra["year_released"] = data["year_released"]
    if data.get("weight"):
        extra["weight_g"] = data["weight"]
    if data.get("image_url"):
        extra["image_url"] = data["image_url"]
    if data.get("category_id"):
        extra["category_id"] = data["category_id"]

    return CatalogItemData(
        bricklink_id=str(data.get("no") or item_no).lower(),
        name=name,
        item_type=str(data.get("type") or item_type),
        year_released=str(data["year_released"]) if data.get("year_released") else None,
        weight=str(data["weight"]) if data.get("weight") else None,
        extra=extra,
    )
