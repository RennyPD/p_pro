from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_permissions
from app.db.Session import get_db
from app.models.access_model import Permission, RolePermission
from app.models.role_model import Role
from app.models.user_model import User
from app.services.governance_workflow import history, lock_governance, record

router = APIRouter(prefix="/access", tags=["access control"])
access_manager = require_permissions("access.manage", fallback_roles=("admin",))


class PermissionCreate(BaseModel):
    slug: str
    description: str


class RolePermissionUpdate(BaseModel):
    permissions: list[str]
    reason: str = "Actualización de permisos"
    expected_permissions: list[str] | None = None


@router.get("/permissions", dependencies=[Depends(access_manager)])
def permissions(db: Session = Depends(get_db)):
    return db.query(Permission).order_by(Permission.slug).all()


@router.post("/permissions", dependencies=[Depends(access_manager)])
def create_permission(data: PermissionCreate, db: Session = Depends(get_db)):
    item = Permission(**data.model_dump())
    db.add(item)
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
    lock_governance(db)
    if db.get(Role, role_id) is None:
        raise HTTPException(status_code=404, detail="Role not found")
    selected = db.query(Permission).filter(Permission.slug.in_(data.permissions)).all()
    if len(selected) != len(set(data.permissions)):
        raise HTTPException(status_code=422, detail="One or more permissions do not exist")
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
    if role_id == user.role_id and (
        {"access.manage", "academic.manage", "reports.view"} & set(before)
    ) - set(data.permissions):
        raise HTTPException(
            409, "No puedes retirar tus propios permisos esenciales desde esta sesión"
        )
    if "access.manage" in before and "access.manage" not in data.permissions:
        alternatives = (
            db.query(User)
            .join(RolePermission, User.role_id == RolePermission.role_id)
            .join(Permission, RolePermission.permission_id == Permission.permission_id)
            .filter(Permission.slug == "access.manage", User.role_id != role_id)
            .count()
        )
        if not alternatives:
            raise HTTPException(409, "Debe quedar al menos un usuario con gestión de accesos")
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
        raise HTTPException(status_code=404, detail="Role not found")
    values = (
        db.query(Permission.slug)
        .join(RolePermission)
        .filter(RolePermission.role_id == role_id)
        .all()
    )
    return {"role_id": role_id, "permissions": sorted(row[0] for row in values)}


@router.get("/me")
def my_permissions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    values = (
        db.query(Permission.slug)
        .join(RolePermission)
        .filter(RolePermission.role_id == user.role_id)
        .all()
    )
    return {"permissions": sorted(row[0] for row in values), "configured": db.query(Permission).count() > 0}
