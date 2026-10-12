from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.curriculum_model import CurriculumCourse
from app.models.section_model import Section
from app.models.subject_model import Subject
from app.repositories.subject_repository import (
    create_subject,
    delete_subject,
    get_subject_by_id,
    get_subjects,
    update_subject,
)
from app.schemas.subject_schema import SubjectCreate, SubjectUpdate


def create_subject_service(db: Session, subject_data: SubjectCreate):

    ensure_unique_code(db, subject_data.code)

    return create_subject(db, subject_data)


def get_subjects_service(db: Session, career_id: int | None = None):
    if career_id is not None:
        return (
            db.query(Subject)
            .join(CurriculumCourse, CurriculumCourse.subject_id == Subject.subject_id)
            .filter(CurriculumCourse.career_id == career_id)
            .all()
        )
    return get_subjects(db)


def get_subject_by_id_service(db: Session, subject_id: int):

    subject = get_subject_by_id(db, subject_id)

    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    return subject


def update_subject_service(db: Session, subject_id: int, subject_data: SubjectUpdate):
    get_subject_by_id_service(db, subject_id)
    if subject_data.code is not None:
        ensure_unique_code(db, subject_data.code, subject_id)
    subject = update_subject(db, subject_id, subject_data)

    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    return subject


def delete_subject_service(db: Session, subject_id: int):
    get_subject_by_id_service(db, subject_id)
    linked_plan = (
        db.query(CurriculumCourse)
        .filter(
            or_(
                CurriculumCourse.subject_id == subject_id,
                CurriculumCourse.prerequisite_subject_id == subject_id,
                CurriculumCourse.corequisite_subject_id == subject_id,
            )
        )
        .first()
    )
    if linked_plan or db.query(Section).filter(Section.subject_id == subject_id).first():
        raise HTTPException(
            status_code=409,
            detail="No se puede eliminar: la asignatura está vinculada a un pensum, requisito o sección. Revisa su ficha antes de modificar esas relaciones.",
        )
    subject = delete_subject(db, subject_id)

    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    return {"message": "Subject deleted successfully"}


def ensure_unique_code(db: Session, code: str, subject_id: int | None = None):
    query = db.query(Subject).filter(func.lower(Subject.code) == code.lower())
    if subject_id is not None:
        query = query.filter(Subject.subject_id != subject_id)
    if query.first():
        raise HTTPException(status_code=409, detail="Ya existe una asignatura con ese código")
