from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.crud.wishlist_crud import (
    create_wishlist_item,
    delete_wishlist_item,
    get_wishlist_item,
    list_user_wishlist,
    update_wishlist_item,
)
from app.schemas.wishlist_schema import (
    WishlistItemCreate,
    WishlistItemRead,
    WishlistItemUpdate,
)

router = APIRouter(prefix="/wishlist", tags=["wishlist"])


@router.get(
    "/user/{user_id}/",
    response_model=List[WishlistItemRead],
    status_code=status.HTTP_200_OK,
)
def read_user_wishlist(user_id: int, db: Session = Depends(get_db)):
    return list_user_wishlist(db, user_id)


@router.get(
    "/user/{user_id}/{item_id}",
    response_model=WishlistItemRead,
    status_code=status.HTTP_200_OK,
)
def read_wishlist_item(user_id: int, item_id: int, db: Session = Depends(get_db)):
    try:
        return get_wishlist_item(db, item_id, user_id)
    except NoResultFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/user/",
    response_model=WishlistItemRead,
    status_code=status.HTTP_201_CREATED,
)
def create_item(data: WishlistItemCreate, db: Session = Depends(get_db)):
    return create_wishlist_item(db, data)


@router.patch(
    "/user/{item_id}",
    response_model=WishlistItemRead,
    status_code=status.HTTP_200_OK,
)
def patch_item(
    item_id: int,
    data: WishlistItemUpdate,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    try:
        return update_wishlist_item(db, item_id, user_id, data)
    except NoResultFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete(
    "/user/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_item(
    item_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    try:
        delete_wishlist_item(db, item_id, user_id)
    except NoResultFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
