from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from app.models.figures_model import WishlistItem
from app.schemas.wishlist_schema import WishlistItemCreate, WishlistItemUpdate


def list_user_wishlist(db: Session, user_id: int) -> list[WishlistItem]:
    return (
        db.query(WishlistItem)
        .filter(WishlistItem.user_id == user_id)
        .order_by(WishlistItem.id.desc())
        .all()
    )


def get_wishlist_item(db: Session, item_id: int, user_id: int) -> WishlistItem:
    item = (
        db.query(WishlistItem)
        .filter(WishlistItem.id == item_id, WishlistItem.user_id == user_id)
        .one_or_none()
    )
    if not item:
        raise NoResultFound(f"Wishlist item id={item_id} not found for user {user_id}")
    return item


def create_wishlist_item(db: Session, data: WishlistItemCreate) -> WishlistItem:
    payload = data.dict()
    if payload.get("bricklink_id"):
        payload["bricklink_id"] = payload["bricklink_id"].lower()
    item = WishlistItem(**payload)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_wishlist_item(
    db: Session,
    item_id: int,
    user_id: int,
    data: WishlistItemUpdate,
) -> WishlistItem:
    item = get_wishlist_item(db, item_id, user_id)
    for field, val in data.dict(exclude_none=True).items():
        if field == "bricklink_id" and val:
            val = str(val).lower()
        setattr(item, field, val)
    db.commit()
    db.refresh(item)
    return item


def delete_wishlist_item(db: Session, item_id: int, user_id: int) -> None:
    item = get_wishlist_item(db, item_id, user_id)
    db.delete(item)
    db.commit()
