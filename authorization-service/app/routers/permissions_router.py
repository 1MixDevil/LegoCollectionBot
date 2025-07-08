# app/routers/permissions_router.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.schemas.permissions_schema import PermissionCreate, PermissionRead
from app.crud.permissions_crud import create_permission, assign_permission, list_user_permissions
from app.core.db import get_db

router = APIRouter(prefix="/permissions", tags=["permissions"])

@router.post("/", response_model=PermissionRead)
def add_permission(perm: PermissionCreate, db: Session = Depends(get_db)):
    return create_permission(db, perm)

@router.post("/assign")
def assign(user_id: int, perm_id: int, db: Session = Depends(get_db)):
    return assign_permission(db, user_id, perm_id)

@router.get("/user/{user_id}", response_model=list[PermissionRead])
def get_user_perms(user_id: int, db: Session = Depends(get_db)):
    return list_user_permissions(db, user_id)
