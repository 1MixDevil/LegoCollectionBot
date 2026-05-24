"""
Синхронизация каталога figure.figures из внешних источников.
"""

from __future__ import annotations

import logging
import os
import time
from typing import List, Set, Tuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.business.bricklink_catalog_list import (
    GENERIC_THEME_NAMES,
    discover_series_metadata,
    fetch_minifigs_by_article,
)
from app.business.rebrickable_client import get_catalog_source
from app.models.figures_model import CollectType, Figure

logger = logging.getLogger("CatalogUpdater")

LOCK_MAX_AGE_SEC = int(os.getenv("CATALOG_LOCK_MAX_AGE_SEC", str(10 * 60)))


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _try_acquire_lock(lock_file: str) -> tuple[bool, int]:
    """
    True — lock взят.
    False — занят; возвращает возраст lock в секундах.
  """
    if os.path.exists(lock_file):
        age = int(time.time() - os.path.getmtime(lock_file))
        stale = False
        try:
            with open(lock_file, encoding="utf-8") as f:
                raw = f.read().strip()
            if raw.isdigit() and not _pid_alive(int(raw)):
                logger.warning("Снят lock: процесс %s уже не работает", raw)
                stale = True
        except OSError:
            stale = True

        if age >= LOCK_MAX_AGE_SEC:
            logger.warning("Снят lock по таймауту (%s сек)", age)
            stale = True

        if stale:
            os.remove(lock_file)
        else:
            return False, age

    with open(lock_file, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))
    return True, 0


def insert_figures(
    db: Session,
    ct: CollectType,
    records: List[Tuple[str, str]],
) -> int:
    if not records:
        return 0

    ids = [rid for rid, _ in records]
    existing: Set[str] = {
        row[0]
        for row in db.query(Figure.bricklink_id).filter(Figure.bricklink_id.in_(ids))
    }
    new = [(rid, name) for rid, name in records if rid not in existing]

    if not new:
        logger.info("[%s] Все %s записей уже в БД", ct.article, len(records))
        return 0

    objs = [
        Figure(bricklink_id=rid, name=name, type_collected_id=ct.id)
        for rid, name in new
    ]
    try:
        db.bulk_save_objects(objs)
        db.commit()
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
        return count


async def ensure_collect_type(db: Session, article: str) -> CollectType:
    """
    Возвращает type_of_collect для префикса; создаёт запись, если серия есть на BrickLink.
    """
    article = article.strip().lower()
    ct = db.query(CollectType).filter_by(article=article).first()
    if ct:
        return ct

    meta = await discover_series_metadata(article)
    if not meta:
        raise ValueError(
            f"Серия «{article}» не найдена на BrickLink. "
            "Проверьте префикс (например lor, sw, hp, sim)."
        )

    ct = CollectType(
        article=article,
        name=str(meta["name"]),
        pad_len=int(meta["pad_len"]),
        bricklink_cat_string=(str(meta.get("cat_string") or "").strip() or None),
    )
    db.add(ct)
    db.commit()
    db.refresh(ct)
    logger.info(
        "Создан type_of_collect: article=%s name=%s pad_len=%s",
        article,
        ct.name,
        ct.pad_len,
    )
    return ct


async def sync_from_bricklink_catalog(db: Session, article: str) -> dict:
    """
    Массовое наполнение каталога из BrickLink catalogList (без cookies).
    Rebrickable не использует артикулы BrickLink (sw0001a) — только fig-XXXXX.
    """
    article = article.strip().lower()
    ct = await ensure_collect_type(db, article)

    existing_count = (
        db.query(Figure).filter(Figure.type_collected_id == ct.id).count()
    )

    logger.info(
        "=== BRICKLINK CATALOG LIST | article=%s | в БД: %s ===",
        article,
        existing_count,
    )

    try:
        records, cat_used, cat_label = await fetch_minifigs_by_article(
            article,
            ct.name,
            bricklink_cat=getattr(ct, "bricklink_cat_string", None) or None,
        )
        if cat_used:
            ct.bricklink_cat_string = cat_used
            if cat_label and ct.name.strip().lower() in GENERIC_THEME_NAMES:
                ct.name = cat_label
            db.commit()
    except RuntimeError as exc:
        return {
            "added": 0,
            "article": article,
            "existing_before": existing_count,
            "scanned_found": 0,
            "checked_base": 0,
            "miss_reasons": {"rate_limit": 1},
            "status": "blocked",
            "source": "bricklink_catalog",
            "message": str(exc),
        }

    added = insert_figures(db, ct, records)

    if not records:
        message = (
            f"BrickLink: в категории «{ct.name}» не найдено минифигурок с префиксом "
            f"{article}. Проверьте article и name в type_of_collect."
        )
        status = "no_items"
    elif added:
        message = (
            f"BrickLink: загружено {len(records)} минифигурок серии {article}, "
            f"новых в БД: {added}"
        )
        status = "ok"
    else:
        message = (
            f"BrickLink: в каталоге {len(records)} шт., все уже были в БД"
        )
        status = "no_new_items"

    result = {
        "added": added,
        "article": article,
        "existing_before": existing_count,
        "scanned_found": len(records),
        "checked_base": len(records),
        "miss_reasons": {},
        "status": status,
        "source": "bricklink_catalog",
        "message": message,
    }
    logger.info("=== BRICKLINK CATALOG LIST DONE | %s ===", result)
    return result


async def sync_from_rebrickable(db: Session, article: str) -> dict:
    """
    При CATALOG_DATA_SOURCE=rebrickable массовый /update идёт через BrickLink list:
    API Rebrickable не содержит артикулов sw/hp (только fig-000001).
    """
    return await sync_from_bricklink_catalog(db, article)


def _resolve_collect_type(db: Session, set_num: str) -> CollectType | None:
    """Подбирает серию по префиксу set_num (sw0001a → sw)."""
    prefix_match = None
    for ct in db.query(CollectType).all():
        if set_num.startswith(ct.article.lower()):
            if prefix_match is None or len(ct.article) > len(prefix_match.article):
                prefix_match = ct
    return prefix_match


async def fetch_and_insert_one(db: Session, set_num: str) -> bool:
    """Подтянуть одну фигурку по BrickLink ID, если её ещё нет в БД."""
    from aiohttp import ClientSession

    from app.business.parser import FastFigureUpdater

    set_num = set_num.strip().lower()
    if db.query(Figure).filter_by(bricklink_id=set_num).first():
        return True

    ct = _resolve_collect_type(db, set_num)
    if not ct:
        return False

    async with ClientSession() as session:
        result = await FastFigureUpdater.fetch_name(session, set_num)
    if not result.name:
        return False

    insert_figures(db, ct, [(set_num, result.name)])
    return True


async def update_catalog(
    db: Session,
    article: str,
    max_miss: int = 50,
    lock: bool = True,
) -> dict:
    """Точка входа для /update — по умолчанию Rebrickable."""
    article = article.strip().lower()
    source = get_catalog_source()

    lock_file = f"/tmp/catalog_{article}.lock"
    if lock:
        acquired, lock_age = _try_acquire_lock(lock_file)
        if not acquired:
            return {
                "added": 0,
                "status": "locked",
                "article": article,
                "lock_age_sec": lock_age,
                "message": (
                    "Подождите завершения предыдущего обновления или перезапустите "
                    "collection-service (снимет lock)."
                ),
            }

    try:
        if source == "rebrickable":
            return await sync_from_rebrickable(db, article)

        from app.business.parser import FastFigureUpdater

        return await FastFigureUpdater.update(db, article, max_miss=max_miss, lock=False)
    finally:
        if lock and os.path.exists(lock_file):
            os.remove(lock_file)
