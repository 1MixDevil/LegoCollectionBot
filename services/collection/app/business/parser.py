import asyncio
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import List, Optional, Set, Tuple

import aiohttp
from aiohttp import ClientSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.business.bricklink_api import (
    BrickLinkAPIError,
    BrickLinkItemNotFound,
    api_credentials_configured,
    get_catalog_item,
    get_data_source,
)
from app.business.bricklink_client import (
    LEGACY_URL,
    V2_URL,
    build_headers,
    cookies_configured,
    load_bricklink_cookies,
    parse_catalog_html,
)
from app.models.figures_model import CollectType, Figure

logger = logging.getLogger("FastFigureUpdater")

LOCK_MAX_AGE_SEC = 30 * 60  # устаревший lock снимается автоматически


@dataclass
class FetchResult:
    name: Optional[str]
    http_status: int
    reason: str
    hint: str = ""


class FastFigureUpdater:
    FETCH_TIMEOUT = int(os.getenv("BRICKLINK_FETCH_TIMEOUT", "20"))
    REQUEST_DELAY = float(os.getenv("BRICKLINK_REQUEST_DELAY", "0.7"))
    CONCURRENCY = int(
        os.getenv("BRICKLINK_CONCURRENCY", "3" if cookies_configured() else "2")
    )

    @staticmethod
    def get_last_id(db: Session, article: str) -> Tuple[int, str, int]:
        """
        Возвращает (стартовый номер, суффикс, кол-во фигурок в БД для серии).
        Пустая БД → старт с 1 (sw0001, не sw0000).
        """
        ct = db.query(CollectType).filter_by(article=article).first()
        if not ct:
            raise ValueError(f"CollectType '{article}' не найден.")

        count = (
            db.query(Figure)
            .filter(Figure.type_collected_id == ct.id)
            .count()
        )
        last: Optional[Figure] = (
            db.query(Figure)
            .filter(Figure.type_collected_id == ct.id)
            .order_by(Figure.bricklink_id.desc())
            .first()
        )
        if not last:
            logger.info(
                "[%s] Каталог пуст — начнём с %s0001 (pad_len=%s), в БД: 0 шт.",
                article,
                article,
                ct.pad_len,
            )
            return 1, "", count

        raw = last.bricklink_id[len(article) :]
        match = re.match(r"(\d+)([a-z]?)", raw, re.IGNORECASE)
        if not match:
            logger.warning(
                "[%s] Неожиданный bricklink_id=%s — старт с 1",
                article,
                last.bricklink_id,
            )
            return 1, "", count

        num, suffix = int(match.group(1)), match.group(2).lower()
        start_num = num + 1
        logger.info(
            "[%s] Последняя в БД: %s → продолжим с %s%0*d, всего в БД: %s шт.",
            article,
            last.bricklink_id,
            article,
            start_num,
            ct.pad_len,
            count,
        )
        return start_num, "", count

    @staticmethod
    def _page_to_fetch(page, item_id: str, via: str) -> FetchResult:
        if page.ok and page.item:
            return FetchResult(
                page.item.name,
                page.http_status,
                f"found_{via}",
                page.item.year_released or "",
            )
        return FetchResult(
            None,
            page.http_status,
            page.reason,
            page.hint,
        )

    @staticmethod
    async def _fetch_via_api(item_id: str) -> FetchResult:
        try:
            item = await asyncio.to_thread(get_catalog_item, item_id)
            extra = item.year_released or ""
            return FetchResult(item.name, 200, "found_api", extra)
        except BrickLinkItemNotFound:
            return FetchResult(
                None, 404, "not_found", "Нет в каталоге BrickLink (API)"
            )
        except BrickLinkAPIError as exc:
            return FetchResult(None, 0, "api_error", str(exc))

    @staticmethod
    async def _fetch_via_scrape(session: ClientSession, item_id: str) -> FetchResult:
        item_id = item_id.strip().lower()
        headers = build_headers()
        cookies = load_bricklink_cookies()
        urls = [V2_URL.format(item_id=item_id), LEGACY_URL.format(item_id=item_id)]

        try:
            for idx, url in enumerate(urls):
                async with session.get(
                    url,
                    headers=headers,
                    cookies=cookies or None,
                ) as resp:
                    text = await resp.text()
                    status = resp.status

                if status != 200:
                    if idx == len(urls) - 1:
                        return FetchResult(
                            None, status, "http_error", f"HTTP {status}"
                        )
                    continue

                page = parse_catalog_html(text, item_id)
                page.url_used = url
                if page.ok:
                    return FastFigureUpdater._page_to_fetch(
                        page, item_id, "v2" if idx == 0 else "legacy"
                    )
                if page.reason == "not_found":
                    return FastFigureUpdater._page_to_fetch(page, item_id, "v2")
                if page.reason == "blocked_or_error" and idx < len(urls) - 1:
                    continue
                return FastFigureUpdater._page_to_fetch(
                    page, item_id, "v2" if idx == 0 else "legacy"
                )

            return FetchResult(None, 0, "network_error", "нет ответа")
        except Exception as exc:
            logger.warning("Ошибка запроса %s: %s", item_id, exc)
            return FetchResult(None, 0, "network_error", str(exc))
        finally:
            if FastFigureUpdater.REQUEST_DELAY > 0:
                await asyncio.sleep(FastFigureUpdater.REQUEST_DELAY)

    @staticmethod
    async def fetch_name(session: ClientSession, item_id: str) -> FetchResult:
        source = get_data_source()
        use_api = source == "api" or (source == "auto" and api_credentials_configured())

        if use_api:
            result = await FastFigureUpdater._fetch_via_api(item_id)
            if result.name or result.reason == "not_found":
                return result
            if source == "api":
                return result
            logger.warning(
                "API не ответил для %s (%s), пробуем HTML",
                item_id,
                result.hint,
            )

        if source == "scrape" or source == "auto":
            return await FastFigureUpdater._fetch_via_scrape(session, item_id)

        return FetchResult(
            None,
            0,
            "no_source",
            "Задайте BRICKLINK_* API ключи или BRICKLINK_COOKIES",
        )

    @staticmethod
    async def collect_figures(
        article: str,
        start_num: int,
        start_suffix: str,
        max_miss: int,
        max_suffix: int,
        pad_length: int = 4,
    ) -> Tuple[List[Tuple[str, str]], dict]:
        source = get_data_source()
        has_api = api_credentials_configured()
        has_cookies = cookies_configured()
        logger.info(
            "[%s] Сканирование: с %s%0*d, max_miss=%s, source=%s, api=%s, cookies=%s, "
            "delay=%.2fs",
            article,
            article,
            start_num,
            pad_length,
            max_miss,
            source,
            "да" if has_api else "нет",
            "да" if has_cookies else "нет",
            FastFigureUpdater.REQUEST_DELAY,
        )

        results: List[Tuple[str, str]] = []
        miss_num = 0
        num = start_num
        stats = {
            "checked_base": 0,
            "found": 0,
            "miss_reasons": {},
        }

        timeout = aiohttp.ClientTimeout(total=FastFigureUpdater.FETCH_TIMEOUT)
        connector = aiohttp.TCPConnector(limit=FastFigureUpdater.CONCURRENCY)

        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            while True:
                base_id = f"{article}{num:0{pad_length}d}"
                stats["checked_base"] += 1
                fetch = await FastFigureUpdater.fetch_name(session, base_id)

                if fetch.name:
                    logger.info(
                        "FOUND %-10s → %s (via %s)",
                        base_id,
                        fetch.name,
                        fetch.reason,
                    )
                    results.append((base_id, fetch.name))
                    stats["found"] += 1
                    miss_num = 0
                else:
                    stats["miss_reasons"][fetch.reason] = (
                        stats["miss_reasons"].get(fetch.reason, 0) + 1
                    )
                    logger.info(
                        "MISS  %-10s | http=%s | reason=%s | %s",
                        base_id,
                        fetch.http_status,
                        fetch.reason,
                        fetch.hint,
                    )
                    miss_num += 1
                    if miss_num >= max_miss:
                        logger.info(
                            "[%s] Остановка: %s подряд пустых базовых ID (max_miss=%s), "
                            "последний проверенный: %s",
                            article,
                            max_miss,
                            max_miss,
                            base_id,
                        )
                        break

                miss_suffix = 0
                suffix_char = "a"
                while miss_suffix < max_suffix:
                    suffixed_id = f"{article}{num:0{pad_length}d}{suffix_char}"
                    fetch_s = await FastFigureUpdater.fetch_name(session, suffixed_id)
                    if fetch_s.name:
                        logger.info(
                            "FOUND %-10s → %s (via %s)",
                            suffixed_id,
                            fetch_s.name,
                            fetch_s.reason,
                        )
                        results.append((suffixed_id, fetch_s.name))
                        stats["found"] += 1
                        miss_suffix = 0
                    else:
                        logger.debug(
                            "MISS  %-10s | reason=%s",
                            suffixed_id,
                            fetch_s.reason,
                        )
                        miss_suffix += 1
                    suffix_char = chr(ord(suffix_char) + 1)
                    await asyncio.sleep(0.1)

                num += 1

        logger.info(
            "[%s] Итог сканирования: проверено базовых ID=%s, найдено=%s, "
            "причины промахов=%s",
            article,
            stats["checked_base"],
            stats["found"],
            stats["miss_reasons"] or "—",
        )
        if stats["found"] == 0 and stats["miss_reasons"].get("blocked_or_error"):
            logger.error(
                "[%s] BrickLink: General Error. Добавьте BRICKLINK_COOKIES в .env "
                "(скопируйте из браузера после входа на bricklink.com).",
                article,
            )
        elif stats["found"] == 0 and stats["miss_reasons"].get("not_found"):
            logger.warning(
                "[%s] Все ID «не найдены» — возможно, неверный префикс или "
                "диапазон номеров для этой серии.",
                article,
            )

        return results, stats

    @staticmethod
    def insert_new_figures(db: Session, ct: CollectType, records: List[Tuple[str, str]]) -> int:
        if not records:
            logger.info("[%s] Нечего вставлять в БД.", ct.article)
            return 0

        ids = [record_id for record_id, _ in records]
        existing: Set[str] = {
            row[0]
            for row in db.query(Figure.bricklink_id).filter(Figure.bricklink_id.in_(ids))
        }
        new = [(rid, name) for rid, name in records if rid not in existing]
        logger.info(
            "[%s] К вставке: %s новых, %s уже были в БД",
            ct.article,
            len(new),
            len(existing),
        )

        if not new:
            return 0

        objs = [
            Figure(bricklink_id=rid, name=name, type_collected_id=ct.id)
            for rid, name in new
        ]
        try:
            db.bulk_save_objects(objs)
            db.commit()
            logger.info("[%s] Вставлено %s фигурок (bulk)", ct.article, len(objs))
            return len(objs)
        except IntegrityError:
            db.rollback()
            count = 0
            for obj in objs:
                try:
                    db.add(obj)
                    db.commit()
                    count += 1
                except IntegrityError:
                    db.rollback()
            logger.warning("[%s] Вставлено %s фигурок (по одной)", ct.article, count)
            return count

    @staticmethod
    async def update(
        db: Session,
        article: str,
        max_miss: int = 50,
        max_suffix: int = 2,
        lock: bool = True,
    ) -> dict:
        article = article.strip().lower()
        ct = db.query(CollectType).filter_by(article=article).first()
        if not ct:
            raise ValueError(f"CollectType '{article}' не найден")

        has_api = api_credentials_configured()
        has_cookies = cookies_configured()
        logger.info(
            "=== UPDATE START | article=%s | max_miss=%s | source=%s | api=%s | cookies=%s ===",
            article,
            max_miss,
            get_data_source(),
            "да" if has_api else "нет",
            "да" if has_cookies else "нет",
        )

        lock_file = f"/tmp/bricklink_{article}.lock"
        if lock:
            if os.path.exists(lock_file):
                age = time.time() - os.path.getmtime(lock_file)
                if age < LOCK_MAX_AGE_SEC:
                    logger.warning(
                        "Обновление %s уже выполняется (lock %.0f сек). "
                        "Подождите или перезапустите collection-service.",
                        article,
                        age,
                    )
                    return {
                        "added": 0,
                        "status": "locked",
                        "article": article,
                        "lock_age_sec": int(age),
                        "message": (
                            "Предыдущее обновление ещё идёт или зависло. "
                            "Подождите ~1 мин и повторите /update"
                        ),
                    }
                logger.warning(
                    "[%s] Снят устаревший lock-файл (возраст %.0f сек)",
                    article,
                    age,
                )
                os.remove(lock_file)
            open(lock_file, "w").close()

        try:
            start_num, start_suffix, existing_count = FastFigureUpdater.get_last_id(
                db, article
            )
            records, stats = await FastFigureUpdater.collect_figures(
                article,
                start_num,
                start_suffix,
                max_miss,
                max_suffix,
                ct.pad_len,
            )
            added = (
                FastFigureUpdater.insert_new_figures(db, ct, records)
                if records
                else 0
            )
            result = {
                "added": added,
                "article": article,
                "existing_before": existing_count,
                "scanned_found": len(records),
                "checked_base": stats["checked_base"],
                "miss_reasons": stats["miss_reasons"],
                "status": (
                    "ok"
                    if added
                    else "blocked"
                    if stats["miss_reasons"].get("blocked_or_error")
                    else "no_new_items"
                ),
                "message": "",
            }
            if result["status"] == "blocked":
                if not has_api and not has_cookies:
                    result["message"] = (
                        "Настройте официальный BrickLink API (рекомендуется, ключи "
                        "не протухают) или BRICKLINK_COOKIES — см. .env.example"
                    )
                elif not has_api:
                    result["message"] = (
                        "HTML+cookies не работают. Лучше один раз настроить "
                        "BRICKLINK_CONSUMER_KEY / TOKEN в .env (официальный API)."
                    )
                else:
                    result["message"] = (
                        "API вернул ошибки. Проверьте IP в настройках токена BrickLink "
                        "и лимит ~5000 запросов/день."
                    )
            logger.info("=== UPDATE DONE | %s ===", result)
            return result
        finally:
            if lock and os.path.exists(lock_file):
                os.remove(lock_file)
