from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.bot_settings_model import BotSetting
from app.schemas.bot_settings_schema import (
    CollageLimitsRead,
    CollageLimitsUpdate,
    WatermarkTextRead,
    WatermarkTextUpdate,
)

router = APIRouter(prefix="/bot-settings", tags=["bot-settings"])

WATERMARK_KEY = "collage_watermark_text"

LIMIT_DEFAULTS = {
    "collage_batch_size": "40",
    "collage_force_batch_above": "40",
    "tierlist_max_member": "80",
    "tierlist_max_premium": "150",
    "tierlist_max_admin": "500",
    "max_serials_per_request": "50",
}


def _get_or_create(db: Session, key: str, default: str = "") -> BotSetting:
    row = db.query(BotSetting).filter(BotSetting.key == key).first()
    if row is None:
        row = BotSetting(key=key, value=default)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def _read_limits(db: Session) -> CollageLimitsRead:
    data: dict[str, int] = {}
    for key, default in LIMIT_DEFAULTS.items():
        row = _get_or_create(db, key, default)
        try:
            data[key] = max(1, int(row.value or default))
        except ValueError:
            data[key] = int(default)
    return CollageLimitsRead(**data)


@router.get("/collage_watermark", response_model=WatermarkTextRead)
def get_collage_watermark(db: Session = Depends(get_db)):
    row = _get_or_create(db, WATERMARK_KEY, "")
    return WatermarkTextRead(text=row.value or "")


@router.put("/collage_watermark", response_model=WatermarkTextRead)
def set_collage_watermark(body: WatermarkTextUpdate, db: Session = Depends(get_db)):
    row = _get_or_create(db, WATERMARK_KEY, "")
    row.value = (body.text or "").strip()[:200]
    db.commit()
    db.refresh(row)
    return WatermarkTextRead(text=row.value or "")


@router.get("/collage_limits", response_model=CollageLimitsRead)
def get_collage_limits(db: Session = Depends(get_db)):
    return _read_limits(db)


@router.put("/collage_limits", response_model=CollageLimitsRead)
def set_collage_limits(body: CollageLimitsUpdate, db: Session = Depends(get_db)):
    payload = body.dict(exclude_unset=True)
    for key, value in payload.items():
        if key not in LIMIT_DEFAULTS or value is None:
            continue
        row = _get_or_create(db, key, LIMIT_DEFAULTS[key])
        row.value = str(int(value))
    db.commit()
    return _read_limits(db)
