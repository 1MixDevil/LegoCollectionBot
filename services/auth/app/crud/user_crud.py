from typing import List
from sqlalchemy.orm import Session
from sqlalchemy.exc import NoResultFound
from fastapi import HTTPException, Depends
from app.models.permissions_model import PermissionGroup
from app.models.user_model import User
from app.schemas.user_schema import UserCreate, UserUpdate

# Создать пользователя
def create_user(db: Session, data: UserCreate) -> User:
    # Проверяем, существует ли пользователь с таким telegram_username
    existing_user = db.query(User).filter(User.telegram_username == data.telegram_username).first()  # Замените `User` на название вашей модели User

    if existing_user:
        raise HTTPException(status_code=400, detail="User with this telegram_username already exists")

    # Проверяем, существует ли пользователь с таким username
    if data.username:
        existing_user_by_username = db.query(User).filter(User.username == data.username).first()
        if existing_user_by_username:
            raise HTTPException(status_code=400, detail="User with this username already exists")

    user = User(**data.dict(exclude_none=True))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

# Получить одного
def get_user(db: Session, user_id: int) -> User:
    user = db.query(User).get(user_id)
    if not user:
        raise NoResultFound(f"User with id={user_id} not found")
    return user

# Список всех
def list_users(db: Session) -> List[User]:
    return db.query(User).all()

# Обновить
def update_user(db: Session, user_id: int, data: UserUpdate) -> User:
    user = get_user(db, user_id)
    for field, value in data.dict(exclude_none=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user

# Удалить
def delete_user(db: Session, user_id: int) -> None:
    user = get_user(db, user_id)
    db.delete(user)
    db.commit()

# Добавить группу прав
def add_group_to_user(db: Session, user_id: int, group_id: int) -> User:
    user = get_user(db, user_id)
    group = db.query(PermissionGroup).get(group_id)
    if not group:
        raise NoResultFound(f"Group with id={group_id} not found")
    user.permission_groups.append(group)
    db.commit()
    db.refresh(user)
    return user

# Удалить группу прав у пользователя
def remove_group_from_user(db: Session, user_id: int, group_id: int) -> User:
    user = get_user(db, user_id)
    group = db.query(PermissionGroup).get(group_id)
    if not group or group not in user.permission_groups:
        raise NoResultFound(f"Group with id={group_id} not assigned to user {user_id}")
    user.permission_groups.remove(group)
    db.commit()
    db.refresh(user)
    return user
