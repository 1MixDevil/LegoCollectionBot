from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import NoResultFound

from app.core.db import get_db
from app.schemas.user_schema import UserCreate, UserRead, UserUpdate
from app.crud.user_crud import (
    create_user,
    get_user,
    list_users,
    update_user,
    delete_user,
    add_group_to_user,
    remove_group_from_user,
)

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
