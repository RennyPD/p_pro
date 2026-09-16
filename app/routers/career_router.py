from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_roles
from app.db.Session import get_db
from app.pagination import paginate_and_filter
from app.schemas.career_schema import CareerCreate, CareerOut, CareerUpdate
from app.services.career_service import (
    create_career_service,
    delete_career_service,
    get_career_service,
    get_careers_service,
    update_career_service,
)

router = APIRouter(prefix="/careers", tags=["careers"])


@router.post("/", response_model=CareerOut, dependencies=[Depends(require_roles("admin"))])
def create_career(data: CareerCreate, db: Session = Depends(get_db)):
    return create_career_service(db, data)


@router.get("/", response_model=list[CareerOut], dependencies=[Depends(get_current_user)])
def list_careers(
    q: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return paginate_and_filter(get_careers_service(db), skip, limit, q, ("name", "description"))


@router.get("/{career_id}", response_model=CareerOut, dependencies=[Depends(get_current_user)])
def get_career(career_id: int, db: Session = Depends(get_db)):
    return get_career_service(db, career_id)


@router.patch(
    "/{career_id}", response_model=CareerOut, dependencies=[Depends(require_roles("admin"))]
)
def update_career(career_id: int, data: CareerUpdate, db: Session = Depends(get_db)):
    return update_career_service(db, career_id, data)


@router.delete("/{career_id}", dependencies=[Depends(require_roles("admin"))])
def delete_career(career_id: int, db: Session = Depends(get_db)):
    return delete_career_service(db, career_id)
