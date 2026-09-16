from sqlalchemy.orm import Session

from app.models.subject_model import Subject
from app.schemas.subject_schema import SubjectCreate, SubjectUpdate


def create_subject(db: Session, subject_data: SubjectCreate):

    subject = Subject(**subject_data.model_dump())

    db.add(subject)
    db.commit()
    db.refresh(subject)

    return subject


def get_subjects(db: Session):
    return db.query(Subject).all()


def get_subject_by_id(db: Session, subject_id: int):
    return db.query(Subject).filter(Subject.subject_id == subject_id).first()


def update_subject(db: Session, subject_id: int, subject_data: SubjectUpdate):

    subject = get_subject_by_id(db, subject_id)

    if not subject:
        return None

    update_data = subject_data.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(subject, key, value)

    db.commit()
    db.refresh(subject)

    return subject


def delete_subject(db: Session, subject_id: int):

    subject = get_subject_by_id(db, subject_id)

    if not subject:
        return None

    db.delete(subject)
    db.commit()

    return True
