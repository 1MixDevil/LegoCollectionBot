# app/crud/permissions_crud.py
from sqlalchemy.orm import Session
from app.models.permissions_model import PermissionName, UserPermission
from app.schemas.permissions_schema import PermissionCreate

def create_permission(db: Session, perm_in: PermissionCreate) -> PermissionName:
    db_perm = PermissionName(name=perm_in.name)
    db.add(db_perm)
    db.commit()
    db.refresh(db_perm)
    return db_perm

def assign_permission(db: Session, user_id: int, perm_id: int) -> UserPermission:
    up = UserPermission(user_id=user_id, permission_id=perm_id)
    db.add(up)
    db.commit()
    db.refresh(up)
    return up

def list_user_permissions(db: Session, user_id: int) -> list[PermissionName]:
    return (
        db.query(PermissionName)
        .join(UserPermission, PermissionName.id == UserPermission.permission_id)
        .filter(UserPermission.user_id == user_id)
        .all()
    )
