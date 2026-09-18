from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_roles
from app.db.Session import get_db
from app.models.access_model import Permission, RolePermission
from app.models.role_model import Role
from app.models.user_model import User

router = APIRouter(prefix="/access", tags=["access control"])


class PermissionCreate(BaseModel):
    slug: str
    description: str


class RolePermissionUpdate(BaseModel):
    permissions: list[str]


@router.get("/permissions", dependencies=[Depends(require_roles("admin"))])
def permissions(db: Session = Depends(get_db)):
    return db.query(Permission).order_by(Permission.slug).all()


@router.post("/permissions", dependencies=[Depends(require_roles("admin"))])
def create_permission(data: PermissionCreate, db: Session = Depends(get_db)):
    item = Permission(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/roles/{role_id}/permissions", dependencies=[Depends(require_roles("admin"))])
def set_role_permissions(role_id: int, data: RolePermissionUpdate, db: Session = Depends(get_db)):
    if db.get(Role, role_id) is None:
        raise HTTPException(status_code=404, detail="Role not found")
    selected = db.query(Permission).filter(Permission.slug.in_(data.permissions)).all()
    if len(selected) != len(set(data.permissions)):
        raise HTTPException(status_code=422, detail="One or more permissions do not exist")
    db.query(RolePermission).filter(RolePermission.role_id == role_id).delete()
    db.add_all(
        [RolePermission(role_id=role_id, permission_id=item.permission_id) for item in selected]
    )
    db.commit()
    return {"role_id": role_id, "permissions": sorted(item.slug for item in selected)}


@router.get("/me")
def my_permissions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    values = (
        db.query(Permission.slug)
        .join(RolePermission)
        .filter(RolePermission.role_id == user.role_id)
        .all()
    )
    return {"permissions": sorted(row[0] for row in values)}
