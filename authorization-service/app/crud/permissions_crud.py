from typing import List
from sqlalchemy.orm import Session
from sqlalchemy.exc import NoResultFound

from app.models.permissions_model import PermissionName, PermissionGroup
from app.schemas.permissions_schema import (
    PermissionCreate,
    PermissionRename,
    PermissionGroupCreate,
)

# — PermissionName — 

def create_permission(db: Session, item: PermissionCreate) -> PermissionName:
    perm = PermissionName(**item.dict())
    db.add(perm)
    db.commit()
    db.refresh(perm)
    return perm

def delete_permission(db: Session, perm_id: int) -> None:
    perm = db.query(PermissionName).get(perm_id)
    if not perm:
        raise NoResultFound(f"Permission with id={perm_id} not found")
    db.delete(perm)
    db.commit()

def rename_permission(db: Session, perm_id: int, data: PermissionRename) -> PermissionName:
    perm = db.query(PermissionName).get(perm_id)
    if not perm:
        raise NoResultFound(f"Permission with id={perm_id} not found")
    perm.name = data.name
    db.commit()
    db.refresh(perm)
    return perm

def list_permissions(db: Session) -> List[PermissionName]:
    """
    Возвращает все записи PermissionName
    """
    return db.query(PermissionName).all()

# — PermissionGroup — 

def create_group(db: Session, item: PermissionGroupCreate) -> PermissionGroup:
    group = PermissionGroup(**item.dict())
    db.add(group)
    db.commit()
    db.refresh(group)
    return group

def get_group(db: Session, group_id: int) -> PermissionGroup:
    group = db.query(PermissionGroup).get(group_id)
    if not group:
        raise NoResultFound(f"Group with id={group_id} not found")
    return group

def add_permission_to_group(db: Session, group_id: int, perm_id: int) -> PermissionGroup:
    group = get_group(db, group_id)
    perm = db.query(PermissionName).get(perm_id)
    if not perm:
        raise NoResultFound(f"Permission with id={perm_id} not found")
    group.permissions.append(perm)
    db.commit()
    db.refresh(group)
    return group

def remove_permission_from_group(db: Session, group_id: int, perm_id: int) -> PermissionGroup:
    group = get_group(db, group_id)
    perm = db.query(PermissionName).get(perm_id)
    if not perm or perm not in group.permissions:
        raise NoResultFound(f"Permission with id={perm_id} not in group {group_id}")
    group.permissions.remove(perm)
    db.commit()
    db.refresh(group)
    return group

def list_groups(db: Session) -> List[PermissionGroup]:
    """
    Возвращает все записи PermissionGroup
    """
    return db.query(PermissionGroup).all()
