from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.bot_settings_model import BotSetting
from app.schemas.bot_settings_schema import WatermarkTextRead, WatermarkTextUpdate

router = APIRouter(prefix="/bot-settings", tags=["bot-settings"])

WATERMARK_KEY = "collage_watermark_text"


def _get_or_create(db: Session, key: str) -> BotSetting:
    row = db.query(BotSetting).filter(BotSetting.key == key).first()
    if row is None:
        row = BotSetting(key=key, value="")
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


@router.get("/collage_watermark", response_model=WatermarkTextRead)
def get_collage_watermark(db: Session = Depends(get_db)):
    row = _get_or_create(db, WATERMARK_KEY)
    return WatermarkTextRead(text=row.value or "")


@router.put("/collage_watermark", response_model=WatermarkTextRead)
def set_collage_watermark(body: WatermarkTextUpdate, db: Session = Depends(get_db)):
    row = _get_or_create(db, WATERMARK_KEY)
    row.value = (body.text or "").strip()[:200]
    db.commit()
    db.refresh(row)
    return WatermarkTextRead(text=row.value or "")
