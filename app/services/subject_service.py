from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.subject_repository import (
    create_subject,
    delete_subject,
    get_subject_by_id,
    get_subjects,
    update_subject,
)
from app.schemas.subject_schema import SubjectCreate, SubjectUpdate


def create_subject_service(db: Session, subject_data: SubjectCreate):

    subjects = get_subjects(db)

    for subject in subjects:
        if subject.code == subject_data.code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Code already exist"
            )

    return create_subject(db, subject_data)


def get_subjects_service(db: Session):
    return get_subjects(db)


def get_subject_by_id_service(db: Session, subject_id: int):

    subject = get_subject_by_id(db, subject_id)

    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    return subject


def update_subject_service(db: Session, subject_id: int, subject_data: SubjectUpdate):

    subject = update_subject(db, subject_id, subject_data)

    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    return subject


def delete_subject_service(db: Session, subject_id: int):

    subject = delete_subject(db, subject_id)

    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    return {"message": "Subject deleted successfully"}
