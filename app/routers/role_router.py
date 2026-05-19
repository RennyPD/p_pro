from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends
from app.db.Session import get_db

from app.services.role_service import (
    create_role_service,
    get_roles_service,
    get_role_by_id_service,
    update_role_service,
    delete_role_service
)
from app.schemas.role_schema import RoleCreate, RoleUpdate, RoleOut

router = APIRouter(
    prefix="/roles",
    tags=["roles"]
)

@router.post("/", response_model=RoleOut)
def create_role(
    role_data: RoleCreate,
    db: Session = Depends(get_db)
):
    return create_role_service(db, role_data)

@router.get("/", response_model=list[RoleOut])
def get_roles(
    db: Session = Depends(get_db)
):
    return get_roles_service(db)

@router.get("/{role_id}", response_model=RoleOut)
def get_role_by_id(
    role_id: int,
    db: Session = Depends(get_db)
):
    return get_role_by_id_service(db, role_id)

@router.put("/{role_id}", response_model=RoleOut)
def update_role(
    role_id: int,
    role_data: RoleUpdate,
    db: Session = Depends(get_db)
):
    return update_role_service(db, role_id, role_data)

@router.delete("/{role_id}")
def delete_role(
    role_id: int,
    db: Session = Depends(get_db)
):
    return delete_role_service(db, role_id)