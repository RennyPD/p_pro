from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.configuration_model import InstitutionSettings
from app.repositories.student_repository import (
    create_student,
    delete_student,
    get_student_by_id,
    get_students,
    update_student,
)
from app.schemas.student_schema import StudentCreate, StudentUpdate


def create_student_service(db: Session, student_data: StudentCreate):
    students = get_students(db)

    for student in students:
        if student.email == student_data.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Email already exists"
            )

    if not student_data.enrollment_number:
        settings = db.get(InstitutionSettings, 1)
        if settings is None:
            settings = InstitutionSettings(settings_id=1)
            db.add(settings)
            db.flush()
        year = datetime.now(UTC).year
        sequence = str(settings.next_enrollment_number).zfill(settings.enrollment_digits)
        generated = f"{settings.enrollment_prefix}-{year}-{sequence}"
        settings.next_enrollment_number += 1
        student_data = student_data.model_copy(update={"enrollment_number": generated})
    return create_student(db, student_data)


def get_students_service(db: Session):
    return get_students(db)


def get_student_by_id_service(db: Session, student_id: int):

    student = get_student_by_id(db, student_id)

    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    return student


def update_student_service(db: Session, student_id: int, student_data: StudentUpdate):

    student = update_student(db, student_id, student_data)

    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    return student


def delete_student_service(db: Session, student_id: int):

    student = delete_student(db, student_id)

    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    return {"message": "Student deleted successfully"}
