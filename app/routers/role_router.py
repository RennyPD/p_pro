from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.auth import require_permissions, role_permission_slugs
from app.db.Session import get_db
from app.models.role_model import Role
from app.models.user_model import User
from app.pagination import page_query, search
from app.schemas.role_schema import RoleCreate, RoleOut, RoleUpdate
from app.services.governance_workflow import record
from app.services.role_service import (
    create_role_service,
    delete_role_service,
    get_role_by_id_service,
    update_role_service,
)

router = APIRouter(prefix="/roles", tags=["roles"])
access_manager = require_permissions("roles.manage")


def role_out(db: Session, role) -> RoleOut:
    return RoleOut.model_validate(role).model_copy(
        update={
            "user_count": len(role.users),
            "permission_count": len(role_permission_slugs(db, role.role_id)),
        }
    )


@router.post("/", response_model=RoleOut)
def create_role(
    role_data: RoleCreate, db: Session = Depends(get_db), actor: User = Depends(access_manager)
):
    role = create_role_service(db, role_data, actor)
    record(db, actor, "role.created", f"role:{role.role_id}", f"Alcance {role.scope}")
    db.commit()
    return role_out(db, role)


@router.get("/", response_model=list[RoleOut], dependencies=[Depends(access_manager)])
def get_roles(
    response: Response,
    q: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = search(db.query(Role), q, Role.name, Role.label, Role.description)
    roles = page_query(query.order_by(Role.role_id), response, skip, limit)
    return [role_out(db, role) for role in roles]


@router.get("/{role_id}", response_model=RoleOut, dependencies=[Depends(access_manager)])
def get_role_by_id(role_id: int, db: Session = Depends(get_db)):
    return role_out(db, get_role_by_id_service(db, role_id))


@router.patch("/{role_id}", response_model=RoleOut)
def update_role(
    role_id: int,
    role_data: RoleUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(access_manager),
):
    return role_out(db, update_role_service(db, role_id, role_data, actor))


@router.delete("/{role_id}")
def delete_role(role_id: int, db: Session = Depends(get_db), actor: User = Depends(access_manager)):
    return delete_role_service(db, role_id, actor)
