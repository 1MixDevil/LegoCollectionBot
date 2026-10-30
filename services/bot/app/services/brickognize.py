"""Распознавание LEGO по фото через Brickognize API."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import httpx

from app.utils.bricklink_ids import catalog_item_url, normalize_bricklink_id

logger = logging.getLogger(__name__)

API_URL = os.getenv(
    "BRICKOGNIZE_API_URL",
    "https://api.brickognize.com/internal/search/",
)
DEFAULT_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "origin": "https://brickognize.com",
    "referer": "https://brickognize.com/",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/148.0.0.0 Safari/537.36"
    ),
}
DEFAULT_TIMEOUT = float(os.getenv("BRICKOGNIZE_TIMEOUT", "120"))

# Brickognize отдаёт type='fig' для минифигурок (не 'minifig')
_MINIFIG_TYPES = frozenset({"minifig", "minifigure", "fig", "figure"})


def _is_bricklink_ext(ext: dict[str, Any]) -> bool:
    return (ext.get("catalog_name") or "").lower() == "bricklink"


def format_top_candidates(
    result: dict[str, Any],
    *,
    limit: int = 5,
    minifigs_only: bool = True,
) -> list[dict[str, Any]]:
    """Лучшие совпадения с BrickLink ID."""
    candidates: list[dict[str, Any]] = []

    for item in result.get("detected_items", []):
        for candidate in item.get("candidate_items", []):
            ctype = (candidate.get("type") or "").lower()
            if minifigs_only and ctype and ctype not in _MINIFIG_TYPES:
                continue

            bricklink = next(
                (ext for ext in candidate.get("external_items", []) if _is_bricklink_ext(ext)),
                None,
            )
            bl_id = bricklink.get("external_id") if bricklink else None
            if not bl_id:
                continue
            bl_id = normalize_bricklink_id(str(bl_id))
            raw_url = (bricklink.get("url") or "").strip()
            # Brickognize иногда отдаёт ?M= для сетов (comcon029-1) — чиним тип сами
            safe_url = catalog_item_url(bl_id)
            if raw_url and ("?S=" in raw_url or "?P=" in raw_url or "?M=" in raw_url):
                # оставляем URL Brickognize только если буква совпадает с нашей эвристикой
                letter = safe_url.split("?")[-1][:1]
                if f"?{letter}=" not in raw_url:
                    raw_url = safe_url
            else:
                raw_url = safe_url

            candidates.append(
                {
                    "id": candidate.get("id"),
                    "type": candidate.get("type"),
                    "name": candidate.get("name") or bl_id,
                    "score": candidate.get("score") or 0,
                    "bricklink_id": bl_id,
                    "bricklink_url": raw_url,
                }
            )

    candidates.sort(key=lambda row: row.get("score") or 0, reverse=True)
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for row in candidates:
        bid = row["bricklink_id"]
        if bid in seen:
            continue
        seen.add(bid)
        unique.append(row)

    return unique[:limit]


async def search_by_image_bytes(
    image_bytes: bytes,
    filename: str = "photo.jpg",
    *,
    external_catalogs: str = "bricklink",
    predict_color: bool = True,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Отправить фото на распознавание."""
    if not image_bytes:
        raise ValueError("Пустое изображение")

    params = {
        "external_catalogs": external_catalogs,
        "predict_color": str(predict_color).lower(),
    }
    mime = "image/jpeg"
    if filename.lower().endswith(".png"):
        mime = "image/png"
    elif filename.lower().endswith(".webp"):
        mime = "image/webp"

    files = {"query_image": (filename, image_bytes, mime)}
    req_timeout = timeout if timeout is not None else DEFAULT_TIMEOUT

    async with httpx.AsyncClient(timeout=req_timeout) as client:
        response = await client.post(
            API_URL,
            params=params,
            headers=DEFAULT_HEADERS,
            files=files,
        )

    response.raise_for_status()
    return response.json()


async def search_by_image_path(
    image_path: str | Path,
    **kwargs: Any,
) -> dict[str, Any]:
    path = Path(image_path)
    if not path.is_file():
        raise FileNotFoundError(path)
    data = path.read_bytes()
    return await search_by_image_bytes(data, path.name, **kwargs)
