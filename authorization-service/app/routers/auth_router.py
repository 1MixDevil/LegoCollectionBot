from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.schemas.user_schema import UserCreate, UserRead
from app.crud.user_crud import get_user_by_username, create_user
from app.core.db import get_db

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/signup/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def signup(user_in: UserCreate, db: Session = Depends(get_db)):
    if get_user_by_username(db, user_in.telegram_username):
        raise HTTPException(status_code=400, detail="Telegram username already registered")
    user = create_user(db, user_in)
    return user
