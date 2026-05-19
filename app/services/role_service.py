from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.repositories.role_repository import (
    create_role,
      delete_role,
        get_role_by_id,
          get_roles,
            update_role
)
from app.schemas.role_schema import RoleCreate, RoleUpdate

def create_role_service(db: Session, role_data: RoleCreate):
    roles = get_roles(db)

    for rol in roles:
        if rol.name == role_data.name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Role name already exists"
            )
    return create_role(db, role_data)

def get_roles_service(db: Session):
    return get_roles(db)

def get_role_by_id_service(db: Session, role_id: int):
    role = get_role_by_id(db, role_id)

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    return role

def update_role_service(db: Session, role_id: int, role_data: RoleUpdate):
    role = update_role(db, role_id, role_data)

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    return role

def delete_role_service(db: Session, role_id: int):
    role = delete_role(db, role_id)

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    return {"message": "Role deleted successfully"}