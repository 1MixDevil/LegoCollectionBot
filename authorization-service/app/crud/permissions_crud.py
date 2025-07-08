# app/crud/permissions_crud.py
from app.models.permissions_model import PermissionName, PermissionGroup
from app.models.associations import user_permission_group
from app.schemas.permissions_schema import PermissionCreate, PermissionRead
from sqlalchemy.orm import Session

def create_permissions_name(
        db: Session,
        item: PermissionCreate
    ) -> PermissionName:
    """
        Создаёт новое право доступа
    """
    permissions_item = PermissionName(**item.dict())
    db.add(permissions_item)
    db.commit()
    db.refresh(permissions_item)
    return permissions_item
