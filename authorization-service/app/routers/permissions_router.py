# app/routers/permissions_router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.schemas.permissions_schema import PermissionCreate, PermissionRead
from app.crud.permissions_crud import (
    create_permissions_name
)
from app.core.db import get_db

router = APIRouter(prefix="/permissions", tags=["permissions"])



@router.post(
        "/createPermissionRule/",
        response_model=PermissionRead,
        status_code=status.HTTP_201_CREATED
)
def create_permissions(
    perm: PermissionCreate,
    db: Session = Depends(get_db)
):
    try:
        create_permissions_name(db, perm)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

