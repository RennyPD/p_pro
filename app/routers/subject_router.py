from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.Session import get_db

from app.schemas.subject_schema import (
    SubjectCreate,
    SubjectUpdate,
    SubjectOut
)
from app.services.subject_service import (
    create_subject_service,
    get_subjects_service,
    get_subject_by_id_service,
    update_subject_service,
    delete_subject_service
)

router = APIRouter(
    prefix="/subjects",
    tags=["subjects"]
)

@router.post("/", response_model=SubjectOut)
def create_subject(
    subject_data: SubjectCreate,
    db: Session = Depends(get_db)
):
    return create_subject_service(db, subject_data)

@router.get("/", response_model=list[SubjectOut])
def get_subjects(
    db: Session = Depends(get_db)
):
    return get_subjects_service(db)

@router.get("/{subject_id}", response_model=SubjectOut)
def get_subject_by_id(
    subject_id: int,
    db: Session = Depends(get_db)
):
    return get_subject_by_id_service(db, subject_id)

@router.put("/{subject_id}", response_model=SubjectOut)
def update_subject(
    subject_id: int,
    subject_data: SubjectUpdate,
    db: Session = Depends(get_db)
):
    return update_subject_service(db, subject_id, subject_data)

@router.delete("/{subject_id}")
def delete_subject(
    subject_id: int,
    db: Session = Depends(get_db)
):
    return delete_subject_service(db, subject_id)

