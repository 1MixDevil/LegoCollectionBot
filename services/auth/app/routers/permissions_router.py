from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import NoResultFound

from app.core.db import get_db
from app.schemas.permissions_schema import (
    PermissionCreate,
    PermissionRead,
    PermissionRename,
    PermissionGroupCreate,
    PermissionGroupRead,
)
from app.crud.permissions_crud import (
    create_permission,
    delete_permission,
    rename_permission,
    create_group,
    get_group,
    add_permission_to_group,
    remove_permission_from_group,
    list_permissions,
    list_groups,
)

router = APIRouter(prefix="/permissions", tags=["permissions"])

# — CRUD для PermissionName — 

@router.post(
    "/rules/",
    response_model=PermissionRead,
    status_code=status.HTTP_201_CREATED
)
def create_rule(perm: PermissionCreate, db: Session = Depends(get_db)):
    try:
        return create_permission(db, perm)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete(
    "/rules/{perm_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_rule(perm_id: int, db: Session = Depends(get_db)):
    try:
        delete_permission(db, perm_id)
    except NoResultFound as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.patch(
    "/rules/{perm_id}",
    response_model=PermissionRead
)
def rename_rule(perm_id: int, data: PermissionRename, db: Session = Depends(get_db)):
    try:
        return rename_permission(db, perm_id, data)
    except NoResultFound as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get(
    "/rules/",
    response_model=List[PermissionRead],
    status_code=status.HTTP_200_OK
)
def read_all_rules(db: Session = Depends(get_db)):
    """
    Показать все правила (PermissionName)
    """
    return list_permissions(db)


# — CRUD для PermissionGroup — 

@router.post(
    "/groups/",
    response_model=PermissionGroupRead,
    status_code=status.HTTP_201_CREATED
)
def create_permission_group(
    group: PermissionGroupCreate,
    db: Session = Depends(get_db)
):
    try:
        return create_group(db, group)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/groups/{group_id}",
    response_model=PermissionGroupRead
)
def read_permission_group(group_id: int, db: Session = Depends(get_db)):
    try:
        return get_group(db, group_id)
    except NoResultFound as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post(
    "/groups/{group_id}/rules/{perm_id}",
    response_model=PermissionGroupRead
)
def assign_rule_to_group(group_id: int, perm_id: int, db: Session = Depends(get_db)):
    try:
        return add_permission_to_group(db, group_id, perm_id)
    except NoResultFound as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete(
    "/groups/{group_id}/rules/{perm_id}",
    response_model=PermissionGroupRead
)
def remove_rule_from_group(group_id: int, perm_id: int, db: Session = Depends(get_db)):
    try:
        return remove_permission_from_group(db, group_id, perm_id)
    except NoResultFound as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get(
    "/groups/",
    response_model=List[PermissionGroupRead],
    status_code=status.HTTP_200_OK
)
def read_all_groups(db: Session = Depends(get_db)):
    """
    Показать все группы (PermissionGroup)
    """
    return list_groups(db)