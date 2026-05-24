from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import NoResultFound

from app.core.db import get_db
from app.schemas.user_schema import (
    UserCreate,
    UserRead,
    UserRoleUpdate,
    UserSettingsRead,
    UserSettingsUpdate,
    UserUpdate,
)
from app.crud.user_crud import (
    create_user,
    get_user,
    list_users,
    update_user,
    delete_user,
    add_group_to_user,
    remove_group_from_user,
    set_user_role,
)
from app.models.user_model import User, UserSettings

router = APIRouter(prefix="/users", tags=["users"])

@router.post(
    "/",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED
)
def create_user_endpoint(data: UserCreate, db: Session = Depends(get_db)):
    try:
        return create_user(db, data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/",
    response_model=List[UserRead],
    status_code=status.HTTP_200_OK
)
def read_all_users(db: Session = Depends(get_db)):
    return list_users(db)

@router.get(
    "/telegram/{telegram_username}",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
)
def read_user_by_telegram(telegram_username: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_username == telegram_username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    from app.crud.user_crud import _bootstrap_role

    if _bootstrap_role(telegram_username, None) == "admin" and user.role != "admin":
        user.role = "admin"
        db.commit()
        db.refresh(user)
    return user


@router.get(
    "/{user_id}",
    response_model=UserRead,
    status_code=status.HTTP_200_OK
)
def read_user(user_id: int, db: Session = Depends(get_db)):
    try:
        return get_user(db, user_id)
    except NoResultFound as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.patch(
    "/{user_id}/role",
    response_model=UserRead,
)
def update_user_role_endpoint(
    user_id: int,
    data: UserRoleUpdate,
    db: Session = Depends(get_db),
):
    try:
        return set_user_role(db, user_id, data.role)
    except NoResultFound as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch(
    "/{user_id}",
    response_model=UserRead
)
def update_user_endpoint(user_id: int, data: UserUpdate, db: Session = Depends(get_db)):
    try:
        return update_user(db, user_id, data)
    except NoResultFound as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_user_endpoint(user_id: int, db: Session = Depends(get_db)):
    try:
        delete_user(db, user_id)
    except NoResultFound as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post(
    "/{user_id}/groups/{group_id}",
    response_model=UserRead
)
def assign_group(user_id: int, group_id: int, db: Session = Depends(get_db)):
    try:
        return add_group_to_user(db, user_id, group_id)
    except NoResultFound as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete(
    "/{user_id}/groups/{group_id}",
    response_model=UserRead
)
def unassign_group(user_id: int, group_id: int, db: Session = Depends(get_db)):
    try:
        return remove_group_from_user(db, user_id, group_id)
    except NoResultFound as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.put("/update_user_settings/", response_model=UserRead)
async def update_user_settings(
    new_settings: UserSettingsUpdate,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == new_settings.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    settings = db.query(UserSettings).filter(UserSettings.user_id == user.id).first()

    if not settings:
        settings = UserSettings(user_id=user.id)
        db.add(settings)

    # Обновляем только те поля, которые явно переданы (не None)
    for field, value in new_settings.dict(exclude={"user_id"}).items():
        if value is not None:
            setattr(settings, field, value)

    db.commit()
    db.refresh(user)
    return user

@router.get("/get_user_settings/{telegram_username}", response_model=UserSettingsRead)
async def get_user_settings(
    telegram_username: str,
    db: Session = Depends(get_db),
):
    print(telegram_username)
    user = db.query(User).filter(User.telegram_username == telegram_username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    settings = db.query(UserSettings).filter(UserSettings.user_id == user.id).first()

    if not settings:
        settings = UserSettings(user_id=user.id)
        db.add(settings)
        db.commit()
        db.refresh(settings)

    return UserSettingsRead(
        id=settings.id,
        user_id=user.id,
        request_price_buy=settings.request_price_buy,
        request_price_sale=settings.request_price_sale,
        is_seller=settings.is_seller,
        show_description=settings.show_description,
        auto_fill_dates=settings.auto_fill_dates,
    )
