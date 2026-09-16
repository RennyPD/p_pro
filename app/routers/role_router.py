from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import require_roles
from app.db.Session import get_db
from app.pagination import paginate_and_filter
from app.schemas.role_schema import RoleCreate, RoleOut, RoleUpdate
from app.services.role_service import (
    create_role_service,
    delete_role_service,
    get_role_by_id_service,
    get_roles_service,
    update_role_service,
)

router = APIRouter(prefix="/roles", tags=["roles"])


@router.post("/", response_model=RoleOut, dependencies=[Depends(require_roles("admin"))])
def create_role(role_data: RoleCreate, db: Session = Depends(get_db)):
    return create_role_service(db, role_data)


@router.get("/", response_model=list[RoleOut], dependencies=[Depends(require_roles("admin"))])
def get_roles(
    q: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return paginate_and_filter(get_roles_service(db), skip, limit, q, ("name", "description"))


@router.get("/{role_id}", response_model=RoleOut, dependencies=[Depends(require_roles("admin"))])
def get_role_by_id(role_id: int, db: Session = Depends(get_db)):
    return get_role_by_id_service(db, role_id)


@router.patch("/{role_id}", response_model=RoleOut, dependencies=[Depends(require_roles("admin"))])
def update_role(role_id: int, role_data: RoleUpdate, db: Session = Depends(get_db)):
    return update_role_service(db, role_id, role_data)


@router.delete("/{role_id}", dependencies=[Depends(require_roles("admin"))])
def delete_role(role_id: int, db: Session = Depends(get_db)):
    return delete_role_service(db, role_id)
