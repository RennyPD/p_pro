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
from app.services.write_locks import lock_access

SYSTEM_ROLES = {"admin", "teacher", "student", "guardian"}


SCOPE_LINKS = {"own": "student_id", "linked": "guardian_id", "sections": "teacher_id"}


def ensure_scope_allowed(actor, scope: str) -> None:
    """Nobody creates or widens a role to a broader data scope than their own."""
    from app.auth import role_scope

    if actor is not None and scope == "institution" and role_scope(actor) != "institution":
        raise HTTPException(403, "No puedes crear roles con alcance institucional")


def ensure_members_fit_scope(role, scope: str) -> None:
    """Accounts already in the role must be linked to the person the scope needs."""
    field = SCOPE_LINKS.get(scope)
    for user in role.users:
        linked = {key: getattr(user, key) for key in ("student_id", "guardian_id", "teacher_id")}
        if field and not linked[field]:
            raise HTTPException(
                409,
                "Hay cuentas en este rol sin la persona vinculada que exige ese alcance",
            )
        if scope == "institution" and (linked["student_id"] or linked["guardian_id"]):
            raise HTTPException(
                409, "Un rol institucional no puede tener cuentas de estudiantes o tutores"
            )


def create_role_service(db: Session, role_data: RoleCreate, actor=None):
    lock_access(db)
    if "scope" not in role_data.model_fields_set:
        # Re-creating a built-in role (teacher, student...) keeps its usual scope.
        from app.permissions import default_scope

        role_data = role_data.model_copy(update={"scope": default_scope(role_data.name)})
    ensure_scope_allowed(actor, role_data.scope)
    code = role_data.name.strip().casefold()
    if not code or len(code) > 50:
        raise HTTPException(422, "Escribe un código de rol de 1 a 50 caracteres")
    roles = get_roles(db)

    for rol in roles:
        if rol.name.casefold() == code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Ya existe un rol con ese nombre"
            )
    role = create_role(db, role_data.model_copy(update={"name": code}))
    from app.models.access_model import Permission
    from app.permissions import SYSTEM_ROLE_DEFAULTS
    from app.services.permission_catalog import grant_system_defaults

    if code in SYSTEM_ROLE_DEFAULTS and db.query(Permission.permission_id).first() is not None:
        # A re-created built-in role starts with its usual permissions.
        grant_system_defaults(db, role)
        db.commit()
        db.refresh(role)
    return role


def get_roles_service(db: Session):
    return get_roles(db)


def get_role_by_id_service(db: Session, role_id: int):
    role = get_role_by_id(db, role_id)

    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rol no encontrado")

    return role


def update_role_service(db: Session, role_id: int, role_data: RoleUpdate, actor=None):
    lock_access(db)
    current = get_role_by_id_service(db, role_id)
    if role_data.scope is not None and role_data.scope != current.scope:
        ensure_scope_allowed(actor, role_data.scope)
        ensure_members_fit_scope(current, role_data.scope)
    if "name" in role_data.model_fields_set and role_data.name != current.name:
        raise HTTPException(409, "El código del rol es fijo. Cambia su etiqueta visible")
    if "description" in role_data.model_fields_set and role_data.description is None:
        raise HTTPException(422, "Escribe una descripción para el rol")
    role = update_role(db, role_id, role_data)

    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rol no encontrado")

    return role


def delete_role_service(db: Session, role_id: int):
    lock_access(db)
    current = get_role_by_id_service(db, role_id)
    if current.name.casefold() in SYSTEM_ROLES or current.users:
        raise HTTPException(
            409, "Conserva los roles del sistema y los roles con cuentas vinculadas"
        )
    role = delete_role(db, role_id)

    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rol no encontrado")

    return {"message": "Rol eliminado"}
