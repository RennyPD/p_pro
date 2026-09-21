from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_permissions
from app.db.Session import get_db
from app.pagination import paginate_and_filter
from app.schemas.subject_schema import SubjectCreate, SubjectOut, SubjectUpdate
from app.services.subject_service import (
    create_subject_service,
    delete_subject_service,
    get_subject_by_id_service,
    get_subjects_service,
    update_subject_service,
)

router = APIRouter(prefix="/subjects", tags=["subjects"])
subject_manager = require_permissions("academic.manage", fallback_roles=("admin",))


@router.post("/", response_model=SubjectOut, dependencies=[Depends(subject_manager)])
def create_subject(subject_data: SubjectCreate, db: Session = Depends(get_db)):
    return create_subject_service(db, subject_data)


@router.get("/", response_model=list[SubjectOut], dependencies=[Depends(get_current_user)])
def get_subjects(
    q: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return paginate_and_filter(get_subjects_service(db), skip, limit, q, ("code", "description"))


@router.get("/{subject_id}", response_model=SubjectOut, dependencies=[Depends(get_current_user)])
def get_subject_by_id(subject_id: int, db: Session = Depends(get_db)):
    return get_subject_by_id_service(db, subject_id)


@router.patch("/{subject_id}", response_model=SubjectOut, dependencies=[Depends(subject_manager)])
def update_subject(subject_id: int, subject_data: SubjectUpdate, db: Session = Depends(get_db)):
    return update_subject_service(db, subject_id, subject_data)


@router.delete("/{subject_id}", dependencies=[Depends(subject_manager)])
def delete_subject(subject_id: int, db: Session = Depends(get_db)):
    return delete_subject_service(db, subject_id)
