from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import (
    ensure_role_within_actor,
    get_current_user,
    require_permissions,
    role_permission_slugs,
    role_scope,
)
from app.db.Session import get_db
from app.models.access_model import Permission, RolePermission
from app.models.role_model import Role
from app.models.user_model import User
from app.permissions import INSTITUTIONAL_PERMISSIONS, PERMISSIONS, SCOPES
from app.services.governance_workflow import history, record
from app.services.permission_catalog import ensure_catalog
from app.services.write_locks import lock_access

router = APIRouter(prefix="/access", tags=["access control"])
access_manager = require_permissions("roles.manage")


class PermissionCreate(BaseModel):
    slug: str
    description: str


class RolePermissionUpdate(BaseModel):
    permissions: list[str]
    reason: str = "Actualización de permisos"
    expected_permissions: list[str] | None = None


@router.get("/permissions", dependencies=[Depends(access_manager)])
def permissions(db: Session = Depends(get_db)):
    """The permission catalog, grouped by module for the role editor."""
    ensure_catalog(db)
    db.commit()
    return [
        {
            "slug": item.slug,
            "module": item.module,
            "label": item.label,
            "description": item.description,
            "institutional": item.slug in INSTITUTIONAL_PERMISSIONS,
        }
        for item in PERMISSIONS
    ]


@router.get("/scopes", dependencies=[Depends(access_manager)])
def scopes():
    return [{"value": key, "label": label} for key, label in SCOPES.items()]


@router.post("/permissions")
def create_permission(
    data: PermissionCreate, db: Session = Depends(get_db), user: User = Depends(access_manager)
):
    lock_access(db)
    item = Permission(**data.model_dump())
    db.add(item)
    db.flush()
    # The creator holds the new grant, so it can delegate it without escalating.
    db.add(RolePermission(role_id=user.role_id, permission_id=item.permission_id))
    record(db, user, "permission.created", f"permission:{item.slug}", data.description[:250])
    db.commit()
    db.refresh(item)
    return item


@router.put("/roles/{role_id}/permissions")
def set_role_permissions(
    role_id: int,
    data: RolePermissionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(access_manager),
):
    lock_access(db)
    role = db.get(Role, role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Rol no encontrado")
    ensure_catalog(db)
    selected = db.query(Permission).filter(Permission.slug.in_(data.permissions)).all()
    if len(selected) != len(set(data.permissions)):
        raise HTTPException(status_code=422, detail="Uno o más permisos no existen")
    before = sorted(
        row[0]
        for row in db.query(Permission.slug)
        .join(RolePermission)
        .filter(RolePermission.role_id == role_id)
    )
    if data.expected_permissions is not None and sorted(data.expected_permissions) != before:
        raise HTTPException(409, "Los permisos cambiaron; recarga antes de guardar")
    if len(data.reason.strip()) < 3:
        raise HTTPException(422, "Indica un motivo para cambiar permisos")
    ensure_role_within_actor(db, user, role_id)
    if set(data.permissions) - set(before) - role_permission_slugs(db, user.role_id):
        raise HTTPException(403, "Solo puedes conceder permisos que tu cuenta tiene")
    essential = {"roles.manage", "users.manage"}
    effective_before = role_permission_slugs(db, role_id)
    if role_id == user.role_id and essential & effective_before - set(data.permissions):
        raise HTTPException(409, "No puedes quitar a tu propio rol la gestión de usuarios y roles")
    if "roles.manage" in effective_before and "roles.manage" not in data.permissions:
        alternatives = [
            other
            for other in db.query(User).filter(User.role_id != role_id, User.active.is_(True))
            if "roles.manage" in role_permission_slugs(db, other.role_id)
            and role_scope(other) == "institution"
        ]
        if not alternatives:
            raise HTTPException(409, "Debe quedar al menos un usuario con gestión de roles")
    db.query(RolePermission).filter(RolePermission.role_id == role_id).delete()
    db.add_all(
        [RolePermission(role_id=role_id, permission_id=item.permission_id) for item in selected]
    )
    record(
        db,
        user,
        "role.permissions.updated",
        f"role:{role_id}",
        f"{data.reason[:250]}; antes={','.join(before)}; después={','.join(sorted(data.permissions))}",
    )
    db.commit()
    return {"role_id": role_id, "permissions": sorted(item.slug for item in selected)}


@router.get("/roles/{role_id}/history", dependencies=[Depends(access_manager)])
def permissions_history(role_id: int, db: Session = Depends(get_db)):
    return history(db, f"role:{role_id}")


@router.get("/roles/{role_id}/permissions", dependencies=[Depends(access_manager)])
def role_permissions(role_id: int, db: Session = Depends(get_db)):
    if db.get(Role, role_id) is None:
        raise HTTPException(status_code=404, detail="Rol no encontrado")
    values = (
        db.query(Permission.slug)
        .join(RolePermission)
        .filter(RolePermission.role_id == role_id)
        .all()
    )
    return {"role_id": role_id, "permissions": sorted(row[0] for row in values)}


@router.get("/me")
def my_permissions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Effective permissions and data scope of the signed-in account."""
    return {
        "permissions": sorted(role_permission_slugs(db, user.role_id)),
        "scope": role_scope(user),
        "role_title": user.role.role_title,
        "configured": True,
    }
