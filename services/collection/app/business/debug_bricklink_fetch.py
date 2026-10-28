#!/usr/bin/env python3
"""Проверка доступа к BrickLink catalogList (запускать в collection-service).

  docker compose exec collection-service python -m app.business.debug_bricklink_fetch njo
"""

from __future__ import annotations

import asyncio
import sys


async def main(article: str = "njo") -> int:
    from app.business.bricklink_catalog_list import (
        BrickLinkBlockedError,
        fetch_minifigs_by_article,
        parse_catalog_list_page,
        _fetch_text,
        CATALOG_LIST_URL,
    )
    import aiohttp

    article = article.strip().lower()
    print(f"=== BrickLink probe article={article!r} ===")
    try:
        async with aiohttp.ClientSession() as session:
            html = await _fetch_text(
                session,
                CATALOG_LIST_URL,
                {"catType": "M", "q": article, "pageSize": 30, "pg": 1},
            )
            batch = parse_catalog_list_page(html, article)
            print(f"search page: html={len(html)} bytes, parsed={len(batch)}")
            for row in batch[:8]:
                print(" ", row)

        records, cat, label = await fetch_minifigs_by_article(article, "Ninjago")
        print(f"full fetch: {len(records)} items, cat={cat}, label={label}")
        for row in records[:10]:
            print(" ", row)
        if not records:
            print("FAIL: 0 items")
            return 1
        print("OK")
        return 0
    except BrickLinkBlockedError as exc:
        print("BLOCKED:", exc)
        return 2
    except Exception as exc:
        print("ERROR:", type(exc).__name__, exc)
        return 3


if __name__ == "__main__":
    art = sys.argv[1] if len(sys.argv) > 1 else "njo"
    raise SystemExit(asyncio.run(main(art)))
