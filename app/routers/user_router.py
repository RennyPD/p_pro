from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_permissions
from app.db.Session import get_db
from app.models.user_model import User
from app.schemas.user_schema import UserCreate, UserOut, UserUpdate
from app.services.governance_workflow import lock_governance, record
from app.services.user_services import (
    create_user_service,
    delete_user_service,
    get_user_by_id_service,
    get_users_service,
    update_user_service,
)

router = APIRouter(prefix="/users", tags=["users"])
access_manager = require_permissions("access.manage", fallback_roles=("admin",))


@router.post("/", response_model=UserOut, dependencies=[Depends(access_manager)])
def create_user(user_data: UserCreate, db: Session = Depends(get_db)):
    return create_user_service(db, user_data)


@router.get("/", response_model=list[UserOut], dependencies=[Depends(access_manager)])
def get_users(db: Session = Depends(get_db)):
    return get_users_service(db)


@router.get("/{user_id}", response_model=UserOut, dependencies=[Depends(access_manager)])
def get_user_by_id(user_id: int, db: Session = Depends(get_db)):
    return get_user_by_id_service(db, user_id)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(access_manager),
):
    lock_governance(db)
    if "role_id" in user_data.model_fields_set:
        if user_data.role_id is None:
            raise HTTPException(422, "El rol no puede ser nulo")
        if user_id == actor.user_id and user_data.role_id != actor.role_id:
            raise HTTPException(409, "No cambies tu propio rol desde esta sesión")
        ensure_other_manager(db, user_id, user_data.role_id)
    record(
        db,
        actor,
        "user.updated",
        f"user:{user_id}",
        "Actualización administrativa de usuario; campos: "
        + ",".join(user_data.model_fields_set - {"password"}),
    )
    return update_user_service(db, user_id, user_data)


@router.delete("/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), actor: User = Depends(access_manager)):
    lock_governance(db)
    if user_id == actor.user_id:
        raise HTTPException(409, "No puedes eliminar tu propia cuenta administrativa")
    ensure_other_manager(db, user_id)
    record(
        db,
        actor,
        "user.deleted",
        f"user:{user_id}",
        "Eliminación administrativa; se verificó continuidad de acceso",
    )
    return delete_user_service(db, user_id)


def ensure_other_manager(db, user_id, new_role=None):
    def capable(user):
        try:
            access_manager(current_user=user, db=db)
            return True
        except HTTPException:
            return False

    target = db.get(User, user_id)
    if not target or not capable(target) or new_role == target.role_id:
        return
    if not any(capable(u) for u in db.query(User).filter(User.user_id != user_id)):
        raise HTTPException(409, "Debe conservarse al menos un usuario con gestión de acceso")
