from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.role_repository import (
    create_role,
    delete_role,
    get_role_by_id,
    get_roles,
    update_role,
)
from app.schemas.role_schema import RoleCreate, RoleUpdate
from app.services.governance_workflow import lock_governance

SYSTEM_ROLES = {"admin", "teacher", "student", "guardian"}


def create_role_service(db: Session, role_data: RoleCreate):
    lock_governance(db)
    code = role_data.name.strip().casefold()
    if not code or len(code) > 50:
        raise HTTPException(422, "Escribe un código de rol de 1 a 50 caracteres")
    roles = get_roles(db)

    for rol in roles:
        if rol.name.casefold() == code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Ya existe un rol con ese nombre"
            )
    return create_role(db, role_data.model_copy(update={"name": code}))


def get_roles_service(db: Session):
    return get_roles(db)


def get_role_by_id_service(db: Session, role_id: int):
    role = get_role_by_id(db, role_id)

    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No se encontró el rol")

    return role


def update_role_service(db: Session, role_id: int, role_data: RoleUpdate):
    lock_governance(db)
    current = get_role_by_id_service(db, role_id)
    if "name" in role_data.model_fields_set and role_data.name != current.name:
        raise HTTPException(409, "El código del rol es fijo. Cambia su etiqueta visible")
    if "description" in role_data.model_fields_set and role_data.description is None:
        raise HTTPException(422, "Escribe una descripción para el rol")
    role = update_role(db, role_id, role_data)

    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No se encontró el rol")

    return role


def delete_role_service(db: Session, role_id: int):
    lock_governance(db)
    current = get_role_by_id_service(db, role_id)
    if current.name.casefold() in SYSTEM_ROLES or current.users:
        raise HTTPException(
            409, "Conserva los roles del sistema y los roles con cuentas vinculadas"
        )
    role = delete_role(db, role_id)

    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No se encontró el rol")

    return {"message": "Role deleted successfully"}
