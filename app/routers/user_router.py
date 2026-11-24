from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.auth import (
    account_is_active,
    ensure_role_within_actor,
    has_permission,
    require_permissions,
    role_permission_slugs,
)
from app.db.Session import get_db
from app.models.role_model import Role
from app.models.user_model import User
from app.pagination import page_query
from app.schemas.user_schema import UserCreate, UserOut, UserPasswordReset, UserUpdate
from app.services.account_sessions import lock_account, revoke_account_sessions
from app.services.billing.limits import ensure_room, is_staff_role
from app.services.email_service import deliver_after_commit
from app.services.governance_workflow import record
from app.services.user_services import (
    create_user_service,
    delete_user_service,
    get_user_by_id_service,
    send_invitation,
    update_user_service,
)
from app.services.write_locks import lock_access

router = APIRouter(prefix="/users", tags=["users"])
access_manager = require_permissions("users.manage")


@router.post("/", response_model=UserOut)
def create_user(
    user_data: UserCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    actor: User = Depends(access_manager),
):
    lock_access(db)
    ensure_role_within_actor(db, actor, user_data.role_id)
    user = create_user_service(db, user_data, actor)
    deliver_after_commit(background_tasks, db)
    return user


@router.post("/{user_id}/invitation", status_code=202)
def resend_invitation(
    user_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    actor: User = Depends(access_manager),
):
    """Send a new activation link; earlier links stop working."""
    lock_access(db)
    target = managed_target(db, actor, user_id)
    send_invitation(db, target)
    record(db, actor, "user.invitation.sent", f"user:{user_id}", target.email)
    db.commit()
    deliver_after_commit(background_tasks, db)
    return {"message": f"Invitación enviada a {target.email}"}


@router.get("/", response_model=list[UserOut], dependencies=[Depends(access_manager)])
def get_users(
    response: Response,
    q: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int | None = Query(None, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(User).options(
        joinedload(User.role),
        joinedload(User.student),
        joinedload(User.teacher),
        joinedload(User.guardian),
    )
    if q and (term := q.strip()):
        query = query.filter(
            or_(
                User.username.icontains(term, autoescape=True),
                User.email.icontains(term, autoescape=True),
            )
        )
    return page_query(query.order_by(User.user_id), response, skip, limit)


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
    lock_access(db)
    target = managed_target(db, actor, user_id)
    if "role_id" in user_data.model_fields_set:
        if user_data.role_id is None:
            raise HTTPException(422, "El rol no puede ser nulo")
        if user_data.role_id != target.role_id:
            ensure_role_within_actor(db, actor, user_data.role_id)
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
    lock_access(db)
    if user_id == actor.user_id:
        raise HTTPException(409, "No puedes eliminar tu propia cuenta administrativa")
    managed_target(db, actor, user_id)
    ensure_other_manager(db, user_id)
    record(
        db,
        actor,
        "user.deleted",
        f"user:{user_id}",
        "Eliminación administrativa; se verificó continuidad de acceso",
    )
    try:
        return delete_user_service(db, user_id)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409,
            "La cuenta tiene historial (notas, pagos, registros u otras acciones) y no se puede "
            "eliminar. Desactívala para quitarle el acceso y conservar el historial",
        ) from None


@router.post("/{user_id}/deactivate", response_model=UserOut)
def deactivate_user(
    user_id: int, db: Session = Depends(get_db), actor: User = Depends(access_manager)
):
    lock_access(db)
    if user_id == actor.user_id:
        raise HTTPException(409, "No puedes desactivar tu propia cuenta")
    target = managed_target(db, actor, user_id)
    if target.active:
        ensure_other_manager(db, user_id)
        target = lock_account(db, target)
        target.active = False
        revoke_account_sessions(db, target)
        record(
            db,
            actor,
            "user.deactivated",
            f"user:{user_id}",
            "Cuenta desactivada; se revocaron sus sesiones",
        )
        db.commit()
        db.refresh(target)
    return target


@router.post("/{user_id}/activate", response_model=UserOut)
def activate_user(
    user_id: int, db: Session = Depends(get_db), actor: User = Depends(access_manager)
):
    lock_access(db)
    target = managed_target(db, actor, user_id)
    if not target.active:
        if is_staff_role(db, target.role_id):
            ensure_room(db, staff=1)
        target.active = True
        record(db, actor, "user.activated", f"user:{user_id}", "Cuenta reactivada")
        db.commit()
        db.refresh(target)
    return target


@router.post("/{user_id}/password", status_code=204)
def reset_user_password(
    user_id: int,
    data: UserPasswordReset,
    db: Session = Depends(get_db),
    actor: User = Depends(access_manager),
):
    lock_access(db)
    managed_target(db, actor, user_id)
    record(db, actor, "user.password.reset", f"user:{user_id}", "Restablecimiento administrativo")
    update_user_service(db, user_id, UserUpdate(password=data.password))


def managed_target(db: Session, actor: User, user_id: int) -> User:
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(404, "Usuario no encontrado")
    ensure_role_within_actor(db, actor, target.role_id)
    return target


def ensure_other_manager(db, user_id, new_role=None):
    def capable(user):
        if not account_is_active(user):
            return False
        try:
            access_manager(current_user=user, db=db)
            return True
        except HTTPException:
            return False

    target = db.get(User, user_id)
    if target is None or not capable(target):
        return
    if new_role is not None and new_role != target.role_id:
        new = db.get(Role, new_role)
        keeps = new is not None and {"users.manage", "roles.manage"} <= role_permission_slugs(
            db, new.role_id
        )
        if keeps and new.scope == "institution":
            return
    others = db.query(User).filter(User.user_id != user_id, User.active.is_(True)).all()
    if not any(capable(other) and has_permission(other, "roles.manage") for other in others):
        raise HTTPException(
            409, "Debe conservarse al menos una cuenta activa que gestione usuarios y roles"
        )
    if not target or not capable(target) or new_role == target.role_id:
        return
    if not any(capable(u) for u in db.query(User).filter(User.user_id != user_id)):
        raise HTTPException(409, "Debe conservarse al menos un usuario con gestión de acceso")
